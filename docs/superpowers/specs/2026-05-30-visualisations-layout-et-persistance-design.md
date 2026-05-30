# Visualisations — mise en page optimale + persistance des réagencements

**Date** : 2026-05-30
**Statut** : conception validée (brainstorming + validation multi-agents sur sources), prêt pour le plan
**Périmètre** : rendu HTML des Visualisations (carte de connaissances + galerie de diagrammes). Aucun impact domaine / pipeline / orchestrateur.

## 1. Contexte et problèmes

Deux retours utilisateur sur les livrables HTML autonomes (ouverts en double-clic, donc
`file://`, sans serveur ni réseau ; rendu **Cytoscape.js** vendorisé inliné, zéro CDN) :

1. **Le positionnement initial des nœuds est sous-optimal** : les **libellés de nœuds**
   se chevauchent et les **libellés d'arêtes** encombrent (cf. capture). Peut-on
   s'appuyer sur de meilleurs algorithmes/réglages ?
2. **On perd la mise en page au refresh** : si l'utilisateur déplace des nœuds puis
   recharge, l'agencement est recalculé. Peut-on **sauvegarder les réagencements** et
   **revenir à la disposition initiale** au besoin ?

## 2. Décisions validées (brainstorming + recherche)

| Sujet | Décision |
|-------|----------|
| Qualité de layout | **Régler fcose à fond** — aucune nouvelle bibliothèque vendorisée |
| Persistance | **localStorage** + bouton « Réinitialiser la disposition » |
| Périmètre | **Carte de connaissances + galerie de diagrammes** |
| Safari/macOS (`file://`) | **Repli auto** (recalcul) + **limite documentée** (pas d'export/import JSON) |

**Validation multi-agents (sources : code vendorisé fcose, doc Cytoscape, MDN/WHATWG)** —
7 corrections intégrées (cf. §4-6). Verdict : approche confirmée faisable, avec les
ajustements ci-dessous.

## 3. Objectifs / non-objectifs

**Objectifs**
- Réduire nettement le **chevauchement des libellés** (nœuds **et** arêtes) à l'ouverture.
- Permettre de **sauvegarder** un réagencement manuel (persistant entre rechargements)
  et de **réinitialiser** vers la disposition calculée.

**Non-objectifs**
- Aucune nouvelle bibliothèque de layout vendorisée (pas de cola/ELK/layout-utilities).
- Pas d'export/import de fichier de disposition (repli auto sous Safari suffit pour v1).
- Pas de reproductibilité stricte du **tout premier** rendu (fcose n'est pas seedable —
  cf. §4.3) ; la stabilité inter-rechargements vient de la **persistance**, pas de fcose.

## 4. Volet A — réglage fcose (libellés de **nœuds**)

Cible : **`knowledge_map.js` (réseau) uniquement**. *(Correction post-implémentation : la
galerie de diagrammes utilise `dagre`/`concentric`/`breadthfirst` — pas fcose — et est
déterministe ; le Volet A ne s'y applique donc pas. Sa lisibilité relève de la hauteur
adaptative + plein écran déjà livrés.)*

### 4.1 `nodeDimensionsIncludeLabels`

- Activer **`nodeDimensionsIncludeLabels: true`** en **conservant `quality: "default"`**.
  Vérifié dans le source vendorisé (`cytoscape-fcose.js`) : la lecture de l'option **n'est
  pas conditionnée par `quality`** (le « Valid in proof quality » du README est obsolète).
  fcose réserve alors la place des libellés (mesure `boundingBox({includeLabels:true})`)
  pendant le calcul → moins de chevauchement des **libellés de nœuds**. Gère aussi les
  **nœuds composés** (communautés = parents : positionnés/dimensionnés autour de leurs
  enfants, libellé du parent inclus).

### 4.2 Espacement (constantes centralisées)

- **`nodeRepulsion` et `idealEdgeLength` doivent être des FONCTIONS**, pas des scalaires
  (sinon **ignorés** — vérifié source) : `nodeRepulsion: () => FCOSE_NODE_REPULSION`,
  `idealEdgeLength: () => FCOSE_IDEAL_EDGE_LENGTH`. Valeurs > défauts (4500 / 50) pour
  aérer (cible ~6000 / ~90, **ajustées à la vérification navigateur**).
- `nodeSeparation: FCOSE_NODE_SEPARATION` (défaut 75) et `gravity: FCOSE_GRAVITY`
  (défaut 0.25, garder modéré) — scalaires.
- **Retirer toute dépendance à `packComponents`** : il exige l'extension
  `cytoscape-layout-utilities` **non vendorisée** (et `randomize:true`) → inopérant ici.
  Le poser explicitement `packComponents: false` (évite un éventuel avertissement console).
- Conserver `animate: false` (déjà en place) et `padding: NETWORK_PADDING`.
- Toutes ces valeurs en **constantes** en tête de fichier (directive « pas de nombre
  magique »).

### 4.3 Déterminisme (assumé, documenté)

fcose est **non-déterministe** (`randomize: true`, `Math.random` dans le layout spectral,
**aucune graine**). `randomize:false` depuis des positions nulles donne un layout
**dégénéré** → à proscrire. Architecture retenue :
1. **1er rendu sans positions sauvegardées** → fcose `randomize:true` (qualité).
2. Sauvegarde des positions (Volet B).
3. **Rechargements avec positions** → **restauration** (preset/`node.position`), **sans
   relancer fcose**.
4. « Réinitialiser » → efface la clé + relance fcose (`randomize:true`) ; la nouvelle
   disposition diffère (sans incidence, aussitôt re-sauvée).

La reproductibilité inter-rechargements est donc assurée par **localStorage**, pas par
fcose. Le **contenu/structure** du livrable reste déterministe (côté serveur) ; la
**disposition** est une préoccupation de vue.

## 5. Volet C — désencombrement des libellés d'**arêtes** (style, ≠ fcose)

fcose n'a **aucune** option pour les libellés d'arêtes : c'est 100 % du **style
Cytoscape**. Cible : `knowledge_map.js` (et diagrammes-graphes si pertinent).

> **Implémentation retenue** : le levier **primaire** est `min-zoomed-font-size`
> (gating au zoom), **pas** `text-opacity`. La conception initiale ci-dessous prévoyait
> `text-opacity: 0/1` ; à l'implémentation, `min-zoomed-font-size` s'est avéré suffisant
> et plus simple (un seul mécanisme, sans seconde propriété d'opacité à entretenir). La
> description ci-dessous est conservée mais corrigée pour refléter le code livré.

- **Masquer en vue d'ensemble** via `min-zoomed-font-size: EDGE_LABEL_MIN_ZOOM_FONT`
  (ex. 8) sur le sélecteur `edge` : sous ce seuil de zoom effectif, Cytoscape n'affiche
  pas le libellé (PAS de bascule de la propriété `label` : la basculer recalcule
  bounds + z-order à chaque survol → saccadé sur ~400 arêtes). En zoomant assez, les
  libellés réapparaissent **automatiquement** (zéro JS).
- **Révéler au survol/sélection** : sur un nœud, `node.connectedEdges().addClass(
  "show-label")` ; retrait au désurvol. Le sélecteur `edge.show-label` lève la grille de
  zoom (`min-zoomed-font-size: 0`) → libellés visibles même dézoomé. Écouter
  **`tapdragover` / `tapdragout`** (normalisés souris+tactile, plus robustes que
  `mouseover`/`mouseout`) + la mécanique `tap`/classe **déjà en place** pour la
  sélection. Envelopper retrait global + ajout local dans **`cy.batch(...)`** (un seul
  redraw).
- Aucune relance de layout dans les handlers de survol (repaint de style uniquement).
- Constantes (seuil `EDGE_LABEL_MIN_ZOOM_FONT`, nom de classe `show-label`) centralisées.

## 6. Volet B — persistance des positions (localStorage)

### 6.1 Module partagé `_layout_store.js`

Nouveau fichier vendorisé (inliné avant le JS applicatif). **Bas niveau localStorage**
uniquement (l'intégration Cytoscape reste chez chaque consommateur) :

```
window.__fahmi2LayoutStore = {
  available: <bool>,            // sonde au démarrage
  read(key)  -> {id:{x,y}}|null,
  write(key, map) -> void,      // try/catch silencieux
  remove(key) -> void,
}
```

- **Sonde de disponibilité** au chargement : `try { setItem(probe); removeItem(probe);
  available=true } catch { available=false }`. Tout accès enveloppé `try/catch` (sous
  Safari `file://`, navigation privée ou cookies bloqués, **l'accès lui-même peut lever**
  — MDN : comportement `file://` « undefined »).
- Si `available === false` → persistance désactivée silencieusement ; le bouton
  « Réinitialiser la disposition » est **neutralisé** (caché/désactivé).

### 6.2 Clé de stockage (renderers Python)

Sous `file://`, le bucket localStorage est **partagé** (Chrome/Edge : un seul pour tous
les fichiers ; Firefox : par dossier) → **clé namespacée obligatoire**, embarquée au
rendu :

```
fahmi2:visuals:<deliverable>:<lang>:<structHash8>:v1
```

- `<deliverable>` : `knowledge_map` ou `diagram:<diagramId>`.
- `<structHash8>` : 8 hex d'un hash des **ids de nœuds triés** (calculé en Python par le
  renderer) → **invalide les positions périmées** après régénération (cohérent avec la
  fraîcheur du manifest). Déplacer/renommer le fichier HTML change l'origine `file://`
  → perte des positions (limite intrinsèque documentée).
- `:v1` : version de schéma (invalidation propre si le format change).

### 6.3 Intégration Cytoscape (consommateurs)

- **Sauvegarde** : `cy.on("dragfree", "node", handler)` (PAS `free` — déclenche sans
  déplacement ; PAS `position` — déclenche pendant layout/restauration → boucles).
  Handler **débouncé** (~200 ms) : sérialise les positions de **tous** les nœuds (y
  compris communautés/parents) → `write(key, map)`. Carte : sauver **seulement en mode
  réseau** (`currentMode === "network"`).
- **Restauration** (`layoutNetwork`) : si `read(key)` non nul → `cy.batch(() =>
  cy.nodes().forEach(n => { const p = saved[n.id()]; if (p) n.position(p); }))` puis
  `cy.fit(undefined, FIT_PADDING)`, **sans relancer fcose**. Sinon → fcose (1er rendu)
  puis sauvegarde du résultat. **Restaurer après `ec.expandAll()`** (état déplié = tous
  les nœuds présents ; ordre déjà en place). **Ne pas** persister l'état repli/dépli
  (toujours démarrer déplié).
- **Mode arbre** (`layoutTree`, dagre) : **jamais** persisté (recalculé à chaque bascule).
- **Bouton « Réinitialiser la disposition »** : `remove(key)` + relance fcose
  (`layoutNetwork` branche « pas de sauvegarde »). Distinct du `relayoutLightbox` existant
  (overlay éphémère, sans localStorage).
- **Galerie de diagrammes** : positions persistées **par diagramme** (clé
  `diagram:<id>`), sauvées sur `dragfree` dans la carte **et** le plein écran (même clé),
  restaurées au rendu. Le bouton « Réinitialiser » du plein écran **efface aussi la clé**.

## 7. Fichiers touchés

**Créés**
- `src/fahmi2/infra/export/_assets/visuals/_layout_store.js` — module localStorage partagé.

**Modifiés**
- `_assets/visuals/knowledge_map.js` — fcose (Volet A), arêtes (Volet C), persistance
  (Volet B : restore/save/reset, mode réseau).
- `_assets/visuals/diagram_board.js` — fcose (Volet A) sur diagrammes-graphes, persistance
  par diagramme (carte + plein écran), reset.
- `_assets/visuals/knowledge_map.html.template` — bouton « Réinitialiser la disposition ».
- `_assets/visuals/diagram_board.html.template` — (le plein écran a déjà un reset ; étendre
  à l'effacement de clé).
- `infra/export/knowledge_map_html.py` / `diagram_board_html.py` — calcul du `structHash8`,
  injection de la clé de stockage + libellé du bouton, inline de `_layout_store.js` avant
  le JS applicatif.
- `infra/export/_visuals_assets.py` — exposer/inliner `_layout_store.js` (au besoin).
- CSS visuals — style `.show-label`, bouton reset, état neutralisé.

Le `.spec` bundle déjà `_assets/visuals/*` par `iterdir()` → **rien à patcher** côté
packaging (le nouveau `.js` est auto-inclus).

## 8. Tests

- **Renderers (unitaires Python)** : le HTML produit contient la **clé de stockage**
  attendue (namespace + langue + hash + v1), le **bouton Réinitialiser**, et le JS
  `_layout_store.js` **inliné** ; le hash change si les ids de nœuds changent.
- **Navigateur (Playwright, dev-only, non packagé)** — servi en HTTP (file:// bloqué dans
  l'outil) :
  - Volet A/C : moins de chevauchement qu'avant (comparaison visuelle), libellés d'arêtes
    masqués au repos et révélés au survol/zoom.
  - Volet B : déplacer un nœud → `write` appelé ; recharger (re-`init`) → positions
    **restaurées** (pas de fcose) ; « Réinitialiser » → clé effacée + recalcul ; sonde
    indisponible simulée → bouton neutralisé, rendu OK.
- **Limite** : le comportement réel `file://` (bucket partagé, Safari bloqué) n'est pas
  testable dans l'outil (file:// bloqué) — couvert par la recherche documentaire et le
  repli gracieux ; vérification HTTP pour la logique.

## 9. Limites assumées (documentées)

- **Safari/macOS en `file://`** : localStorage **bloqué** → persistance inopérante
  (repli : recalcul fcose à chaque ouverture, bouton Réinitialiser neutralisé). Documenté
  comme l'exclusion CJK/RTL. Utilisateurs cibles = **Windows** (Chrome/Edge/Firefox) → OK.
- **Déplacer/renommer le fichier HTML** → nouvelle origine `file://` → positions perdues.
- **Premier rendu non reproductible** (fcose non seedable) — sans incidence (la
  disposition est une vue ; le contenu reste déterministe).
- **Navigation privée / réglages stricts** → localStorage volatil/absent → repli gracieux.

## 10. Risques / points ouverts

- **Valeurs fcose** (répulsion / longueur d'arête / séparation) : à **calibrer à la
  vérification navigateur** sur le vrai graphe (388 nœuds) ; constantes ajustables.
- **`nodeDimensionsIncludeLabels` en `quality:"default"`** : effet attendu plein (source),
  mais si le désencombrement reste partiel, **option de repli** : passer le **1er** calcul
  fcose en `quality:"proof"` (coût CPU one-shot) — à décider à la vérification.
- **Persistance du plein écran des diagrammes** : partage de clé carte↔overlay — à valider
  ergonomiquement (sinon limiter la persistance à la carte de connaissances en v1).
