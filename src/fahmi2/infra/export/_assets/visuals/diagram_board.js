/* Galerie de schémas (Visualisations).
   Les diagrammes « graphe » (flowchart/hierarchy/decision_tree/cycle) sont des petites
   instances Cytoscape, **initialisées paresseusement** (IntersectionObserver) à partir
   du JSON porté par ``data-graph``. Les diagrammes linéaires (timeline/comparison) sont
   du HTML/CSS déjà rendu côté serveur. Filtres par type + bascule de thème. */
(function () {
  "use strict";

  // La hauteur du canvas est fixée au rendu (côté serveur, selon le nombre de nœuds).
  // Ici, on borne le zoom à l'initialisation pour ne jamais rétrécir les libellés en
  // deçà du lisible (au-delà, l'utilisateur zoome/pane). Constantes centralisées.
  var FIT_PADDING = 22;
  var MIN_INITIAL_ZOOM = 0.62;  // plancher de lisibilité
  var MAX_INITIAL_ZOOM = 1.4;   // ne pas sur-grossir un graphe minuscule
  var ZOOM_BOUND_MIN = 0.25;
  var ZOOM_BOUND_MAX = 3.0;

  function use(ext) { if (ext && window.cytoscape) { try { cytoscape.use(ext); } catch (e) { /* déjà */ } } }
  use(window.cytoscapeDagre);

  function clamp(value, lo, hi) { return Math.max(lo, Math.min(hi, value)); }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function diagramStyles() {
    return [
      { selector: "node", style: {
        "background-color": cssVar("--accent-strong"), label: "data(label)",
        color: "#fff", "font-size": 12, "font-weight": 600, "text-valign": "center",
        "text-halign": "center", "text-wrap": "wrap", "text-max-width": 150,
        shape: "round-rectangle", width: "label", height: "label",
        padding: 11, "text-margin-y": 0
      } },
      { selector: 'node[role = "decision"]', style: {
        shape: "diamond", "background-color": cssVar("--example"), width: 60, height: 60
      } },
      { selector: 'node[role = "terminal"]', style: {
        shape: "round-rectangle", "background-color": cssVar("--term")
      } },
      { selector: "edge", style: {
        width: 1.8, "line-color": cssVar("--edge"), "target-arrow-color": cssVar("--edge"),
        "target-arrow-shape": "triangle", "curve-style": "bezier", label: "data(label)",
        "font-size": 10.5, color: cssVar("--t2"), "text-rotation": "autorotate",
        "text-background-color": cssVar("--surface"), "text-background-opacity": 0.9,
        "text-background-padding": 2
      } }
    ];
  }

  var instances = [];
  var lightboxCy = null;  // instance Cytoscape de l'overlay (détruite à la fermeture)

  function buildElements(spec) {
    var els = [];
    spec.nodes.forEach(function (n) {
      els.push({ data: { id: n.id, label: n.label, role: n.role || "" } });
    });
    spec.links.forEach(function (l, i) {
      els.push({ data: { id: "l" + i, source: l.from, target: l.to, label: l.label || "" } });
    });
    return els;
  }

  function layoutFor(spec) {
    return spec.cyclic
      ? { name: "concentric", animate: false, minNodeSpacing: 40 }
      : (window.cytoscapeDagre
        ? { name: "dagre", animate: false, rankDir: "TB", nodeSep: 24, rankSep: 44 }
        : { name: "breadthfirst", animate: false, directed: true });
  }

  function makeCy(container, spec) {
    return cytoscape({
      container: container, elements: buildElements(spec), style: diagramStyles(),
      layout: layoutFor(spec),
      // Zoom (molette) + déplacement (glisser) activés.
      userZoomingEnabled: true, userPanningEnabled: true,
      autoungrabify: true, boxSelectionEnabled: false,
      minZoom: ZOOM_BOUND_MIN, maxZoom: ZOOM_BOUND_MAX
    });
  }

  function initDiagram(container) {
    if (container.__done) { return; }
    container.__done = true;
    var cy = makeCy(container, JSON.parse(container.getAttribute("data-graph")));
    cy.fit(undefined, FIT_PADDING);
    // Plancher/plafond de lisibilité : si ``fit`` a trop réduit (graphe dense), on
    // remonte au plancher (l'utilisateur pane, ou agrandit en plein écran) ; on évite
    // aussi de sur-grossir un tout petit graphe.
    cy.zoom(clamp(cy.zoom(), MIN_INITIAL_ZOOM, MAX_INITIAL_ZOOM));
    cy.center();
    instances.push(cy);
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { if (e.isIntersecting) { initDiagram(e.target); } });
  }, { rootMargin: "120px" });
  document.querySelectorAll(".cy-diagram[data-graph]").forEach(function (c) { observer.observe(c); });

  // ---- Filtres par type ----
  function applyFilters() {
    var counts = 0;
    document.querySelectorAll(".card").forEach(function (card) {
      var chip = document.querySelector('.chip[data-type="' + card.getAttribute("data-type") + '"]');
      var on = !chip || !chip.classList.contains("off");
      card.classList.toggle("hidden", !on);
      if (on) { counts += 1; }
    });
    var empty = document.getElementById("empty");
    if (empty) { empty.style.display = counts === 0 ? "block" : "none"; }
  }
  document.querySelectorAll(".chip[data-type]").forEach(function (chip) {
    chip.addEventListener("click", function () { chip.classList.toggle("off"); applyFilters(); });
  });

  // ---- Plein écran (agrandir) ----
  // Pour les diagrammes complexes qu'une carte ne peut afficher lisiblement : overlay
  // pleine fenêtre. Les graphes y sont re-rendus dans une nouvelle instance Cytoscape
  // (zoom/pan, fit à la grande surface) ; les diagrammes linéaires (timeline/comparaison)
  // y sont clonés tels quels (HTML défilable). Fermeture : bouton ✕, Échap.
  var lightbox = document.getElementById("lightbox");
  var lightboxBody = document.getElementById("lightbox-body");
  var lightboxTitle = document.getElementById("lightbox-title");
  var lightboxClose = document.getElementById("lightbox-close");
  var lastTrigger = null;  // bouton .expand ayant ouvert l'overlay (focus restitué à la fermeture)

  function closeLightbox() {
    if (lightboxCy) { lightboxCy.destroy(); lightboxCy = null; }
    lightboxBody.innerHTML = "";
    lightbox.setAttribute("hidden", "");
    if (lastTrigger) { lastTrigger.focus(); lastTrigger = null; }  // retour du focus
  }

  function openLightbox(card, trigger) {
    if (lightboxCy) { lightboxCy.destroy(); lightboxCy = null; }  // ré-ouverture : pas de fuite
    lastTrigger = trigger || null;
    var h3 = card.querySelector("h3");
    lightboxTitle.textContent = h3 ? h3.textContent : "";
    lightboxBody.innerHTML = "";
    lightbox.removeAttribute("hidden");  // visible AVANT init (Cytoscape mesure la taille)
    var graph = card.querySelector(".cy-diagram[data-graph]");
    if (graph) {
      var full = document.createElement("div");
      full.className = "cy-full";
      lightboxBody.appendChild(full);
      lightboxCy = makeCy(full, JSON.parse(graph.getAttribute("data-graph")));
      lightboxCy.resize();
      lightboxCy.fit(undefined, 48);
    } else {
      var linear = card.querySelector(".timeline, .cmp");
      if (linear) { lightboxBody.appendChild(linear.cloneNode(true)); }
    }
    lightboxClose.focus();  // focus dans la modale (accessibilité clavier)
  }

  document.querySelectorAll(".expand").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var card = btn.closest(".card");
      if (card) { openLightbox(card, btn); }
    });
  });
  lightboxClose.addEventListener("click", closeLightbox);
  document.addEventListener("keydown", function (e) {
    if (lightbox.hasAttribute("hidden")) { return; }
    if (e.key === "Escape") { closeLightbox(); }
    // Piège de focus : le seul contrôle de la modale est le bouton de fermeture ;
    // on garde donc le focus dessus (Tab/Shift+Tab ne sortent pas de l'overlay).
    else if (e.key === "Tab") { e.preventDefault(); lightboxClose.focus(); }
  });

  // ---- Thème ----
  document.getElementById("theme").addEventListener("click", function () {
    var root = document.documentElement;
    root.setAttribute("data-theme", root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    instances.forEach(function (cy) { cy.style(diagramStyles()); });
    if (lightboxCy) { lightboxCy.style(diagramStyles()); }
  });

  window.__boardReady = true;  // sentinelle de vérification (Playwright)
  window.__board = { init: initDiagram, instances: instances, open: openLightbox, close: closeLightbox };
})();
