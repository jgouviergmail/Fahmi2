# Packaging Fahmi2 (Windows portable .zip)

> Build entièrement automatisé : ffmpeg est téléchargé et bundlé
> automatiquement par les scripts. L'utilisateur final n'a aucune
> dépendance externe à installer.

## Pré-requis développeur

1. **Python 3.11 ou 3.12** installé (cf.
   [docs/03-installation.md](../docs/03-installation.md)).
2. **Venv activé** avec les dépendances :
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   pip install pyinstaller>=6.10
   ```
3. **Accès internet** : le script de build télécharge ffmpeg portable s'il
   n'est pas déjà présent dans `vendor/ffmpeg/bin/`.

## Build en une commande

```powershell
.\packaging\build.ps1
```

Le script orchestre automatiquement :

1. **fetch-ffmpeg.ps1** — téléchargement de `ffmpeg-release-essentials.zip`
   depuis https://www.gyan.dev/ffmpeg/, vérification SHA256, **vérification de la
   présence de l'encodeur `libopus`** (requis pour la préparation audio du STT
   cloud — le build échoue sinon), extraction de `ffmpeg.exe` et `ffprobe.exe`
   dans `vendor/ffmpeg/bin/`. Idempotent : skip si les binaires sont déjà présents.
2. Nettoyage des anciens `build/` et `dist/`.
3. Vérification de la présence de `pyinstaller`.
4. **PyInstaller `--onedir`** : produit `dist/Fahmi2/` contenant
   `Fahmi2.exe`, toutes les dépendances Python, ffmpeg + ffprobe bundlés,
   les templates de prompts, le DDL SQLite, le fichier de messages
   localisés FR.

## Génération de l'archive de distribution

```powershell
.\packaging\make-portable-zip.ps1
```

Produit `dist/Fahmi2-<version>-win64.zip` à partir de `dist/Fahmi2/`.

## Tester l'EXE buildé

```powershell
.\dist\Fahmi2\Fahmi2.exe
```

L'application doit se lancer en moins de 5 secondes et afficher la
fenêtre principale.

## Vérifier la taille

```powershell
Get-ChildItem dist/Fahmi2 -Recurse | Measure-Object -Property Length -Sum |
    Select-Object @{n='SizeMB';e={[math]::Round($_.Sum / 1MB, 1)}}
```

Ordre de grandeur (v1.0.0) : **≈ 670 Mo déployé** (`dist/Fahmi2/`), **≈ 270 Mo
zippé** — Python embarqué + PySide6 + faster-whisper/CTranslate2 + ffmpeg (≈ 200 Mo)
+ sklearn + reportlab/xhtml2pdf.

## Distribution

Distribuer le `.zip`. L'utilisateur final :

1. Télécharge `Fahmi2-<version>-win64.zip`.
2. Décompresse dans un dossier de son choix (ex: `C:\Apps\Fahmi2\`).
3. Double-clique sur `Fahmi2.exe`.
4. Au 1er lancement, **SmartScreen** affichera un avertissement *« Éditeur
   inconnu »* — cliquer *« Plus d'infos »* → *« Exécuter quand même »*
   (une seule fois).

**Aucune autre action manuelle requise** : ffmpeg est bundlé, les données
utilisateur (projets, clés API chiffrées, etc.) sont créées automatiquement
dans `%APPDATA%\Fahmi2\` et `%LOCALAPPDATA%\Fahmi2\`.

## Mise à jour côté utilisateur

1. Télécharger la nouvelle version `.zip`.
2. Fermer Fahmi2 si ouvert.
3. Décompresser le nouveau `.zip` (peut écraser l'ancien dossier).
4. Relancer `Fahmi2.exe`.

Les données utilisateur sont **automatiquement préservées** et migrées si
nécessaire par le `MigrationRunner` interne.

## Détails techniques

### Structure du dist/Fahmi2/

```
dist/Fahmi2/
├── Fahmi2.exe                       ← Point d'entrée
├── ffmpeg.exe                       ← Bundlé (depuis vendor/)
├── ffprobe.exe                      ← Bundlé (depuis vendor/)
├── *.dll, *.pyd                     ← Runtime Python + PySide6
├── _internal/
│   ├── fahmi2/
│   │   ├── core/errors/messages.fr.json
│   │   ├── infra/prompts/defaults/*.j2   ← 8 phases + 3 phase_5_* thématiques + phase_6_glossary_localization + 8 pedagogy_* + 3 chat_*
│   │   └── infra/storage/_schema.sql
│   └── genanki/                          ← données collectées (apkg_schema.sql, apkg_col.anki2)
└── …
```

### Dépendances exports (genanki / markdown / xhtml2pdf / htmldocx)

Les exports (Anki / Markdown / PDF / HTML / Word) ajoutent des dépendances. Elles
sont **déjà câblées** dans `packaging/fahmi2.spec` (gitignored ; build v1.0.0 validé) :

- **`xhtml2pdf`** (export **PDF**, rendu du HTML) s'appuie sur **`reportlab`** et
  tire `html5lib`, `pypdf`, `Pillow`, `svglib`, `arabic-reshaper`, `python-bidi`,
  `pyHanko` — **tous Python pur** (aucun binaire natif), donc *bundleables* mais
  ils **alourdissent** l'archive (≈ 270 Mo zippé, ≈ 670 Mo déployé). Le `.spec`
  applique `collect_all('xhtml2pdf')` + `collect_all('reportlab')` (données et
  **polices internes** de ReportLab) + `collect_all('arabic_reshaper')` (fichier de
  config). L'export **HTML** n'ajoute rien (pur Python).
- **`markdown`** (rendu Markdown→HTML, partagé HTML/PDF) charge ses extensions
  (`tables`, `toc`…) **par nom** → `collect_submodules('markdown')` dans le `.spec`.
- **`genanki` 0.13.1** (export `.apkg`) **inline le schéma en modules Python**
  (`apkg_col.py` / `apkg_schema.py`) : **aucun fichier de données à collecter** —
  ses modules sont bundlés par l'analyse d'imports. (`collect_data_files('genanki')`
  renvoie `[]` ; conservé dans le `.spec` par sécurité si une version future
  ré-externalise ces données.)
- **`htmldocx`** (export **Word `.docx`**, rendu HTML→docx) s'appuie sur
  **`beautifulsoup4`** (`bs4`) — tous deux **pur Python** ; `lxml` (natif) est
  **déjà** tiré par `python-docx` (cf. ingestion). Imports paresseux dans
  `markdown_docx` → `hiddenimports += ['htmldocx']` + `collect_submodules('bs4')`
  dans le `.spec`.
- **Polices PDF** : le rendu PDF s'appuie sur des **polices système Windows**,
  enregistrées auprès de ReportLab — **aucune police à bundler**, mais l'EXE en
  dépend à l'exécution (toujours présentes sur une cible Windows standard) :
  **Arial** (`%SystemRoot%\Fonts\arial*.ttf`) pour le latin **et l'arabe** (glyphes
  arabes + liaison contextuelle via `arabic-reshaper`/`python-bidi`) ; **Microsoft
  YaHei** (`%SystemRoot%\Fonts\msyh.ttc`, TrueType Collection chargée via
  `subfontIndex`) pour le **chinois**. Si YaHei est absente, l'export PDF chinois
  lève `EXPORT.NO_CJK_FONT` (MD/HTML/Word restent disponibles). Quelques tirets
  Unicode rares (U+2010/2011/2012/2015) non rendus par ReportLab+Arial sont
  normalisés au rendu PDF (`markdown_pdf._normalize_for_pdf`). Deux autres
  traitements **purement runtime** (rien à bundler) : les caractères **sans glyphe**
  dans la police active (émojis décoratifs) sont **retirés** du PDF
  (`_strip_unrenderable_for_pdf`), et la **prose chinoise est pré-coupée** par `<br/>`
  (ReportLab ne coupe qu'aux espaces, absents en CJK ; `_prewrap_cjk_runs`).

### Traductions i18n (.qm)

L'UI est traduisible via la pile native Qt (`QTranslator` + `.ts` / `.qm` ;
cf. `src/fahmi2/i18n/`). La langue source est le **français** — les chaînes
en code sont en FR. Les autres langues sont chargées au démarrage depuis des
fichiers `.qm` binaires (compilés depuis les `.ts` éditables) bundlés avec
l'application.

- **Au build** : régénérer les `.qm` (avant ou après `pyinstaller`) :
  ```powershell
  .\.venv\Scripts\python.exe scripts\i18n_compile.py
  ```
  Le dossier `src/fahmi2/i18n/compiled/` est **`.gitignore`** (artefact
  binaire dérivé) — il **doit** être recompilé à chaque build (le script
  `build.ps1` peut être étendu pour le faire automatiquement).
- **Dans `packaging/fahmi2.spec` (gitignored)** — ajouter dans `datas` :
  ```python
  ("src/fahmi2/i18n/compiled/*.qm", "fahmi2/i18n/compiled"),
  ```
  Sans cette ligne, **l'app packagée n'embarquera pas les traductions** et
  restera en français quelle que soit la préférence utilisateur (silencieux :
  `install_translator` retombe sur la langue source si le `.qm` est absent).
- **Au runtime** : `fahmi2.i18n.bundled_translations_dir()` détecte le mode
  packagé (`sys.frozen` + `sys._MEIPASS`) et résout
  `<bundle_root>/fahmi2/i18n/compiled/`. En dev, résolu via `__file__` à
  côté du paquet.

**Ajouter une langue** :
1. Ajouter la valeur à `AppLanguage` (`src/fahmi2/i18n/languages.py`) + son
   libellé natif dans `LANGUAGE_LABELS`.
2. `.\.venv\Scripts\python.exe scripts\i18n_extract.py` — génère
   `fahmi2_<code>.ts` (langue cible) ou complète l'existant.
3. Traduire les `<translation type="unfinished"></translation>` dans le
   `.ts` (éditeur de texte ou Qt Linguist).
4. `.\.venv\Scripts\python.exe scripts\i18n_compile.py` — produit le `.qm`.
5. Rebuild PyInstaller : le `.qm` est embarqué via `datas`.

### Dépendances ingestion documents (pypdf / python-docx)

L'ingestion des **documents texte** (`infra/ingestion/text_extractor.py`) ajoute :

- **`pypdf`** (extraction du texte des **PDF**) est **déjà** tiré par `xhtml2pdf`
  (cf. ci-dessus) → déjà bundlé, rien de plus à câbler.
- **`python-docx`** (module `docx`, extraction des **.docx**) **embarque un
  template** (`docx/templates/default.docx`) chargé à l'instanciation de
  `Document()` → ajouter `collect_data_files('docx')` (ou `collect_all('docx')`)
  dans le `.spec`, sinon l'extraction `.docx` échoue en mode packagé.
- `pypdf` et `docx` sont importés **paresseusement** (dans les fonctions de
  `DefaultTextExtractor`) : si l'analyse statique de PyInstaller les manque, les
  ajouter en `hiddenimports`.

### Binaire yt-dlp (ingestion YouTube)

L'ingestion des **liens YouTube** (`infra/ingestion/youtube_downloader.py`)
appelle le **binaire** `yt-dlp` (pas une dépendance pip importée) :

- **Au build** : télécharger `yt-dlp.exe` depuis la release GitHub officielle
  (`yt-dlp/yt-dlp`) et le copier **à la racine du bundle** (même dossier que
  `ffmpeg.exe`). Cf. `packaging/fetch-ytdlp.ps1` (script dédié).
- **Au runtime** : `resolve_ytdlp_binary_or_none()` cherche, dans l'ordre, la
  variable d'environnement **`FAHMI2_YTDLP`** (override), puis le binaire bundlé,
  puis le binaire installé **à côté de l'interpréteur** (venv), sinon retombe sur
  le `PATH`.
- **En développement** : `pip install yt-dlp` (déjà dans les dépendances `dev`)
  suffit — `yt-dlp.exe` atterrit dans `.venv/Scripts/` et est résolu
  automatiquement, sans variable d'environnement.
- **Fragilité (important)** : yt-dlp **casse régulièrement** quand YouTube change
  ses protections. Le binaire est donc **remplaçable sans rebuild** (override
  `FAHMI2_YTDLP` ou remplacement du `yt-dlp.exe` bundlé). Recommander un rebuild
  régulier pour rafraîchir la version bundlée. En cas d'échec, le message
  `INGESTION.YOUTUBE_DOWNLOAD_FAILED` invite à mettre à jour yt-dlp.
- **Réseau requis** ; le téléchargement de contenu YouTube relève de la
  **responsabilité de l'utilisateur** (ToS YouTube).
- yt-dlp télécharge la **meilleure piste audio** (`-f bestaudio/best`,
  `--no-playlist`) ; la conversion WAV est faite ensuite par le ffmpeg bundlé du
  `MediaIngestor` (yt-dlp n'a donc pas besoin d'une `--ffmpeg-location` dédiée).

### Résolution runtime du ffmpeg bundlé

Au démarrage de l'application, `core/config/paths.py` détecte
`sys.frozen=True` + `sys._MEIPASS` (signatures PyInstaller) et résout les
binaires bundlés via `resolve_ffmpeg_binary_or_none()` /
`resolve_ffprobe_binary_or_none()`. En mode développement, ces fonctions
retournent `None` et le PATH système est utilisé.

### Mise à jour de ffmpeg

Pour figer une version de ffmpeg (au lieu de l'« essentials » courant) :

1. Modifier `$downloadUrl` dans `packaging/fetch-ffmpeg.ps1` pour pointer
   sur la version désirée.
2. Supprimer `vendor/ffmpeg/bin/` localement.
3. Relancer `.\packaging\fetch-ffmpeg.ps1`.
4. Commiter (ne pas commiter les binaires, déjà dans `.gitignore`).

### Pourquoi pas de signature de code en v1 ?

La signature requiert un certificat commercial (~200-500 €/an). Pour
l'usage mono-utilisateur ciblé, le coût-bénéfice n'est pas pertinent en
v1. SmartScreen affiche un avertissement au 1er lancement uniquement
(clic *« Plus d'infos »* → *« Exécuter quand même »*).

Si la distribution s'étend à un public plus large, l'ajout d'une
signature SignTool est trivial à intégrer (étape supplémentaire dans
`build.ps1`).
