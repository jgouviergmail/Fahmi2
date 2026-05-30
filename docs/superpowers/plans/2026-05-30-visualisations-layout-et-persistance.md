# Plan — Visualisations : layout fcose lisible + persistance des réagencements

> Exécuté **inline**. Spec : `docs/superpowers/specs/2026-05-30-visualisations-layout-et-persistance-design.md`.

## Phases

- **Phase 1 — Layout carte (Volet A + C)** : ✅ **FAIT** (commit `feat(visuals): carte
  de connaissances — layout fcose lisible + désencombrement des arêtes`). fcose
  `nodeDimensionsIncludeLabels` + espacement (fonctions) + `packComponents:false` ;
  libellés d'arêtes masqués/révélés (`text-opacity`/`show-label`). Browser-vérifié.
  *(Correction : les diagrammes utilisent dagre/concentric, pas fcose → Volet A =
  carte uniquement.)*
- **Phase 2 — Persistance carte (Volet B)** : *détaillée ci-dessous.*
- **Phase 3 — Persistance diagrammes** : réutilise `_layout_store.js` ; déplacements
  manuels par diagramme (dagre déterministe → seul le manuel est à persister).
- **Phase 4 — Docs + correction spec + revue exhaustive finale.**

---

## Phase 2 — Persistance des positions de la carte (localStorage)

### Task 2.1 : Module partagé `_layout_store.js`

**Créer** `src/fahmi2/infra/export/_assets/visuals/_layout_store.js` :

```javascript
/* Persistance des positions de nœuds en localStorage (HTML autonome, file://).
   Bas niveau : sonde de disponibilité + read/write/remove, tout en try/catch
   (sous Safari/file://, navigation privée ou cookies bloqués, l'ACCÈS peut lever).
   L'intégration Cytoscape reste chez le consommateur. */
(function () {
  "use strict";
  function probe() {
    try {
      var k = "fahmi2:probe";
      window.localStorage.setItem(k, "1");
      window.localStorage.removeItem(k);
      return true;
    } catch (e) { return false; }
  }
  var AVAILABLE = probe();
  window.__fahmi2LayoutStore = {
    available: AVAILABLE,
    read: function (key) {
      if (!AVAILABLE) { return null; }
      try {
        var raw = window.localStorage.getItem(key);
        return raw ? JSON.parse(raw) : null;
      } catch (e) { return null; }
    },
    write: function (key, map) {
      if (!AVAILABLE) { return; }
      try { window.localStorage.setItem(key, JSON.stringify(map)); } catch (e) { /* quota/secu */ }
    },
    remove: function (key) {
      if (!AVAILABLE) { return; }
      try { window.localStorage.removeItem(key); } catch (e) { /* noop */ }
    }
  };
})();
```

- [ ] Écrire le fichier (le `.spec` le bundle déjà via `iterdir()` ; rien à patcher
  packaging).

### Task 2.2 : Renderer — clé de stockage + inline du store + libellé du bouton

**Modifier** `src/fahmi2/infra/export/knowledge_map_html.py` :

- [ ] Helpers (constantes + hash) :

```python
import hashlib

_LAYOUT_STORE_JS = "_layout_store.js"
_STORAGE_KEY_PREFIX = "fahmi2:visuals:knowledge_map"
_STORAGE_KEY_VERSION = "v1"
_NODES_HASH_LEN = 8


def _storage_key(graph: KnowledgeGraph) -> str:
    """Clé localStorage namespacée par livrable + langue + hash de structure.

    Le hash des ids de nœuds invalide les positions périmées après régénération ;
    le namespace évite les collisions sous file:// (bucket partagé).

    Args:
        graph: Graphe rendu.

    Returns:
        ``fahmi2:visuals:knowledge_map:<lang>:<hash8>:v1``.
    """
    joined = "\n".join(sorted(node.id for node in graph.nodes))
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:_NODES_HASH_LEN]
    return f"{_STORAGE_KEY_PREFIX}:{graph.language.value}:{digest}:{_STORAGE_KEY_VERSION}"
```

- [ ] Dans `render_knowledge_map_html`, injecter la clé dans le payload JSON (avant
  `json.dumps`) et ajouter les remplacements :

```python
    payload = _graph_to_json(graph, strings)
    payload["storageKey"] = _storage_key(graph)
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    ...
    "@@RESET_LAYOUT@@": strings.reset_layout,
    "@@LAYOUT_STORE@@": read_visuals_asset(_LAYOUT_STORE_JS),
```

- [ ] `_KmStrings` : ajouter `reset_layout: str` aux **5** langues (fr/en/de/es/it),
  ex. fr « Réinitialiser la disposition », en « Reset layout », de « Layout
  zurücksetzen », es « Restablecer disposición », it « Reimposta disposizione ».

### Task 2.3 : Template — bouton Réinitialiser + script du store

**Modifier** `knowledge_map.html.template` :

- [ ] Ajouter le bouton dans la toolbar (après le bouton thème, ligne 19) :

```html
    <button type="button" class="iconbtn" id="reset-layout" title="@@RESET_LAYOUT@@" aria-label="@@RESET_LAYOUT@@">⟲</button>
```

- [ ] Inliner le store **avant** l'app JS (après `@@VENDORED@@`) :

```html
@@VENDORED@@
<script>
@@LAYOUT_STORE@@
</script>
<script>
@@APP_JS@@
</script>
```

### Task 2.4 : `knowledge_map.js` — restauration / sauvegarde / reset

**Modifier** `knowledge_map.js` :

- [ ] Constantes + références :

```javascript
  var SAVE_DEBOUNCE_MS = 250;          // débounce de la sauvegarde au déplacement
  var STORAGE_KEY = DATA.storageKey || null;
  var store = window.__fahmi2LayoutStore || null;
  var persistEnabled = !!(store && store.available && STORAGE_KEY);
  var currentMode = "network";         // suit le mode (persistance réseau uniquement)
```

- [ ] `layoutNetwork()` : restaurer si positions sauvées, sinon fcose :

```javascript
  function persistedPositions() {
    return persistEnabled ? store.read(STORAGE_KEY) : null;
  }
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
    cy.nodes().forEach(function (n) { var p = n.position(); map[n.id()] = { x: p.x, y: p.y }; });
    store.write(STORAGE_KEY, map);
  }
```
  et dans `layoutNetwork()`, après `expandAll()` :

```javascript
    var saved = persistedPositions();
    if (saved) { applyPositions(saved); return; }
    var lay = cy.layout({ name: name, animate: false, ... });   // fcose existant
    // .run() n'est pas garanti synchrone → sauver sur layoutstop (fige le 1er calcul
    // pour un rendu STABLE aux rechargements ; fcose étant non-déterministe).
    if (persistEnabled) { lay.one("layoutstop", savePositions); }
    lay.run();
```

- [ ] `setMode` : maintenir `currentMode = mode;`.

- [ ] Sauvegarde au déplacement (débouncée), nœuds **et** communautés :

```javascript
  var saveTimer = null;
  cy.on("dragfree", "node", function () {
    if (saveTimer) { clearTimeout(saveTimer); }
    saveTimer = setTimeout(savePositions, SAVE_DEBOUNCE_MS);
  });
```

- [ ] Bouton Réinitialiser (neutralisé si persistance indisponible) :

```javascript
  var resetBtn = document.getElementById("reset-layout");
  if (resetBtn) {
    if (!persistEnabled) { resetBtn.setAttribute("disabled", "disabled"); }
    resetBtn.addEventListener("click", function () {
      if (persistEnabled) { store.remove(STORAGE_KEY); }
      focusedId = null; setMode("network");   // relance fcose (branche « pas de sauvegarde »)
    });
  }
```

### Task 2.5 : Tests renderer + vérification navigateur

- [ ] `tests/unit/infra/export/test_knowledge_map_html.py` : le HTML contient la clé
  (`fahmi2:visuals:knowledge_map:fr:` + 8 hex + `:v1`), le bouton `id="reset-layout"`,
  le module (`__fahmi2LayoutStore`) ; **deux graphes aux ids différents → hash
  différents** ; même graphe → hash stable.
- [ ] Vérification navigateur (Playwright HTTP, dev-only) : déplacer un nœud → `write`
  appelé ; **recharger** → positions **restaurées** (pas de fcose) ; « Réinitialiser »
  → clé effacée + recalcul ; sonde indisponible (stub) → bouton désactivé, rendu OK.
- [ ] `pytest` / `ruff` / `mypy --strict` verts.

### Fin de Phase 2 — Revue de code approfondie

Checklist complète (constantes centralisées, conformité patterns, Google docstrings
Python, nommage, DRY/SRP, repli gracieux, pas de régression) ×3 jusqu'à conviction.

---

## Phase 3 — Persistance diagrammes (esquisse, détaillée au démarrage)

Réutiliser `_layout_store.js` ; clé `fahmi2:visuals:diagram:<id>:<lang>:<hash>:v1` ;
`dragfree` save + restore au rendu de chaque carte ; le « Réinitialiser » du plein écran
efface aussi la clé. dagre déterministe → seul le manuel est persisté.

## Phase 4 — Docs + revue finale

CLAUDE.md / CHANGELOG / README / docs/02 (layout + persistance), **correction spec**
(Volet A = carte only), vérification navigateur récap, revue exhaustive de la branche.
