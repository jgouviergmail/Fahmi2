/* Galerie de schémas (Visualisations).
   Les diagrammes « graphe » (flowchart/hierarchy/decision_tree/cycle) sont des petites
   instances Cytoscape, **initialisées paresseusement** (IntersectionObserver) à partir
   du JSON porté par ``data-graph``. Les diagrammes linéaires (timeline/comparison) sont
   du HTML/CSS déjà rendu côté serveur. Filtres par type + bascule de thème. */
(function () {
  "use strict";

  function use(ext) { if (ext && window.cytoscape) { try { cytoscape.use(ext); } catch (e) { /* déjà */ } } }
  use(window.cytoscapeDagre);

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function diagramStyles() {
    return [
      { selector: "node", style: {
        "background-color": cssVar("--accent-strong"), label: "data(label)",
        color: "#fff", "font-size": 10, "font-weight": 600, "text-valign": "center",
        "text-halign": "center", "text-wrap": "wrap", "text-max-width": 110,
        shape: "round-rectangle", width: "label", height: "label",
        padding: 10, "text-margin-y": 0
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
        "font-size": 9, color: cssVar("--t2"), "text-rotation": "autorotate",
        "text-background-color": cssVar("--surface"), "text-background-opacity": 0.9,
        "text-background-padding": 2
      } }
    ];
  }

  var instances = [];

  function initDiagram(container) {
    if (container.__done) { return; }
    container.__done = true;
    var spec = JSON.parse(container.getAttribute("data-graph"));
    var els = [];
    spec.nodes.forEach(function (n) {
      els.push({ data: { id: n.id, label: n.label, role: n.role || "" } });
    });
    spec.links.forEach(function (l, i) {
      els.push({ data: { id: "l" + i, source: l.from, target: l.to, label: l.label || "" } });
    });
    var layout = spec.cyclic
      ? { name: "concentric", animate: false, minNodeSpacing: 40 }
      : (window.cytoscapeDagre
        ? { name: "dagre", animate: false, rankDir: "TB", nodeSep: 24, rankSep: 44 }
        : { name: "breadthfirst", animate: false, directed: true });
    var cy = cytoscape({
      container: container, elements: els, style: diagramStyles(),
      layout: layout, userZoomingEnabled: false, userPanningEnabled: false,
      autoungrabify: true, boxSelectionEnabled: false
    });
    cy.fit(undefined, 18);
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

  // ---- Thème ----
  document.getElementById("theme").addEventListener("click", function () {
    var root = document.documentElement;
    root.setAttribute("data-theme", root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    instances.forEach(function (cy) { cy.style(diagramStyles()); });
  });

  window.__boardReady = true;  // sentinelle de vérification (Playwright)
  window.__board = { init: initDiagram, instances: instances };
})();
