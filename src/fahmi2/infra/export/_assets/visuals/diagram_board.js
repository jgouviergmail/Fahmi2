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
  var SAVE_DEBOUNCE_MS = 250;  // débounce de la sauvegarde des positions au déplacement
  var store = window.__fahmi2LayoutStore || null;  // persistance (peut être indisponible)

  function use(ext) { if (ext && window.cytoscape) { try { cytoscape.use(ext); } catch (e) { /* déjà */ } } }
  use(window.cytoscapeDagre);

  function clamp(value, lo, hi) { return Math.max(lo, Math.min(hi, value)); }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  // ---- Persistance des positions (localStorage via _layout_store.js, partagé) ----
  function persistKey(el) {
    return (store && store.available && el) ? el.getAttribute("data-storage-key") : null;
  }
  function applySaved(cy, key) {
    if (!key) { return false; }
    var saved = store.read(key);
    if (!saved) { return false; }
    cy.batch(function () {
      cy.nodes().forEach(function (n) {
        var p = saved[n.id()]; if (p) { n.position({ x: p.x, y: p.y }); }
      });
    });
    return true;  // disposition restaurée → l'appelant peut éviter le clamp de zoom
  }
  function attachPersist(cy, key) {
    if (!key) { return; }
    var timer = null;
    cy.on("dragfree", "node", function () {
      if (timer) { clearTimeout(timer); }
      timer = setTimeout(function () {
        var map = {};
        cy.nodes().forEach(function (n) {
          var p = n.position(); map[n.id()] = { x: p.x, y: p.y };
        });
        store.write(key, map);
      }, SAVE_DEBOUNCE_MS);
    });
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
        // Losange **auto-dimensionné** au libellé (au lieu d'un 60×60 fixe qui
        // tronquait les questions longues). Padding généreux : le bloc de texte
        // centré tient dans la zone inscrite du losange ; max-width réduit pour un
        // bloc plus carré (mieux adapté à la forme).
        shape: "diamond", "background-color": cssVar("--example"),
        width: "label", height: "label", padding: 30, "text-max-width": 96
      } },
      { selector: 'node[role = "terminal"]', style: {
        shape: "round-rectangle", "background-color": cssVar("--term")
      } },
      { selector: "edge", style: {
        width: 1.8, "line-color": cssVar("--edge"), "target-arrow-color": cssVar("--edge"),
        "target-arrow-shape": "triangle", "curve-style": "bezier", label: "data(label)",
        // Libellés d'arêtes **horizontaux** (pas d'autorotate, illisible sur les
        // liens verticaux) + retour à la ligne (pas de troncature), sur fond opaque.
        "font-size": 10.5, color: cssVar("--t2"),
        "text-wrap": "wrap", "text-max-width": 120,
        "text-background-color": cssVar("--surface"), "text-background-opacity": 0.92,
        "text-background-padding": 3, "text-background-shape": "round-rectangle"
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
      // Zoom (molette), déplacement de la vue (glisser le fond) ET déplacement des
      // **nœuds** (``autoungrabify: false``) : l'utilisateur peut réagencer un
      // diagramme que l'auto-layout n'a pas parfaitement disposé.
      userZoomingEnabled: true, userPanningEnabled: true,
      autoungrabify: false, boxSelectionEnabled: false,
      minZoom: ZOOM_BOUND_MIN, maxZoom: ZOOM_BOUND_MAX
    });
  }

  function initDiagram(container) {
    if (container.__done) { return; }
    container.__done = true;
    var cy = makeCy(container, JSON.parse(container.getAttribute("data-graph")));
    container.__cy = cy;  // référencé par l'overlay pour lui propager ses positions à la fermeture
    var key = persistKey(container);
    var restored = applySaved(cy, key);  // positions sauvegardées si présentes (sinon layout calculé)
    cy.fit(undefined, FIT_PADDING);
    // Plancher/plafond de lisibilité réservé aux layouts AUTO-calculés : si ``fit`` a
    // trop réduit (graphe dense), on remonte au plancher (l'utilisateur pane, ou agrandit
    // en plein écran) ; on évite aussi de sur-grossir un tout petit graphe. Une
    // disposition MANUELLE restaurée (potentiellement étalée) n'est pas clampée — sinon
    // elle serait rognée à chaque ouverture (cohérent avec knowledge_map.js, qui ne
    // clampe pas non plus la restauration).
    if (!restored) {
      cy.zoom(clamp(cy.zoom(), MIN_INITIAL_ZOOM, MAX_INITIAL_ZOOM));
    }
    cy.center();
    attachPersist(cy, key);
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
  var lightboxReset = document.getElementById("lightbox-reset");
  var lastTrigger = null;  // bouton .expand ayant ouvert l'overlay (focus restitué à la fermeture)
  var lightboxSpec = null;  // spec du graphe ouvert (pour réinitialiser la disposition)
  // Clé localStorage du graphe ouvert, PARTAGÉE avec la carte d'origine : l'overlay est
  // l'éditeur AUTORITAIRE (ses positions sont propagées vers la carte à la fermeture).
  var lightboxKey = null;
  var lightboxCardCy = null;  // instance Cytoscape de la carte d'origine (propagation à la fermeture)

  function closeLightbox() {
    if (lightboxCy) { lightboxCy.destroy(); lightboxCy = null; }
    // Propager les positions persistées par l'overlay vers l'instance de la carte (même
    // clé partagée). Sans cela, la carte garde ses positions PÉRIMÉES en mémoire et un
    // futur ``dragfree`` y réécrirait la clé avec ce layout antérieur, écrasant
    // silencieusement le réagencement fait en plein écran (last-writer-wins).
    if (lightboxKey && lightboxCardCy) { applySaved(lightboxCardCy, lightboxKey); }
    lightboxSpec = null;
    lightboxKey = null;
    lightboxCardCy = null;
    lightboxBody.innerHTML = "";
    lightboxReset.setAttribute("hidden", "");
    lightbox.setAttribute("hidden", "");
    if (lastTrigger) { lastTrigger.focus(); lastTrigger = null; }  // retour du focus
  }

  function relayoutLightbox() {
    if (lightboxCy && lightboxSpec) {
      // Réinitialiser = oublier les positions persistées (dagre/concentric étant
      // déterministes, le recalcul redonne la disposition d'origine).
      if (lightboxKey && store) { store.remove(lightboxKey); }
      lightboxCy.layout(layoutFor(lightboxSpec)).run();
      lightboxCy.fit(undefined, 48);
    }
  }

  function openLightbox(card, trigger) {
    if (lightboxCy) { lightboxCy.destroy(); lightboxCy = null; }  // ré-ouverture : pas de fuite
    lightboxSpec = null;
    lightboxKey = null;
    lightboxCardCy = null;
    lastTrigger = trigger || null;
    var h3 = card.querySelector("h3");
    lightboxTitle.textContent = h3 ? h3.textContent : "";
    lightboxBody.innerHTML = "";
    lightbox.removeAttribute("hidden");  // visible AVANT init (Cytoscape mesure la taille)
    var graph = card.querySelector(".cy-diagram[data-graph]");
    if (graph) {
      lightboxSpec = JSON.parse(graph.getAttribute("data-graph"));
      lightboxKey = persistKey(graph);  // clé partagée avec la carte
      lightboxCardCy = graph.__cy || null;  // instance de carte à resynchroniser à la fermeture
      var full = document.createElement("div");
      full.className = "cy-full";
      lightboxBody.appendChild(full);
      lightboxCy = makeCy(full, lightboxSpec);
      applySaved(lightboxCy, lightboxKey);  // restaure le réagencement persisté
      lightboxCy.resize();
      lightboxCy.fit(undefined, 48);
      attachPersist(lightboxCy, lightboxKey);  // sauvegarde au déplacement
      lightboxReset.removeAttribute("hidden");  // « réinitialiser la disposition » (graphes)
    } else {
      var linear = card.querySelector(".timeline, .cmp");
      if (linear) { lightboxBody.appendChild(linear.cloneNode(true)); }
      lightboxReset.setAttribute("hidden", "");  // sans objet pour les diagrammes linéaires
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
  lightboxReset.addEventListener("click", relayoutLightbox);
  document.addEventListener("keydown", function (e) {
    if (lightbox.hasAttribute("hidden")) { return; }
    if (e.key === "Escape") { closeLightbox(); return; }
    if (e.key !== "Tab") { return; }
    // Piège de focus : Tab/Shift+Tab cyclent entre les contrôles de la modale
    // (réinitialiser si visible, puis fermer) sans en sortir.
    e.preventDefault();
    var controls = [];
    if (!lightboxReset.hasAttribute("hidden")) { controls.push(lightboxReset); }
    controls.push(lightboxClose);
    var index = controls.indexOf(document.activeElement);
    var next = (index + (e.shiftKey ? -1 : 1) + controls.length) % controls.length;
    controls[next].focus();
  });

  // ---- Thème ----
  document.getElementById("theme").addEventListener("click", function () {
    var root = document.documentElement;
    root.setAttribute("data-theme", root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    instances.forEach(function (cy) { cy.style(diagramStyles()); });
    if (lightboxCy) { lightboxCy.style(diagramStyles()); }
  });

  window.__boardReady = true;  // sentinelle de vérification (Playwright)
  window.__board = {
    init: initDiagram, instances: instances,
    open: openLightbox, close: closeLightbox, reset: relayoutLightbox
  };
})();
