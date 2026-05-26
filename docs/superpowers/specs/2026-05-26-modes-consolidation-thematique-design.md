# Mode de consolidation « Refonte thématique » — design

- **Date** : 2026-05-26
- **Statut** : **spec validée** (brainstorming terminé)
- **Origine** : réalise le mode `THEMATIC_MERGE` du backlog parqué
  `2026-05-22-modes-consolidation-backlog.md`. Le mode `SMART_ORDER` de ce backlog
  **reste hors périmètre** (ajoutable ultérieurement sans refonte grâce au
  dispatcher de stratégies).
- **Prérequis** : entrants multiples + ordonnancement (Spec A, livrée v1.1.0).

## 1. Intention

Aujourd'hui la phase 5 (consolidation) assemble les contenus structurés **dans
l'ordre choisi par l'utilisateur**, 1 source = 1 chapitre, le contenu étant
**recopié tel quel** (le LLM ne produit que les méta-éléments : titre, intro,
sommaire, conclusion). C'est le mode `ORDERED`.

On ajoute un mode **`THEMATIC` (refonte thématique transversale)** : le LLM
**agrège, agence et structure** l'ensemble des contenus des entrants pour produire
un document consolidé unique, à la manière d'un journaliste/étudiant qui fait une
synthèse à partir de plusieurs sources.

**Principe directeur — rigueur sur le fond, souplesse sur la forme :**

- **Fond (rigueur)** : interdiction d'inventer ou d'ajouter des faits ; tous les
  faits, chiffres, données et raisonnements des entrants doivent être préservés.
- **Forme (souplesse)** : le LLM décide la structure thématique, reformule,
  fusionne, déduplique, rédige les transitions.
- **Conflits entre sources** : le LLM **n'arbitre pas** ; il présente les écarts
  attribués à chaque source, voire en tire des réflexions.

Le mode est un **choix** (`GenerationSettings.consolidation_mode`), défaut
`ORDERED`. Tout le reste du pipeline (phases 0–4, 6, 7) est inchangé.

## 2. Modèle de données & dispatcher

### 2.1 Enum & réglage

- `domain/enums.py` : `class ConsolidationMode(StrEnum) { ORDERED = "ordered",
  THEMATIC = "thematic" }`.
- `domain/generation.py` : nouveau champ
  `GenerationSettings.consolidation_mode: ConsolidationMode = ConsolidationMode.ORDERED`.
- `infra/storage/sqlite_state.py` : sérialisation `"consolidation_mode":
  str(gen.consolidation_mode)` ; désérialisation *lenient*
  `ConsolidationMode(payload.get("consolidation_mode", ConsolidationMode.ORDERED))`.
  Les blobs existants (sans le champ) restent en `ORDERED` → **aucune rupture**.

### 2.2 Dispatcher de stratégies

La phase 5 devient un dispatcher. Nouveau package
`pipeline/handlers/_consolidation/` :

- `_base.py` — `ConsolidationStrategy` (ABC, méthode
  `consolidate(ctx, structured_by_source) -> ConsolidationResult`) **plus** les
  helpers déterministes **partagés**, extraits de l'actuel
  `phase_5_consolidation.py` : renumérotation `1 / 1.1 / 1.1.1`, construction du
  sommaire (`_build_toc_lines`), ancres GFM (`slugify_anchor`), assemblage
  méta + chapitres. Le **contrat de chapitre** (corps en `##`/`###`) est partagé.
  - `ConsolidationResult` (`@dataclass(frozen=True)`) : porte le **markdown
    consolidé** (`consolidated_markdown: str`) et le **coût cumulé**
    (`cost_usd: float`) de tous les appels LLM de la stratégie. Le dispatcher en
    tire l'écriture de `consolidated_master.md` et le `cost_usd` du
    `PhaseExecution` (le mode `ORDERED` somme ses 2 appels, le mode `THEMATIC`
    somme T1×sources + T2 + T3×chapitres + T4).
- `ordered.py` — `OrderedConsolidationStrategy` : comportement **actuel à
  l'identique** (résumé condensé par source via `phase_5_video_summary`, méta via
  `phase_5_consolidation`, contenu recopié, 1 source = 1 chapitre).
- `thematic.py` — `ThematicConsolidationStrategy` : nouvelle stratégie (§3).
- `phase_5_consolidation.py` — sélectionne la stratégie selon
  `ctx.settings.consolidation_mode`, exécute, persiste **un** `PhaseExecution`.

Ce découpage prépare `SMART_ORDER` (autre `ConsolidationStrategy`) sans toucher au
dispatcher ni au moteur.

## 3. Mode thématique : pipeline interne (map-reduce à provenance)

Modèle du journaliste : extraire des **notes fidèles** → les **agencer par
thème** → **rédiger** à partir des notes. La fidélité du fond circule via des
**identifiants traçables**.

### 3.1 T1 — Relevé factuel par source (LLM, parallélisé)

Pour chaque source (en parallèle, borné par `parallelism.llm_workers`), le LLM
extrait la **liste exhaustive des éléments à préserver** — au sens large : faits,
chiffres, données, **raisonnements/arguments**, affirmations.

> **Limite de passage à l'échelle (assumée, à surveiller au plan)** : un relevé
> *exhaustif + extraits verbatim* sur une source très longue peut approcher le
> plafond de tokens de sortie du LLM. Décision : T1 traite la source **entière**
> en un appel (le grand contexte DeepSeek couvre des cours typiques) ; si une
> source dépasse un seuil, le plan d'implémentation pourra ajouter un **découpage
> par section** (sur les `#`/`##` du structuré) avec concaténation du relevé —
> non implémenté d'emblée (YAGNI).

Chaque élément :

```json
{
  "id": "<source_id>#<NN>",
  "source_id": "<source_id>",
  "enonce": "<l'énoncé fidèle, reformulable>",
  "donnees": "<chiffres / données brutes, le cas échéant>",
  "type": "fait | chiffre | donnee | raisonnement | affirmation",
  "extrait_verbatim": "<extrait littéral de la source, vérité de terrain>"
}
```

- L'`id` est **stable** (préfixe `source_id`, compteur).
- `extrait_verbatim` est l'extrait **littéral** de la source d'où provient
  l'élément : c'est la **vérité de terrain** transmise à T3 (ferme le trou de
  fidélité du modèle « notes seules »).
- Prompt instruit d'être **exhaustif** : ne rien omettre du fond.

**Artefacts conservés** (sous `ctx.workspace/consolidation/`) :

- `facts_master.json` — tous les éléments, groupés par source.
- `facts.md` — **rendu lisible** (par source → liste d'éléments), pour
  consultation humaine.

### 3.2 T2 — Plan thématique transversal (1 appel LLM)

Reçoit **tous les éléments** sous forme compacte (`id` + `enonce`, groupés par
source) et produit le plan :

```json
{
  "global_title": "…",
  "chapters": [
    { "title": "…", "order": 1, "element_ids": ["s1#03", "s2#07", "…"] },
    "…"
  ]
}
```

- Un `id` peut apparaître dans **plusieurs** chapitres (élément transverse).
- **Directive de co-localisation des conflits** : les éléments traitant du
  **même point** (notamment ceux qui se **contredisent** entre sources) doivent
  être assignés au **même chapitre**, pour que la contradiction soit visible par
  un unique rédacteur en T3.
- **Contrôle déterministe n°1 (couverture du plan)** : `union(element_ids assignés)`
  doit égaler `{tous les ids extraits}`. Tout `id` **orphelin** est :
  1. journalisé (log + détails) ;
  2. **réinjecté** dans un chapitre de fin **« Éléments complémentaires »** — on
     évite de le rattacher au chapitre « le plus proche » (jugement non
     déterministe) ; ce filet garantit qu'**aucun élément ne peut disparaître**.
     Seul l'**assignement** est déterministe : ce chapitre **passe lui aussi par
     la rédaction T3** (prose synthétisée, comme les autres), il ne s'agit pas
     d'un dépotoir d'éléments bruts.

**Artefact conservé** : `thematic_plan.json`.

### 3.3 T3 — Rédaction par chapitre (map-reduce, parallélisé)

Pour chaque chapitre (en parallèle, borné par `parallelism.llm_workers`), le LLM
reçoit :

- ses **éléments assignés** (`enonce`, `donnees`, **`extrait_verbatim`**, `source_id`) ;
- *(optionnel)* le **glossaire** : les `extrait_verbatim` portent **déjà** la
  terminologie homogénéisée en phases 3/4, donc la réinjection n'a qu'un bénéfice
  marginal pour un surcoût réel. Décision : **ne pas injecter le glossaire en T3**
  par défaut (YAGNI) — réévaluable si la cohérence terminologique se dégrade ;
- les directives : utiliser **uniquement** le contenu fourni, **ne rien
  inventer**, préserver chiffres/données, **présenter les conflits par source**
  (« selon la source A… / la source B indique au contraire… ») **sans arbitrer**,
  fusionner/dédupliquer, rédiger les transitions.

Le chapitre renvoie : le **corps Markdown** (titres `##`/`###` selon le contrat)
**et** la liste des `element_ids` **réellement utilisés**.

- **Contrôle déterministe n°2 (couverture de la rédaction)** :
  `assignés ⊆ utilisés`. Tout `id` assigné mais non rendu est **journalisé et
  signalé** (l'élément reste traçable dans `facts.md` ; l'utilisateur est averti
  via les logs).

**Artefacts conservés** : `chapters/<order>.md`.

### 3.4 T4 — Méta + assemblage déterministe

- Méta-éléments (titre global, introduction, conclusion) via un appel type
  `phase_5_consolidation` (réutilisé), nourri par le plan thématique.
- Assemblage final avec **sommaire et numérotation déterministes** réutilisés de
  `_base.py` (`slugify_anchor`, renumérotation hiérarchique) → produit
  `consolidated_master.md`, **de même nature** que le document du mode `ORDERED`.

## 4. Garanties de fidélité (récapitulatif)

| Risque | Garde-fou |
|---|---|
| Perte d'un élément **après** extraction | Contrôles déterministes d'ids n°1 (plan) et n°2 (rédaction) |
| Perte de nuance **pendant** la rédaction | `extrait_verbatim` transmis comme vérité de terrain en T3 |
| Élément orphelin (non planifié) | Chapitre déterministe « Éléments complémentaires » |
| Conflit entre sources noyé | Co-localisation en T2 + présentation par source en T3 (sans arbitrage) — *best-effort, dépend du prompt T2 ; risque résiduel assumé* |
| Hallucination / ajout de faits | Directive stricte « uniquement le contenu fourni » en T3 |

> Limite assumée : l'**exhaustivité de l'extraction T1** repose sur le LLM (le
> prompt l'exige) ; les `extrait_verbatim` la rendent vérifiable a posteriori via
> `facts.md`. Aucune passe de vérification LLM globale (jugée moins fiable et plus
> coûteuse que les contrôles déterministes d'ids).

## 5. Checkpoint / reprise (sans toucher `PipelineEngine`)

Le moteur reste « phase par phase » : la phase 5 persiste **un**
`PhaseExecution`. Pour ne pas tout recalculer si T3 échoue à mi-parcours, la
stratégie thématique **écrit ses artefacts intermédiaires** (`facts_master.json`,
`thematic_plan.json`, `chapters/<n>.md`) et, lors d'une **reprise** (phase 5
ré-exécutée car le Run est `FAILED`), **saute les artefacts déjà frais**.

La fraîcheur est gardée par un **hash de cohérence** (réglages pertinents +
empreinte des sources), sur le modèle du `pedagogy/manifest.json`. Un hash qui ne
correspond plus invalide les artefacts (recalcul). **Aucun changement de schéma
SQLite ni du moteur.**

> Limite assumée : le hash **ne couvre pas** une modification d'**override de
> prompt** (`%APPDATA%/Fahmi2/prompts/*.j2`) entre deux runs — des artefacts
> intermédiaires pourraient être réutilisés avec l'ancien prompt. Cas marginal
> (reprise après échec, pas réédition de prompt) ; à documenter, non traité.

## 6. Coût

`CostEstimator.estimate` reçoit `consolidation_mode`. En `THEMATIC`, le coût de la
phase 5 est calculé avec un **jeu de facteurs dédié** (`_LOAD_FACTORS` ou branche
spécifique) couvrant : T1 (par source) + T2 (plan, sur le volume des énoncés) + T3
(somme par chapitre, fonction du nombre de chapitres et des extraits) + T4 (méta).
Reste **heuristique** (ordre de grandeur).

> **Précision (vérifiée dans le code)** : le **pipeline de génération n'applique
> aucun plafond de coût à l'exécution** — `cost_ceiling_usd` n'est utilisé que par
> le `CostEstimator` **pré-run** et son affichage UI (aucune référence à
> `cost_ceiling` dans `pipeline/`). L'enforcement runtime n'existe que pour la
> **pédagogie** (`SupportsOrchestrator`). Le mode `THEMATIC` ne change donc
> **que l'estimation** ; on **n'ajoute pas** d'enforcement runtime (hors
> périmètre). Conséquence à assumer : le surcoût thématique réel n'est pas borné
> en cours d'exécution, seulement estimé avant lancement.

## 7. Aval — phases 6/7 (vérifié, inchangé)

- Phase 6 (traduction) traduit `consolidated_master.md` **comme un tout** et copie
  les artefacts par source (toujours produits par la phase 4, inchangée).
- Phase 7 (cohérence) opère par langue sur le consolidé.
- **Aucune hypothèse « 1 source = 1 chapitre » en aval** → rien à modifier.
  Couvert par un **test de non-régression**.

## 8. UI & réglages

- **Sélecteur de mode de consolidation** (Ordonné / Refonte thématique) dans
  `ui/dialogs/generation_settings_view.py`, avec une aide expliquant le compromis
  fidélité/synthèse.
- `ui/widgets/source_order_view.py` : l'**inclusion/exclusion** reste pertinente
  en thématique, mais **l'ordre n'a plus d'effet** → **note d'information**
  affichée quand le mode est thématique (le widget reste fonctionnel pour
  l'exclusion).

## 9. Prompts & catalogue

Trois nouveaux templates dans `infra/prompts/defaults/` (éditables/overridables
comme les autres, enregistrés au catalogue `app/prompts_service.py`) :

- `phase_5_fact_ledger` (T1)
- `phase_5_thematic_plan` (T2)
- `phase_5_thematic_chapter` (T3)

T4 réutilise `phase_5_consolidation`. `phase_5_video_summary` reste utilisé par le
mode `ORDERED`.

## 10. Constantes

Pas de magic value : sous-dossier `consolidation/`, noms de fichiers
(`facts_master.json`, `facts.md`, `thematic_plan.json`, `chapters/`), libellé du
chapitre « Éléments complémentaires », noms de templates → **constantes**
centralisées (module de la stratégie thématique / `generation.py` selon la portée).

## 11. Tests

- **Stratégie thématique** (`FakeLLMProvider`) : contrôle de couverture n°1
  (plan), réinjection d'un id orphelin → « Éléments complémentaires », contrôle
  n°2 (rédaction), présentation d'un conflit (deux sources, énoncés opposés dans
  un même chapitre), transmission des `extrait_verbatim`, reprise *coarse*
  (artefact frais sauté via hash).
- **Helpers déterministes partagés** : tests existants conservés (non-régression
  `ORDERED`, TOC/numérotation/ancres).
- **(Dé)sérialisation** `consolidation_mode` + migration d'un blob sans le champ.
- **Coût** `THEMATIC` (facteurs dédiés).
- **Aval** : non-régression phases 6/7 sur un consolidé thématique.
- **UI** : smoke test du sélecteur ; note d'ordre grisée en thématique.
- **Vérifications finales obligatoires** : `pytest`, `ruff check .`,
  `mypy src tests` tous au vert.

## 12. Fichiers (indicatif)

- `domain/enums.py` (`ConsolidationMode`)
- `domain/generation.py` (`consolidation_mode`, constantes)
- `infra/storage/sqlite_state.py` ((dé)sérialisation lenient)
- `pipeline/handlers/phase_5_consolidation.py` (dispatcher)
- `pipeline/handlers/_consolidation/{_base,ordered,thematic}.py` (stratégies)
- `infra/prompts/defaults/phase_5_{fact_ledger,thematic_plan,thematic_chapter}.j2`
- `app/prompts_service.py` (catalogue)
- `app/cost_estimator.py` (facteur par mode)
- `ui/dialogs/generation_settings_view.py` (sélecteur)
- `ui/widgets/source_order_view.py` (note d'ordre sans effet en thématique)
- `tests/` (unitaires stratégie, sérialisation, coût, aval, UI)

## 13. Hors périmètre (YAGNI)

- Mode `SMART_ORDER` (réordonnancement sans fusion) — reste parqué.
- Passe de vérification LLM globale — remplacée par les contrôles déterministes.
- Mode hybride « pass-through dans la refonte » — en thématique, **tout entrant
  est matière première** ; le drapeau `reformulate_documents` n'a pas d'effet sur
  le mode thématique.
- Export dédié du relevé factuel — `facts.md`/`facts_master.json` restent sur
  disque (consultables), pas d'export documentaire supplémentaire pour l'instant.
