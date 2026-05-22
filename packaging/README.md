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

Cible : ~250-300 Mo (Python embedded + PySide6 + ffmpeg + sklearn).

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
│   │   ├── infra/prompts/defaults/*.j2   ← 8 phases + 8 pedagogy_*
│   │   └── infra/storage/_schema.sql
│   └── genanki/                          ← données collectées (apkg_schema.sql, apkg_col.anki2)
└── …
```

### Dépendances exports (genanki / markdown / xhtml2pdf)

Les exports (Anki / Markdown / PDF / HTML) ajoutent des dépendances à collecter
par PyInstaller. À vérifier dans `packaging/fahmi2.spec` (gitignored — modification
non versionnée) au prochain build :

- **`genanki`** (export `.apkg`) embarque des **fichiers de données**
  (`apkg_schema.sql`, `apkg_col.anki2`) qui ne sont pas détectés par l'analyse
  d'imports : les collecter explicitement via `--collect-data genanki` (CLI) ou
  `collect_data_files('genanki')` dans le `.spec`. Sans cela, l'export plante au
  runtime (fichier de données introuvable).
- **`xhtml2pdf`** (export **PDF**, rendu du HTML) s'appuie sur **`reportlab`** et
  tire `html5lib`, `pypdf`, `Pillow`, `svglib`, `arabic-reshaper`, `python-bidi`,
  `pyHanko` — **tous Python pur** (aucun binaire natif), donc *bundleables* mais
  ils **alourdissent** l'archive. Collecter données + sous-modules :
  `--collect-all xhtml2pdf` et `--collect-all reportlab` (ReportLab embarque des
  données et polices internes) ; ajouter en `hiddenimports` ce que l'analyse
  manque. **`markdown`** (rendu Markdown→HTML, partagé HTML/PDF) est un module pur.
  L'export **HTML** n'ajoute rien (pur Python).
- **Police PDF** : le rendu PDF s'appuie sur la police **Arial du système
  Windows** (`%SystemRoot%\Fonts\arial*.ttf`), enregistrée auprès de ReportLab —
  **aucune police à bundler**, mais l'EXE en dépend à l'exécution (toujours
  présente sur une cible Windows). Quelques tirets Unicode rares
  (U+2010/2011/2012/2015) non rendus par ReportLab+Arial sont normalisés au rendu
  PDF (`markdown_pdf._normalize_for_pdf`).

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
