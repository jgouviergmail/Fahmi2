/* Logique interactive de la carte de connaissances (Cytoscape).
   Données injectées dans <script id="km-data" type="application/json">.
   Deux modes : « réseau » (fcose, communautés en nœuds composés) et « arbre »
   (dagre/breadthfirst, enraciné sur le nœud focalisé). Recherche, filtres par type,
   panneau latéral de détail, bascule de thème. */
(function () {
  "use strict";

  // Constantes d'interaction/layout centralisées (aucun nombre magique dispersé) —
  // aligné sur le pattern de diagram_board.js.
  var WHEEL_SENSITIVITY = 0.2;
  var ZOOM_BOUND_MIN = 0.1;   // carte dense : plancher bas mais borné (pas d'invisibilité)
  var ZOOM_BOUND_MAX = 3.0;
  var ZOOM_STEP = 1.2;        // facteur des boutons zoom +/−
  var FIT_PADDING = 40;       // marge de cadrage (fit) réseau/arbre/bouton recadrer
  var SEARCH_FIT_PADDING = 60;// marge de cadrage sur les résultats de recherche
  var NETWORK_PADDING = 30;   // padding des layouts fcose/dagre/breadthfirst
  var DAGRE_NODE_SEP = 30;
  var DAGRE_RANK_SEP = 60;
  var MAX_PANEL_RELATIONS = 12;  // relations affichées dans le panneau latéral
  // Réglages fcose pour aérer le réseau (valeurs > défauts fcose 4500/50/75/0.25).
  // nodeRepulsion/idealEdgeLength DOIVENT être des fonctions (sinon ignorés par fcose).
  var FCOSE_NODE_REPULSION = 6500;
  var FCOSE_IDEAL_EDGE_LENGTH = 95;
  var FCOSE_NODE_SEPARATION = 110;
  var FCOSE_GRAVITY = 0.2;
  var SAVE_DEBOUNCE_MS = 250;  // débounce de la sauvegarde des positions au déplacement

  var DATA = JSON.parse(document.getElementById("km-data").textContent);
  var NODE_TYPES = ["concept", "glossary_term", "example", "idea"];
  var I = DATA.i18n || {};
  var EDGE_LABELS = I.edgeLabels || {};   // type de relation -> libellé localisé
  var TYPE_LABEL = I.typeLabels || {};    // type de nœud -> libellé localisé
  var UI = I.ui || {};                    // libellés d'interface du panneau
  var TYPE_VAR = {
    concept: "--concept", glossary_term: "--term", example: "--example", idea: "--idea"
  };
  // Persistance des positions (localStorage via _layout_store.js). Désactivée
  // silencieusement si indisponible (Safari/file://, navigation privée…).
  var STORAGE_KEY = DATA.storageKey || null;
  var store = window.__fahmi2LayoutStore || null;
  var persistEnabled = !!(store && store.available && STORAGE_KEY);

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function use(ext) { if (ext && window.cytoscape) { try { cytoscape.use(ext); } catch (e) { /* déjà enregistré */ } } }
  use(window.cytoscapeFcose);
  use(window.cytoscapeDagre);
  use(window.cytoscapeExpandCollapse);

  // ---- Construction des éléments Cytoscape ----
  function buildElements() {
    var els = [];
    DATA.communities.forEach(function (c) {
      els.push({ data: { id: "c" + c.id, label: c.label || "", kind: "community" } });
    });
    DATA.nodes.forEach(function (n) {
      var d = { id: n.id, label: n.label, type: n.type };
      if (n.community !== null && n.community !== undefined) { d.parent = "c" + n.community; }
      els.push({ data: d });
    });
    DATA.edges.forEach(function (e) {
      els.push({ data: { id: e.id, source: e.source, target: e.target, type: e.type,
        label: e.label || EDGE_LABELS[e.type] || "" } });
    });
    return els;
  }

  function styles() {
    return [
      { selector: "node[kind = 'community']", style: {
        "background-color": cssVar("--accent"), "background-opacity": 0.05,
        "border-width": 1, "border-color": cssVar("--border-card"),
        "border-opacity": 0.8, shape: "round-rectangle", padding: 18,
        label: "data(label)", "text-valign": "top", "text-halign": "center",
        "font-size": 12, "font-weight": 700, color: cssVar("--t2"),
        "text-margin-y": -6
      } },
      { selector: "node[kind != 'community']", style: {
        "background-color": function (n) { return cssVar(TYPE_VAR[n.data("type")] || "--concept"); },
        label: "data(label)", color: cssVar("--t1"), "font-size": 11, "font-weight": 600,
        "text-valign": "bottom", "text-halign": "center", "text-margin-y": 5,
        "text-wrap": "wrap", "text-max-width": 130,
        "text-background-color": cssVar("--canvas"), "text-background-opacity": 0.78,
        "text-background-padding": 3, "text-background-shape": "round-rectangle",
        width: 30, height: 30, "border-width": 2.5, "border-color": cssVar("--surface")
      } },
      { selector: "edge", style: {
        width: 1.6, "line-color": cssVar("--edge"), "target-arrow-color": cssVar("--edge"),
        "target-arrow-shape": "triangle", "curve-style": "bezier", label: "data(label)",
        "font-size": 8, color: cssVar("--t3"),
        // Libellés d'arêtes MASQUÉS au repos (text-opacity 0, pas la prop `label` : éviter
        // les recalculs de bounds) — révélés sur le nœud sélectionné (classe show-label).
        "text-opacity": 0,
        "text-background-color": cssVar("--canvas"), "text-background-opacity": 0.85,
        "text-background-padding": 2
      } },
      { selector: "edge.show-label", style: { "text-opacity": 1 } },
      { selector: ".selected", style: {
        "border-width": 4, "border-color": cssVar("--accent"), "border-opacity": 1
      } },
      { selector: ".dim", style: { opacity: 0.12 } }
    ];
  }

  var cy = cytoscape({
    container: document.getElementById("cy"),
    elements: buildElements(),
    style: styles(),
    wheelSensitivity: WHEEL_SENSITIVITY,
    minZoom: ZOOM_BOUND_MIN, maxZoom: ZOOM_BOUND_MAX
  });

  // ---- Expand/collapse des communautés ----
  var ec = null;
  if (typeof cy.expandCollapse === "function") {
    ec = cy.expandCollapse({ layoutBy: null, fisheye: false, animate: false, undoable: false });
  }

  // ---- Layouts ----
  var focusedId = null;
  var currentMode = "network";  // mode courant (persistance en mode réseau uniquement)

  function applyPositions(saved) {
    cy.batch(function () {
      cy.nodes().forEach(function (n) {
        var p = saved[n.id()];
        if (p) { n.position({ x: p.x, y: p.y }); }
      });
    });
    cy.fit(undefined, FIT_PADDING);
  }
  function savePositions() {
    if (!persistEnabled || currentMode !== "network") { return; }
    var map = {};
    cy.nodes().forEach(function (n) {
      var p = n.position(); map[n.id()] = { x: p.x, y: p.y };
    });
    store.write(STORAGE_KEY, map);
  }
  function layoutNetwork() {
    if (ec) { try { ec.expandAll(); } catch (e) { /* noop */ } }
    var saved = persistEnabled ? store.read(STORAGE_KEY) : null;
    if (saved) { applyPositions(saved); return; }  // restauration : pas de recalcul
    var name = window.cytoscapeFcose ? "fcose" : "cose";
    var lay = cy.layout({
      name: name, animate: false, quality: "default", padding: NETWORK_PADDING,
      // Réserve la place des LIBELLÉS pendant le calcul → bien moins de chevauchement.
      nodeDimensionsIncludeLabels: true,
      // packComponents exige l'extension layout-utilities (non vendorisée) → désactivé.
      packComponents: false,
      nodeRepulsion: function () { return FCOSE_NODE_REPULSION; },
      idealEdgeLength: function () { return FCOSE_IDEAL_EDGE_LENGTH; },
      nodeSeparation: FCOSE_NODE_SEPARATION,
      gravity: FCOSE_GRAVITY
    });
    // .run() n'est pas garanti synchrone → sauver sur layoutstop fige le 1er calcul
    // pour un rendu STABLE aux rechargements (fcose étant non-déterministe).
    if (persistEnabled) { lay.one("layoutstop", savePositions); }
    lay.run();
  }
  function layoutTree() {
    // Un nœud focalisé recentre l'arbre sur lui : seul `breadthfirst` honore
    // `roots` (le layout dagre ne supporte pas de racine unique). Sans focus,
    // dagre donne un arbre hiérarchique global plus lisible (repli breadthfirst).
    var opts;
    if (focusedId) {
      opts = { name: "breadthfirst", animate: false, directed: false, padding: NETWORK_PADDING, roots: [focusedId] };
    } else if (window.cytoscapeDagre) {
      opts = { name: "dagre", animate: false, rankDir: "TB", nodeSep: DAGRE_NODE_SEP, rankSep: DAGRE_RANK_SEP };
    } else {
      opts = { name: "breadthfirst", animate: false, directed: true, padding: NETWORK_PADDING };
    }
    cy.layout(opts).run();
    cy.fit(undefined, FIT_PADDING);
  }
  function setMode(mode) {
    currentMode = mode;
    var btnNetwork = document.getElementById("btn-network");
    var btnTree = document.getElementById("btn-tree");
    btnNetwork.classList.toggle("on", mode === "network");
    btnTree.classList.toggle("on", mode === "tree");
    btnNetwork.setAttribute("aria-pressed", mode === "network" ? "true" : "false");
    btnTree.setAttribute("aria-pressed", mode === "tree" ? "true" : "false");
    if (mode === "network") { focusedId = null; layoutNetwork(); } else { layoutTree(); }
  }

  // ---- Panneau latéral ----
  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function nodeData(id) { return DATA.nodes.find(function (n) { return n.id === id; }); }

  function relationsOf(id) {
    var rels = [];
    DATA.edges.forEach(function (e) {
      if (e.source === id) { rels.push({ id: e.target, type: e.type }); }
      else if (e.target === id) { rels.push({ id: e.source, type: e.type }); }
    });
    return rels;
  }

  function openPanel(id) {
    var n = nodeData(id);
    if (!n) { return; }
    var color = cssVar(TYPE_VAR[n.type] || "--concept");
    var html = '<div class="panel-head">';
    html += '<span class="badge"><span class="dot" style="background:' + color + '"></span>'
      + escapeHtml(TYPE_LABEL[n.type] || n.type) + "</span>";
    html += "<h2>" + escapeHtml(n.label) + "</h2>";
    if (n.chapterAnchor) { html += '<div class="sub">' + escapeHtml(n.chapterAnchor) + "</div>"; }
    html += "</div>";
    if (n.definition) {
      html += '<section><div class="lbl">' + escapeHtml(UI.definition || "Définition")
        + '</div><p class="def">' + escapeHtml(n.definition) + "</p></section>";
    }
    if (n.excerpts && n.excerpts.length) {
      html += '<section><div class="lbl">' + escapeHtml(UI.excerpt || "Extrait source") + "</div>";
      n.excerpts.forEach(function (ex) {
        html += '<blockquote class="quote">' + escapeHtml(ex.text);
        if (ex.chapter) { html += '<span class="src">§ ' + escapeHtml(ex.chapter) + "</span>"; }
        html += "</blockquote>";
      });
      html += "</section>";
    }
    var rels = relationsOf(id);
    if (rels.length) {
      html += '<section><div class="lbl">' + escapeHtml(UI.relations || "Relations")
        + '</div><div class="rel">';
      rels.slice(0, MAX_PANEL_RELATIONS).forEach(function (r) {
        var other = nodeData(r.id);
        if (!other) { return; }
        var oc = cssVar(TYPE_VAR[other.type] || "--concept");
        html += '<span class="relchip" data-id="' + escapeHtml(r.id) + '">'
          + '<span class="dot" style="background:' + oc + '"></span>'
          + escapeHtml(other.label) + " <small>· " + escapeHtml(EDGE_LABELS[r.type] || r.type)
          + "</small></span>";
      });
      html += "</div></section>";
    }
    html += '<button class="gobtn" id="btn-focus">'
      + escapeHtml(UI.focus || "Recentrer (mode arbre) →") + "</button>";
    var panel = document.getElementById("panel");
    panel.innerHTML = html;
    panel.classList.remove("hidden");
    document.getElementById("btn-focus").addEventListener("click", function () {
      focusedId = id; setMode("tree");
    });
    panel.querySelectorAll(".relchip").forEach(function (chip) {
      chip.addEventListener("click", function () { selectNode(chip.getAttribute("data-id")); });
    });
  }

  function selectNode(id) {
    cy.elements().removeClass("selected dim show-label");
    var node = cy.getElementById(id);
    if (node.empty()) { return; }
    var neighborhood = node.closedNeighborhood();
    cy.elements().not(neighborhood).addClass("dim");
    node.addClass("selected");
    node.connectedEdges().addClass("show-label");  // révèle les relations du nœud
    openPanel(id);
  }

  cy.on("tap", "node[kind != 'community']", function (evt) { selectNode(evt.target.id()); });
  cy.on("tap", function (evt) {
    if (evt.target === cy) {
      cy.elements().removeClass("selected dim show-label");
      document.getElementById("panel").classList.add("hidden");
    }
  });

  // ---- Recherche ----
  document.getElementById("search").addEventListener("input", function (e) {
    var q = e.target.value.trim().toLowerCase();
    cy.elements().removeClass("dim selected show-label");
    if (!q) { return; }
    var matches = cy.nodes("[kind != 'community']").filter(function (n) {
      return n.data("label").toLowerCase().indexOf(q) !== -1;
    });
    if (matches.length) {
      cy.elements().addClass("dim");
      matches.removeClass("dim").addClass("selected");
      cy.fit(matches, SEARCH_FIT_PADDING);
    }
  });

  // ---- Filtres par type ----
  function applyFilters() {
    var active = {};
    NODE_TYPES.forEach(function (t) {
      active[t] = !document.querySelector('.chip[data-type="' + t + '"]').classList.contains("off");
    });
    cy.nodes("[kind != 'community']").forEach(function (n) {
      n.style("display", active[n.data("type")] ? "element" : "none");
    });
  }
  document.querySelectorAll(".chip[data-type]").forEach(function (chip) {
    chip.addEventListener("click", function () { chip.classList.toggle("off"); applyFilters(); });
  });

  // ---- Barre d'outils ----
  document.getElementById("btn-network").addEventListener("click", function () { setMode("network"); });
  document.getElementById("btn-tree").addEventListener("click", function () { setMode("tree"); });
  document.getElementById("zoom-in").addEventListener("click", function () { cy.zoom(cy.zoom() * ZOOM_STEP); });
  document.getElementById("zoom-out").addEventListener("click", function () { cy.zoom(cy.zoom() / ZOOM_STEP); });
  document.getElementById("zoom-fit").addEventListener("click", function () { cy.fit(undefined, FIT_PADDING); });
  document.getElementById("theme").addEventListener("click", function () {
    var root = document.documentElement;
    root.setAttribute("data-theme", root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    cy.style(styles());
  });

  // ---- Persistance : sauvegarde au déplacement (débouncée) + réinitialisation ----
  var saveTimer = null;
  cy.on("dragfree", "node", function () {
    if (saveTimer) { clearTimeout(saveTimer); }
    saveTimer = setTimeout(savePositions, SAVE_DEBOUNCE_MS);
  });
  var resetBtn = document.getElementById("reset-layout");
  if (resetBtn) {
    if (!persistEnabled) { resetBtn.setAttribute("disabled", "disabled"); }
    resetBtn.addEventListener("click", function () {
      if (persistEnabled) { store.remove(STORAGE_KEY); }
      focusedId = null; setMode("network");  // relance fcose (branche « sans sauvegarde »)
    });
  }

  // ---- Démarrage ----
  layoutNetwork();
  window.__km = { cy: cy, select: selectNode, mode: setMode };  // hook (debug/automation)
  window.__kmReady = true;  // sentinelle pour la vérification automatisée (Playwright)
})();
