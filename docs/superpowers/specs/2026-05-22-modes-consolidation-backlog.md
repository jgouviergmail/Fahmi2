# Modes de consolidation (ordre intelligent / refonte thématique) — backlog à brainstormer (Spec B)

- **Date** : 2026-05-22
- **Statut** : **backlog — à brainstormer** (pas encore une spec validée)
- **Origine** : extrait de la discussion sur l'élargissement des entrants. Sorti
  de la Spec A (`2026-05-22-entrants-generation-elargis-design.md`) pour ne pas
  noyer une fonctionnalité ambitieuse dans une spec d'ingestion.
- **Prérequis** : Spec A livrée (sources multiples + ordonnancement). La
  consolidation reste en mode `ORDERED` (actuel) tant que la Spec B n'est pas faite.

## Intention utilisateur (déjà actée)

L'utilisateur veut **trois modes de consolidation au choix** :

| Mode | Ce que fait la phase 5 | Correspondance source ↔ chapitre |
|---|---|---|
| **`ORDERED`** (défaut, actuel) | Assemble le contenu reformulé dans l'ordre choisi | 1 source = 1 chapitre |
| **`SMART_ORDER`** | Le LLM choisit l'**ordre** des chapitres | 1 source = 1 chapitre |
| **`THEMATIC_MERGE`** | **Refonte thématique transversale** : regroupe par thème, fusionne, déduplique | structure thématique |

> Rappel de compréhension : le contenu est **déjà reformulé** (phase 3) et
> structuré (phase 4). La phase 5 ne « réécrit » pas — `THEMATIC_MERGE` ajoute une
> **couche de fusion/réorganisation transversale** par-dessus, ce qui fait perdre
> la correspondance 1 source = 1 chapitre.

## Piste d'architecture (à challenger)

- Enum `ConsolidationMode { ORDERED, SMART_ORDER, THEMATIC_MERGE }` ;
  `GenerationSettings.consolidation_mode` (défaut `ORDERED`).
- Phase 5 en **dispatcher de stratégies** ; sous-étape « résumés par source »
  (`phase_5_video_summary`) commune et inchangée.
- `SMART_ORDER` : + 1 appel LLM `phase_5_smart_order` renvoyant une permutation
  des `source_id`, repli déterministe si incohérent, puis réutilise l'assemblage
  actuel.
- `THEMATIC_MERGE` : **map-reduce** — plan thématique (`phase_5_thematic_plan`)
  puis rédaction par chapitre (`phase_5_thematic_chapter`, parallélisé), sommaire/
  numérotation déterministes réutilisés.

## Questions ouvertes à traiter au brainstorming (les vrais trous)

1. **Glossaire** : les phases 3/4 injectent des termes du glossaire. Comment la
   rédaction par chapitre thématique sélectionne/injecte les termes pertinents ?
2. **Checkpoint / reprise** : la phase 5 ne persiste qu'**un** `PhaseExecution`.
   Un map-reduce qui échoue au chapitre 8/10 recommence tout. Faut-il un
   checkpoint intra-phase (artefacts de plan + chapitres déjà rédigés) ? Impact
   sur `PipelineEngine` (qui est « phase par phase »).
3. **Coût** : quantifier le surcoût `THEMATIC_MERGE` (relecture des contenus
   structurés une fois par chapitre, sources possiblement relues plusieurs fois) ;
   adapter `_LOAD_FACTORS` par mode.
4. **Qualité / perte de contenu** : sur un grand nombre de sources, le plan peut
   condenser/omettre. Garde-fous ? Couverture (vérifier que chaque source est
   référencée au moins une fois) ?
5. **Documents non reformulés** : un document en pass-through (Spec A) serait
   **refondu** en `THEMATIC_MERGE` — contradiction avec l'intention « préserver un
   document déjà bien écrit ». Politique à définir (exclure du merge ? avertir ?).
6. **Interaction traduction (phase 6) / cohérence (phase 7)** : vérifier que le
   document thématique traverse l'aval sans hypothèse cassée.
7. **Valeur de `SMART_ORDER`** : pour un cours déjà numéroté, le LLM peut produire
   un ordre **pire** que celui de l'utilisateur. Confirmer la priorité / l'utilité.
8. **UI** : sélecteur de mode ; la liste « Ordre des sources » (Spec A) n'a d'effet
   qu'en `ORDERED` (grisée + note ailleurs).

## Fichiers pressentis (indicatif)
`domain/enums.py` (`ConsolidationMode`), `domain/generation.py`
(`consolidation_mode`), `pipeline/handlers/phase_5_consolidation.py` (dispatcher),
`pipeline/handlers/_consolidation/` (stratégies), 3 prompts
`infra/prompts/defaults/phase_5_*.j2`, `app/cost_estimator.py` (facteur par mode),
`app/prompts_service.py` (catalogue), UI réglages.
