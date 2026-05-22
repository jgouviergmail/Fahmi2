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

- **Ajout** d'un dispatcher de format et de la table d'extensions (centralisation,
  pas de magic string) :
  - `EXTENSION_BY_FORMAT: dict[ExportFormat, str]` → `{MARKDOWN: ".md", PDF: ".pdf",
    HTML: ".html"}`.
  - `render_document(markdown_text: str, output_path: Path, fmt: ExportFormat) -> None`
    qui dispatche : `MARKDOWN` → écriture texte atomique ; `PDF` →
    `render_markdown_to_pdf` ; `HTML` → `render_markdown_to_html`.
- Les primitives existantes `render_markdown_to_pdf` / `render_markdown_to_html`
  sont **réutilisées telles quelles** (le HTML autonome stylé convient à un
  document par support).
- **Suppression** de `assemble_markdown` (et de ses 2 tests dans
  `tests/unit/infra/export/test_markdown_pdf.py`) : devient mort une fois
  l'agrégation pédagogie supprimée (les fichiers consolidé/glossaire et chaque
  support sont déjà des documents Markdown complets — aucun assemblage requis).

### 2. `app/_export_common.py` (nouveau, interne)

- `@dataclass(frozen=True) DocumentExportResult` (**déplacé** depuis
  `pedagogy_export.py` ; conserve `output_paths` + propriété `document_count`).
- `DocumentCollector = Callable[[Project], list[tuple[str, str]]]` (alias de type,
  documente le contrat « prêt-pour-C »).
- `write_documents(documents: Iterable[tuple[str, str]], *, output_dir: Path, fmt:
  ExportFormat) -> DocumentExportResult` : pour chaque `(stem, markdown)`, calcule
  `output_dir / f"{stem}{EXTENSION_BY_FORMAT[fmt]}"` et appelle `render_document`.
  Retourne les chemins écrits (ordre d'entrée préservé → déterministe).

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
- Constantes d'agrégation obsolètes supprimées (`_SUBJECT_STEM`,
  `_CORRECTION_STEM`, `_SUBJECT_TITLE`, `_CORRECTION_TITLE`, `_SECTION_SEPARATOR`
  côté pédagogie). Les stems suivent la convention `<support>.<lang>` /
  `<support>.<lang>.corrige`, cohérente avec `consolidated.{lang}` et le layout
  disque.

### 4. `app/generation_export.py` (nouveau)

- `collect_generation_documents(project) -> list[tuple[str, str]]` : pour chaque
  langue de sortie présente, lit (si le fichier existe) :
  - `consolidated.{lang}.md` → `(f"consolidated.{lang.value}", contenu)` ;
  - `glossary.{lang}.md` → `(f"glossary.{lang.value}", contenu)`.
  La source est lue sur disque dans `output_dir` de génération
  (`workspace_folder / generation / output`), via les helpers existants
  (`consolidated_doc_filename`, et le nom `glossary.{lang}.md`).
- `export_generation_documents(project, *, output_dir, fmt) -> DocumentExportResult`
  délègue à `write_documents`.

### 5. Domaine — `domain/generation.py`

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
  `run_document_export(*, window, logs_dock, configured_formats, labels,
  exporter)` qui factorise la séquence commune : si aucun format → message ;
  `QInputDialog` (choix du format) → `QFileDialog.getExistingDirectory` → appel de
  `exporter(fmt, output_dir)` → gestion `Fahmi2Error` / `Exception` → cas
  « 0 document » → log `*_EXPORTED` + `QMessageBox`. `exporter` est un
  `Callable[[ExportFormat, Path], DocumentExportResult]`.
- `ui/pedagogy_controller.py` : `export_markdown/pdf/html` + `_export_documents`
  remplacés par un appel au helper partagé, en passant
  `lambda fmt, d: export_pedagogy_documents(project, output_dir=d, fmt=fmt)` et
  `project.pedagogy.export_formats`. La pré-condition « pédagogie configurée »
  reste dans le contrôleur. APKG conserve son chemin dédié.
- `ui/generation_controller.py` : `show_export=True` + tooltip ;
  `export_requested` → handler qui appelle le helper partagé avec
  `export_generation_documents` et `generation.export_formats`.
- `EXPORT_LABELS` (dans `ui/pedagogy_labels.py`) est **réutilisé** par la
  génération (libellés génériques Anki/Markdown/PDF/HTML). Pas de déplacement
  (YAGNI) ; importé tel quel.

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
  `assemble_markdown` ; ajout d'un test du dispatcher `render_document`
  (extension correcte par format) et de `EXTENSION_BY_FORMAT`.
- `tests/unit/app/test_export_common.py` (nouveau) : `write_documents` écrit un
  fichier par `(stem, md)` avec la bonne extension ; ordre préservé ;
  `document_count`.
- `tests/unit/app/test_pedagogy_export_documents.py` : adapté — vérifie **un
  fichier par support/corrigé** (plus d'agrégat `supports.{lang}.md`) ; noms
  `<support>.<lang>(.corrige).<ext>` ; supports absents omis.
- `tests/unit/app/test_pedagogy_export.py` : `.apkg` inchangé (régression).
- `tests/unit/app/test_generation_export.py` (nouveau) : consolidé + glossaire par
  langue ; fichiers manquants omis ; formats MD/PDF/HTML.
- `tests/unit/domain/` : invariant `GenerationSettings.export_formats` (APKG
  rejeté ; défaut vide).
- `tests/unit/infra/storage/` : round-trip + désérialisation **lenient** (payload
  sans `export_formats` → ensemble vide) ; snapshot de run.
- `tests/conftest.py` : `make_generation_settings` accepte/ initialise
  `export_formats` (défaut vide).
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
