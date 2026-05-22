# Export granulaire (pédagogie) + export documentaire de la Génération — Design

**Date :** 2026-05-22
**Statut :** validé (brainstorming) — prêt pour plan d'implémentation

## Objectif

Deux évolutions de l'export, conçues avec une factorisation commune :

1. **Pédagogie** — les exports **Markdown, PDF et HTML** produisent désormais
   **un fichier par support** (et un fichier par corrigé), au lieu d'un document
   agrégé par langue. La séparation visuelle demandée pour le HTML est obtenue par
   la séparation **physique** : chaque support devient un document autonome propre.
2. **Génération** — ajout d'un export documentaire **Markdown / PDF / HTML** (même
   mécanique et même paramétrage que la pédagogie), produisant le **document
   consolidé** et le **glossaire** en fichiers séparés, **par langue**.

L'export Anki `.apkg` (pédagogie uniquement) est **inchangé**.

## Architecture retenue : « A, prête-pour-C »

Un **cœur d'écriture générique** partagé, alimenté par des **collecteurs** propres
à chaque fonctionnalité. Le contrat partagé est :

```
list[tuple[str, str]]   # (stem, markdown) — stem = nom de fichier sans extension
        +
ExportFormat            # MARKDOWN | PDF | HTML
        ↓
write_documents(...)    # écrit un fichier par (stem, markdown) à la bonne extension
        ↓
DocumentExportResult    # chemins écrits
```

Chaque fonctionnalité expose un **collecteur** à signature uniforme
`Callable[[Project], list[tuple[str, str]]]`. Migration future vers un Protocol
formel (`DocumentSource.collect()`, approche « C ») ou un registre auto-enregistré
(aligné sur `FeatureRegistry`) reste **mécanique** : envelopper le collecteur dans
une classe. On ne paie pas cette indirection tant que l'auto-enregistrement n'est
pas un besoin (YAGNI).

**Note d'extensibilité.** Ajouter un nouveau support pédagogique ne touche pas le
cœur : le collecteur pédagogie itère les supports présents. Ajouter une 3ᵉ
fonctionnalité = écrire un nouveau collecteur + un `export_<feature>_documents`,
sans modifier `write_documents`. Le cœur partagé suppose des documents **Markdown
déjà rendus** : une source produisant une forme différente nécessiterait d'étendre
le cœur (limite commune à A et C).

## Composants

### 1. `infra/export/markdown_pdf.py` (modifié)

- **Ajout** de la table d'extensions (centralisation, pas de magic string) :
  `EXTENSION_BY_FORMAT: dict[ExportFormat, str]` → `{MARKDOWN: ".md", PDF: ".pdf",
  HTML: ".html"}` (APKG **absent** — format non documentaire).
- Les primitives `render_markdown_to_pdf` / `render_markdown_to_html` /
  `pdf_fonts_available` sont **conservées telles quelles** : le module reste un
  **pur *renderer*** sans dépendance vers la couche storage. Le **dispatch** par
  format vit dans la couche app (cf. §2), **pas ici** (on évite de coupler
  `infra/export` à `FsArtifactStore`).
- **Suppression** de `assemble_markdown` (et de ses 2 tests dans
  `tests/unit/infra/export/test_markdown_pdf.py`) : devient mort une fois
  l'agrégation pédagogie supprimée (les fichiers consolidé/glossaire et chaque
  support sont déjà des documents Markdown complets — aucun assemblage requis).

### 2. `app/document_export.py` (nouveau, **public**)

Module **public** (pas `_underscore`) car l'UI en importe `DocumentExportResult`
(type de retour du helper d'export). Précédent : `app/_cost_common.py` est interne
et n'est jamais importé par l'UI — ce ne serait pas le cas ici.

- `@dataclass(frozen=True) DocumentExportResult` (**déplacé** depuis
  `pedagogy_export.py` ; conserve `output_paths` + propriété `document_count`).
- `DocumentCollector = Callable[[Project], list[tuple[str, str]]]` (alias de type,
  documente le contrat « prêt-pour-C »).
- `write_documents(documents: Iterable[tuple[str, str]], *, output_dir: Path, fmt:
  ExportFormat) -> DocumentExportResult` — **porte le dispatch** :
  - garde : `if fmt not in EXTENSION_BY_FORMAT: raise ValueError(...)` (rejette
    APKG / format non documentaire — erreur de programmation) ;
  - pour chaque `(stem, markdown)`, chemin
    `output_dir / f"{stem}{EXTENSION_BY_FORMAT[fmt]}"` ;
  - `MARKDOWN` → `FsArtifactStore().write_text_atomic` (**copie atomique** du
    contenu — préserve le comportement actuel de l'export MD) ;
  - `PDF` → `render_markdown_to_pdf` ; `HTML` → `render_markdown_to_html`.
  - Retourne les chemins écrits (ordre d'entrée préservé → déterministe).

### 3. `app/pedagogy_export.py` (refactor)

- `export_pedagogy_to_apkg` : **inchangé**.
- `_build_documents` (agrégation par langue) **remplacé** par un collecteur
  `collect_pedagogy_documents(project) -> list[tuple[str, str]]` :
  - itère les langues, puis les supports dans `_EXPORT_SUPPORT_ORDER` (ordre
    déterministe conservé pour la stabilité des sorties/tests) ;
  - pour chaque `<support>.md` présent → `(f"{support.value}.{lang.value}",
    contenu)` ;
  - pour chaque `<support>.corrige.md` présent →
    `(f"{support.value}.{lang.value}.corrige", contenu)`.
- `export_pedagogy_documents(project, *, output_dir, fmt) -> DocumentExportResult`
  délègue à `write_documents(collect_pedagogy_documents(project), …)`.
- `DocumentExportResult` est désormais importé depuis `app.document_export` (plus
  défini ici).
- Constantes d'agrégation obsolètes supprimées (`_SUBJECT_STEM`,
  `_CORRECTION_STEM`, `_SUBJECT_TITLE`, `_CORRECTION_TITLE`, `_SECTION_SEPARATOR`
  côté pédagogie). Les stems suivent la convention `<support>.<lang>` /
  `<support>.<lang>.corrige`, cohérente avec `consolidated.{lang}` et le layout
  disque. `_EXPORT_SUPPORT_ORDER` est **conservé** (ordre déterministe des fichiers
  produits) ; sa docstring est mise à jour (plus d'agrégation).

### 4. `app/generation_export.py` (nouveau)

- `collect_generation_documents(project) -> list[tuple[str, str]]` : itère
  **toutes** les `Language` (robuste, sans dépendre de `project.generation` qui
  peut être `None`) et, pour chaque fichier **présent** sur disque :
  - `consolidated.{lang}.md` → stem `consolidated.{lang.value}` (nom de fichier
    `consolidated_doc_filename(lang)` privé de son extension `.md`), contenu ;
  - `glossary.{lang}.md` → stem `glossary.{lang.value}`, contenu.
  La source est le dossier de sortie génération
  (`workspace_folder / GENERATION_WORKSPACE_SUBDIR / GENERATION_OUTPUT_SUBDIR`).
  Les noms de fichiers proviennent des helpers domaine `consolidated_doc_filename`
  et **`glossary_doc_filename`** (nouveau, cf. §5) — **pas de magic string**. Les
  stems exportés sont dérivés en retirant l'extension `.md`.
- `export_generation_documents(project, *, output_dir, fmt) -> DocumentExportResult`
  délègue à `write_documents`. (`output_dir` = dossier **destination** choisi par
  l'utilisateur, distinct du dossier source ci-dessus.)

### 5. Domaine — `domain/generation.py`

- **Nouveau helper** `glossary_doc_filename(language: Language) -> str` →
  `f"glossary.{language}.md"`, à côté de `consolidated_doc_filename`. **Refactor**
  de `pipeline/handlers/phase_6_translation.py:181` (qui code le nom en dur) pour
  l'utiliser → source unique de vérité, réutilisée par le collecteur génération.
- Constante `DEFAULT_GENERATION_EXPORT_FORMATS: frozenset[ExportFormat] =
  frozenset()` (**vide = opt-in**).
- Ensemble autorisé `GENERATION_EXPORT_FORMATS: frozenset[ExportFormat] =
  frozenset({MARKDOWN, PDF, HTML})` (pas d'APKG en génération).
- `GenerationSettings` : nouveau champ
  `export_formats: frozenset[ExportFormat] = DEFAULT_GENERATION_EXPORT_FORMATS`.
- Invariant `__post_init__` : `self.export_formats <= GENERATION_EXPORT_FORMATS`
  sinon `ValueError` (APKG interdit).

### 6. Persistance — `infra/storage/sqlite_state.py`

- `_serialize_generation_settings` : ajoute
  `"export_formats": sorted(f.value for f in gen.export_formats)`.
- `_deserialize_generation_settings` : **lenient** —
  `export_formats=frozenset(ExportFormat(f) for f in payload.get("export_formats",
  []))` (les projets v2 antérieurs sans le champ retombent sur l'ensemble vide).
- Le snapshot de run (`_serialize_run_snapshot` / `_deserialize_run_snapshot`)
  réutilise ces fonctions → couvert automatiquement, y compris pour les snapshots
  anciens (désérialisation lenient).

### 7. UI

- `ui/dialogs/generation_settings_view.py` :
  - nouvelle page `_CAT_EXPORT = "Export"` (mirroir de la page pédagogie),
    cases à cocher pour **MARKDOWN, PDF, HTML uniquement** (itère
    `GENERATION_EXPORT_FORMATS`, libellés via `EXPORT_LABELS`) ;
  - `to_settings` lit les cases → `export_formats` ; `populate` coche selon
    `generation.export_formats`.
- `ui/_export_ui.py` (nouveau) — **helper UI partagé** :
  `run_document_export(*, window, logs_dock, configured_formats, label_by_format,
  exporter)` qui factorise la séquence commune : si aucun format → message ;
  `QInputDialog` (choix du format) → `QFileDialog.getExistingDirectory` → appel de
  `exporter(fmt, output_dir)` → gestion `Fahmi2Error` / `Exception` → cas
  « 0 document » → log `*_EXPORTED` + `QMessageBox`. `exporter` est un
  `Callable[[ExportFormat, Path], DocumentExportResult]`. `DocumentExportResult`
  est importé de `app.document_export`.
- `ui/pedagogy_controller.py` : `export_markdown/pdf/html` + `_export_documents`
  remplacés par un appel au helper partagé, en passant
  `lambda fmt, d: export_pedagogy_documents(project, output_dir=d, fmt=fmt)` et
  `project.pedagogy.export_formats`. La pré-condition « pédagogie configurée »
  (`project.pedagogy is None`) reste dans le contrôleur. APKG conserve son chemin
  dédié (`export_apkg`).
- `ui/generation_controller.py` : `show_export=True` + tooltip ; le bouton reste
  **toujours actif** (validation au clic, comme la pédagogie) ; pré-condition
  `project.generation is None` → message « génération non configurée » ;
  `export_requested` → handler qui appelle le helper partagé avec
  `lambda fmt, d: export_generation_documents(project, output_dir=d, fmt=fmt)` et
  `project.generation.export_formats`.
- `EXPORT_LABELS` (dans `ui/pedagogy_labels.py`) est **réutilisé** par la
  génération (libellés génériques Anki/Markdown/PDF/HTML ; seules les clés
  MD/PDF/HTML sont passées). Pas de déplacement (YAGNI) ; importé tel quel.

## Conventions de nommage des fichiers exportés

| Source | Stem | Exemple (PDF) |
|--------|------|---------------|
| Support pédagogique (sujet) | `<support>.<lang>` | `qcm.fr.pdf` |
| Support pédagogique (corrigé) | `<support>.<lang>.corrige` | `qcm.fr.corrige.pdf` |
| Génération — consolidé | `consolidated.<lang>` | `consolidated.fr.pdf` |
| Génération — glossaire | `glossary.<lang>` | `glossary.fr.pdf` |

`<support>` = `SupportType.value` ; `<lang>` = `Language.value`. Pour le format
Markdown, l'export écrit le même contenu que le fichier source (copie vers le
dossier choisi) ; PDF/HTML rendent ce Markdown.

## Gestion des erreurs

- PDF sans police Unicode : `ConfigError("EXPORT.NO_PDF_FONT")` (existant),
  remontée par le helper UI en `QMessageBox` (inchangé).
- Aucun document collecté (rien généré encore) : `document_count == 0` →
  message « Générez d'abord… » (existant côté pédagogie, identique côté génération).
- Aucun format configuré : message renvoyant vers ⚙ Réglages → Export (existant
  côté pédagogie ; le helper partagé l'unifie).
- Les exceptions inattendues restent attrapées au niveau UI (affichage UX puis
  stop), comme aujourd'hui.

## Tests

- `tests/unit/infra/export/test_markdown_pdf.py` : retrait des 2 tests
  `assemble_markdown` ; ajout d'un test de `EXTENSION_BY_FORMAT` (clés MD/PDF/HTML,
  valeurs `.md/.pdf/.html`, APKG absent).
- `tests/unit/app/test_document_export.py` (nouveau) : `write_documents` écrit un
  fichier par `(stem, md)` avec la bonne extension ; MD = contenu copié ; ordre
  préservé ; `document_count` ; **garde** : `fmt=APKG` lève `ValueError`. Les cas
  PDF sont sous `@pytest.mark.skipif(not pdf_fonts_available())`.
- `tests/unit/app/test_pedagogy_export_documents.py` : adapté — vérifie **un
  fichier par support/corrigé** (plus d'agrégat `supports.{lang}.md`) ; noms
  `<support>.<lang>(.corrige).<ext>` ; supports absents omis. PDF sous `skipif`
  (pattern existant `pdf_fonts_available`).
- `tests/unit/app/test_pedagogy_export.py` : `.apkg` inchangé (régression).
- `tests/unit/app/test_generation_export.py` (nouveau) : consolidé + glossaire par
  langue ; fichiers manquants omis ; `project.generation is None` → liste vide ;
  formats MD/HTML ; PDF sous `skipif`.
- `tests/unit/domain/test_generation.py` : helper `glossary_doc_filename` ;
  invariant `GenerationSettings.export_formats` (APKG rejeté → `ValueError` ;
  défaut vide).
- `tests/unit/pipeline/handlers/test_phase_6_translation.py` : le nom du glossaire
  reste `glossary.{lang}.md` après refactor vers le helper (non-régression).
- `tests/unit/infra/storage/` : round-trip + désérialisation **lenient** (payload
  sans `export_formats` → ensemble vide) ; snapshot de run.
- `tests/conftest.py` : `make_generation_settings` initialise `export_formats`
  (défaut vide ; surchargeable par kwarg).
- UI : smoke tests `pytest-qt` de la page Export génération (build/populate/
  to_settings) ; viewmodels inchangés.

## Documentation à mettre à jour

- `docs/01-presentation-fonctionnelle.md` : export pédagogie = 1 fichier/support ;
  nouvel export génération (consolidé + glossaire, MD/PDF/HTML).
- `docs/04-parametrage.md` : page Export côté Génération ; granularité pédagogie.
- `docs/07-guide-utilisateur.md` : bouton Exporter en Génération ; description des
  fichiers produits.
- `CLAUDE.md` : mention export génération + granularité par fichier.
- `CHANGELOG.md` : entrée dédiée.
- `packaging/README.md` : inchangé (HTML/MD/PDF déjà couverts ; dépendances
  identiques).

## Hors périmètre

- Export APKG côté génération (pas de cartes).
- Agrégation optionnelle (un seul document) : abandonnée suite au choix « 1 fichier
  par support / consolidé + glossaire séparés ».
- Auto-enregistrement des sources d'export dans un registre (approche C / registre)
  — possible plus tard, migration mécanique.
- Choix du dossier d'export persistant / export « tous formats en un clic » : on
  conserve le choix de **un** format par action via `QInputDialog` (UX existante).
