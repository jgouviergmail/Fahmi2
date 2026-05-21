# Parallélisation des traitements (génération + pédagogie) — design détaillé

- **Date** : 2026-05-21
- **Statut** : design (à valider)
- **Portée** : moteur de génération (`pipeline/`), orchestrateur pédagogie
  (`app/supports_orchestrator.py`), couche transverse (`core/`), réglages
  (`domain/`) et exposition UI (réglages « Avancé »).
- **Objectif** : réduire le délai de traitement en exécutant en parallèle les
  unités de travail indépendantes (appels LLM et STT cloud, I/O-bound), sans
  réécrire les moteurs et en restant extensible à l'ajout/retrait de phases du
  pipeline et de livrables pédagogiques.

## 1. Objectif & portée

Aujourd'hui tout est strictement séquentiel : une vidéo après l'autre, un
support après l'autre, dans un unique `QThread` worker. Les appels LLM
(DeepSeek) et STT cloud (OpenAI) sont **I/O-bound** : ils passent l'essentiel de
leur temps à attendre le réseau, donc un pool de threads borné libère le GIL
pendant l'attente et délivre un gain réel **sans** multiprocessing.

Ce design introduit **un seul primitif de concurrence borné**, partagé par les
deux moteurs, et remplace les boucles `for` séquentielles par des appels à ce
primitif. La déclaration de ce qui est parallélisable reste **locale** au
composant concerné (handler de phase, orchestrateur pédagogie), jamais
centralisée dans un planificateur global.

**Hors périmètre** : STT local (faster-whisper, 1 GPU partagé → séquentiel
imposé) ; tout changement du format des artefacts ou du checkpoint SQLite ;
le streaming des réponses LLM.

## 2. Constat de départ

- **Exécution 100 % séquentielle** : `PipelineEngine.execute` itère les phases,
  puis `_execute_phase` itère les vidéos en série
  (`pipeline/engine.py`). `SupportsOrchestrator.generate` itère
  `langues × supports` en série, et chaque générateur par chapitre itère ses
  chapitres en série (`pedagogy/generators/_base.py`).
- **Une configuration de parallélisme « morte »** : `ParallelismConfig`
  (`stt_cloud_workers=3`, `llm_workers=4`) existe dans `GenerationSettings`,
  est **persistée et relue** en SQLite (`infra/storage/sqlite_state.py`), mais
  n'est **jamais lue par le moteur** et n'est **pas exposée** dans l'UI
  (`generation_settings_view.py` fige `parallelism=ParallelismConfig()`). La
  conception d'origine (`2026-05-19-fahmi2-design.md` §5.4) prévoyait pourtant
  la parallélisation. Ce design la réalise enfin.

## 3. Décisions verrouillées

1. **Abstraction = executor borné + déclaration légère** (pas de scheduler DAG :
   le graphe est quasi linéaire avec 2 barrières naturelles, un DAG paierait une
   complexité permanente injustifiée).
2. **Ordre de livraison : pédagogie d'abord, puis pipeline** (la pédagogie n'a
   aucune barrière → meilleur ratio gain/risque ; on valide le primitif dessus).
3. **Réglages : auto par défaut, ajustables en « Avancé »**.
   `llm_workers = 16` par défaut (réglable jusqu'à 64) ; `stt_cloud_workers = 3`
   (inchangé). Effectif auto-borné à `min(workers, nb d'unités)`.
4. **Plafond de coût : léger dépassement toléré** (les requêtes en vol au
   franchissement du plafond vont au bout).
5. **Timeout client DeepSeek explicite (~600 s)** pour absorber les requêtes
   lentes sous charge (DeepSeek garde la connexion ouverte par keep-alive).

### 3.1 Note sur les limites de débit des fournisseurs

- **DeepSeek** : la limite est par **concurrence** (500 connexions pour
  `deepseek-v4-pro`, 2 500 pour `deepseek-v4-flash`), sans plafond RPM/TPM. Avec
  `llm_workers = 16` on est 2 à 3 ordres de grandeur sous la limite → `429`
  quasi impossible. Le retry exponentiel **avec jitter** déjà en place
  (`core/retry/policy.py`, `jitter=True`) suffit largement.
- **OpenAI Whisper (STT cloud)** : vraies limites **RPM par palier de compte** →
  `stt_cloud_workers` reste **modeste (3)** pour ne pas déclencher de vrais
  `429` sur le STT.

## 4. Architecture — le primitif `map_bounded`

Nouveau module pur dans la couche transverse : `core/concurrency/_executor.py`
(n'importe ni Qt, ni HTTP, ni SQL — conforme aux règles de couches).

```python
def map_bounded(
    fn: Callable[[T], R],
    items: Sequence[T],
    *,
    max_workers: int,
    pause_token: PauseToken | None = None,
) -> list[R]:
    """Exécute fn(item) au plus max_workers à la fois, ordre des résultats
    préservé. Fail-fast. Honore le PauseToken entre soumissions."""
```

Sémantique précise :

- **Borné** par `max_workers` (`ThreadPoolExecutor`). `max_workers=1` ⇒
  exécution strictement séquentielle (chemin équivalent à la boucle `for`
  actuelle) : c'est l'interrupteur universel pour les tests et le débogage.
- **Ordre préservé** : les résultats reviennent dans l'ordre des `items`, quel
  que soit l'ordre de complétion.
- **Fail-fast** : à la première exception, on cesse de soumettre, on annule les
  tâches **non démarrées** (`Future.cancel()` / `shutdown(cancel_futures=True)`),
  on laisse finir celles **déjà démarrées** (un appel LLM en cours n'est pas
  interruptible), puis on relève l'exception.
- **Pause/annulation** : `map_bounded` consulte le `PauseToken` **avant chaque
  soumission** — `wait_if_paused()` (bloque) puis `raise_if_cancelled()` (lève
  `PausedError`). Les tâches en vol terminent ; aucune nouvelle n'est soumise.

**Simplification clé** : côté pédagogie, `_run_one` **capture déjà** les
`Fahmi2Error` et renvoie `(cost, failed)` sans lever
(`supports_orchestrator.py`). Le mode *fail-fast* unique ne se déclenche donc
jamais pour la pédagogie → on obtient le comportement *best-effort* (un support
échoue, les autres continuent) **gratuitement**, sans second mode d'erreur dans
le primitif.

## 5. Pipeline — déclaration légère + câblage moteur

Le `PhaseHandler` gagne **une seule méthode**, avec un défaut sûr :

```python
class PhaseHandler(ABC):
    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        """Workers pour paralléliser les unités per-video. Défaut : 1 (séquentiel)."""
        return 1
```

- **Phase 0 STT** surcharge : `parallelism.stt_cloud_workers` si le provider est
  cloud, **sinon 1** (1 GPU local → séquentiel imposé).
- **Phases 1, 3, 4** (LLM per-video) surchargent : `parallelism.llm_workers`.
- Toute autre phase hérite du défaut `1`.

Le moteur (`pipeline/engine.py`, `_execute_phase`) devient :

```python
if handler.is_per_video:
    workers = handler.max_parallel_workers(ctx)
    map_bounded(
        lambda v: self._execute_one(handler, ctx, video=v),
        ctx.run.videos,
        max_workers=workers,
        pause_token=ctx.pause_token,
    )
else:
    self._execute_one(handler, ctx, video=None)
```

Les **barrières** (phases 2 et 5, batch) sont préservées **naturellement** : le
moteur reste « phase par phase » et ne démarre la phase suivante qu'une fois
toutes les unités de la phase courante terminées. Le checkpoint SQLite par
`(phase, vidéo)` reste valide : chaque thread persiste une ligne distincte (pas
de conflit de clé `UNIQUE`).

## 6. Phases batch — parallélisme interne (5, 6, 7)

Ces phases ne bouclent pas sur les vidéos au niveau moteur ; elles bouclent **en
interne** et utilisent `map_bounded` *dans* leur handler, avec
`ctx.settings.parallelism.llm_workers` :

- **Phase 6 Traduction** : aplatir `langues × {docs per-video, consolidé,
  glossaire}` (toutes unités indépendantes) → `map_bounded`. Plus gros gisement
  (souvent `L × (N + 2)` unités).
- **Phase 7 Cohérence** : `map_bounded` sur les langues.
- **Phase 5 Consolidation** (optionnel, cf. §10) : `map_bounded` sur les
  `_summarize_video` (indépendants), puis l'appel meta final séquentiel
  (barrière interne). L'assemblage relit déjà les fichiers dans l'ordre des
  vidéos → déterminisme du document préservé.

**Garantie anti-explosion de threads** : le moteur ne parallélise qu'une phase à
la fois et chaque phase borne son propre pool à `llm_workers` ⇒ jamais de pools
imbriqués, au plus `llm_workers` appels concurrents à tout instant.

## 7. Pédagogie — aplatissement générique

Cœur du « ajouter/retirer un livrable sans rien toucher ». L'orchestrateur
construit la liste des unités à partir du **registre** (déjà la source de vérité
extensible) :

```python
tasks = [
    (lang, st)
    for lang in pedagogy.languages
    for st in self._registry.canonical_order()
    if st in pedagogy.selected_supports and self._registry.has(st)
]
results = map_bounded(lambda t: self._run_one(...), tasks,
                      max_workers=workers, pause_token=pause_token)
```

L'unité dérivant du registre, **ajouter ou retirer un support est pris en compte
automatiquement** — zéro code de parallélisme à toucher. Les générateurs restent
inchangés (chapitres séquentiels en interne).

**Grain assumé (YAGNI)** : on parallélise au niveau `(langue × support)` — déjà
8 à 16 unités, suffisant pour saturer 16 workers. On **ne** parallélise **pas**
aussi les chapitres pour l'instant (éviterait un pool imbriqué). Si un jour un
projet présente peu de supports mais beaucoup de chapitres, on ajoutera ce grain.

Trois états partagés à neutraliser, par ordre de simplicité :

- **`total_cost` / `any_failure`** : agrégés **après** `map_bounded` depuis les
  `(cost, failed)` retournés → aucun verrou. Le nombre de workers est lu sur le
  champ `llm_workers` de `PedagogySettings` (cf. §8).
- **Manifeste de fraîcheur** : `manifest.record` + `write_manifest` protégés par
  un `threading.Lock` (préserve la reprise *coarse* à granularité fine).
- **Plafond de coût** : compteur de coût partagé sous verrou ; chaque tâche, en
  début, court-circuite si le cumul ≥ plafond. Dépassement borné par le nombre
  de workers (cf. §10).

## 8. Réglages & infrastructure

- **Pipeline** : `ParallelismConfig` (déjà persistée) est enfin **lue** (via
  `max_parallel_workers`) et **exposée** dans une section repliée « Avancé » de
  `generation_settings_view.py`. Défauts : `llm_workers = 16` (plage 1–64),
  `stt_cloud_workers = 3` (plage 1–8). Bornes hautes appliquées par
  `__post_init__`.
- **Pédagogie** : `PedagogySettings` gagne un champ `llm_workers: int`
  (défaut 16, plage 1–64). Pas de `ParallelismConfig` complète : la pédagogie
  n'a pas de STT, donc `stt_cloud_workers` n'aurait aucun sens. Migration
  **lenient** à la lecture du blob v2 (champ absent → défaut), et le même bloc
  « Avancé » côté `pedagogy_settings_view.py`.
- **Timeout DeepSeek** : fixer un timeout explicite (~600 s) sur le client
  `OpenAI` du `DeepSeekAdapter` (aujourd'hui construit sans timeout). En
  non-streaming, le SDK absorbe les keep-alive — rien d'autre à coder.
- **`FsArtifactStore`** : rendre le suffixe `.tmp` **unique** (uuid4) dans
  `_tmp_path_for` — défense en profondeur contre deux écritures concurrentes du
  même chemin (improbable en pratique, chaque unité écrit un chemin distinct).

## 9. Thread-safety & invariants (vérifiés)

Briques **déjà prêtes**, confirmées par lecture de code :

- **SQLite** : mode WAL + une connexion par thread (`threading.local`) +
  `busy_timeout`. Les phases per-video écrivent des lignes
  `(run_id, phase_id, video_id)` distinctes (pas de conflit). WAL autorise les
  lectures UI concurrentes avec les écritures workers ; les écritures workers se
  sérialisent (busy_timeout) — négligeable (writes courts vs appels LLM en
  secondes).
- **`PauseToken`** : `threading.Event` + verrou.
- **`EventBus`** : verrou sur `subscribe`/`publish` + copie des handlers avant
  dispatch.
- **`RetryPolicy`** : `@dataclass(frozen=True)`, jitter activé → partageable
  entre threads, atténue tout pic de retry synchronisé.
- **`DeepSeekAdapter`** : sans état mutable, client `httpx` thread-safe pour
  appels concurrents.
- **`PromptLoader`** : aucun cache mutable ; `Environment` Jinja2 partageable,
  `render` recompile à chaque appel, `_load_source` en lecture seule.
- **`GlossaryRetriever`** : `PassthroughRetriever` (pur, sans état) est
  l'implémentation réellement injectée.
- **Viewmodels UI** : branchés via le **Signal Qt** `event_emitted`
  (`...connect(self._on_pipeline_event)` / `..._on_event`), jamais via
  `subscribe()`. Worker dans un `QThread` + Signal ⇒ **QueuedConnection** ⇒ tous
  les `apply_event`/relectures s'exécutent **sérialisés sur le thread UI**, quel
  que soit le nombre de threads workers. `RunMatrixViewModel` /
  `StatsStripViewModel` relisent SQLite (idempotent) ;
  `PedagogyProgressViewModel` mute en mémoire **mais uniquement sur le thread
  UI**.
- **`JsonlFileSink`** : `_write` sérialise par verrou interne (seul abonné
  potentiel via `subscribe`, chemin worker).

## 10. Comportements assumés & limites connues

1. **La pause n'est plus instantanée.** Un appel LLM en cours n'est pas
   interruptible. Pause/annulation ⇒ on cesse de soumettre, les requêtes en vol
   (≤ workers) terminent, puis on bloque/lève. `map_bounded` honore le
   `PauseToken` **entre soumissions**.
2. **Plafond de coût non-déterministe sur « qui passe ».** Avec un pool, *quelles*
   unités sont générées avant le franchissement du plafond dépend de
   l'ordonnancement des threads (et non plus de l'ordre canonique). Conséquence :
   deux runs interrompus au plafond peuvent compléter des unités différentes.
   Sans corruption ni double facturation ; dépassement borné par
   `workers × coût d'un appel` (≈ 1 $ à 16 workers, DeepSeek étant bon marché).
3. **Gain pipeline dépendant du provider STT.** En STT **local** (1 GPU,
   séquentiel imposé), si la transcription domine le temps total, le Lot C
   apporte peu. Gain franc en STT **cloud** ou quand les phases LLM dominent.
4. **Lot D (parallélisme interne phase 5) : ROI faible, donc optionnel.** Le
   handler de consolidation est déjà dense ; le gain des résumés parallélisés est
   marginal. Implémenté seulement si le profilage le justifie (sinon non fait).
5. **`map_bounded` ne préempte pas.** « Fail-fast » et « cancel » n'annulent que
   les tâches **non démarrées** ; les démarrées vont au bout.
6. **Sérialisation des écritures SQLite** (WAL, un écrivain à la fois) : présente
   mais négligeable au regard de la durée des appels LLM.

## 11. Extensibilité

- **Ajouter une phase pipeline** : écrire son handler ; il est **séquentiel par
  défaut** (`max_parallel_workers` hérite `1`), opt-in pour paralléliser. Le
  moteur ne change pas. Si la phase est batch avec boucle interne, elle utilise
  `map_bounded` elle-même.
- **Retirer une phase** : la désenregistrer du `PhaseRegistry`. Aucun impact.
- **Ajouter/retirer un livrable pédagogique** : enregistrer/retirer le
  générateur du `SupportGeneratorRegistry`. L'aplatissement `(langue × support)`
  le prend en compte automatiquement — aucun code de parallélisme à modifier.

## 12. Tests

- **`map_bounded`** : ordre préservé ; borne de concurrence respectée (compteur
  de concurrence max observée) ; `max_workers=1` ≡ séquentiel ; fail-fast
  (annulation des non démarrées + propagation de la 1ʳᵉ exception) ; pause puis
  reprise ; annulation via `PauseToken`.
- **Déterminisme** : même document consolidé en séquentiel vs parallèle (golden
  test sur N vidéos), `FakeLLMProvider` déterministe par entrée.
- **Concurrence réelle** : pédagogie avec `FakeLLMProvider` lent → aucun fichier
  ni manifeste corrompu, `total_cost`/`any_failure` exacts, respect du plafond
  (dépassement ≤ workers).
- **Régression UI** : events entrelacés via `QtEventBus` → matrice/tuiles
  cohérentes (smoke `pytest-qt`).
- Suite complète verte : `pytest`, `ruff check .`, `mypy src tests`.

## 13. Découpage en lots

1. **Lot A — Socle** : `core/concurrency/map_bounded` + durcissement
   `FsArtifactStore` (`.tmp` unique) + timeout DeepSeek + tests du primitif.
2. **Lot B — Pédagogie** : aplatissement `(langue × support)`, verrous ciblés
   (manifeste, compteur plafond), champ workers `PedagogySettings` + UI
   « Avancé ».
3. **Lot C — Pipeline per-video** : `max_parallel_workers` sur les handlers
   0/1/3/4, câblage moteur, exposition `ParallelismConfig` en UI « Avancé ».
4. **Lot D — Phases batch internes** : phase 6 (langue × doc), phase 7 (langues),
   et phase 5 (résumés) **si** profilage favorable (cf. §10.4).

Chaque lot est livrable et testable indépendamment ; A → B délivrent déjà le
meilleur ratio gain/risque.
