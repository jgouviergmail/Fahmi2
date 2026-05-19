# Packaging Fahmi2 (Windows portable .zip)

## Pré-requis

1. **Python 3.11 ou 3.12** installé.
2. **Venv** activé :
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   pip install pyinstaller>=6.10
   ```
3. **ffmpeg portable** placé dans `vendor/ffmpeg/bin/` :
   - Télécharger https://www.gyan.dev/ffmpeg/builds/ → `ffmpeg-release-essentials.zip`
   - Extraire et copier `ffmpeg.exe` et `ffprobe.exe` (du sous-dossier `bin/`)
     dans `vendor/ffmpeg/bin/`.

## Build

```powershell
.\packaging\build.ps1
```

Produit `dist/Fahmi2/` contenant `Fahmi2.exe` + dépendances + ffmpeg bundlé.

## Archive de distribution

```powershell
.\packaging\make-portable-zip.ps1
```

Produit `dist/Fahmi2-<version>-win64.zip`.

## Distribution

Distribuer le `.zip`. L'utilisateur :

1. Télécharge `Fahmi2-<version>-win64.zip`
2. Décompresse dans un dossier de son choix (ex: `C:\Apps\Fahmi2\`)
3. Double-clique sur `Fahmi2.exe`
4. Au 1er lancement, **SmartScreen** affichera un avertissement « Éditeur
   inconnu » — cliquer sur *« Plus d'infos »* → *« Exécuter quand même »*
   (avertissement une seule fois)
5. Les données utilisateur seront créées automatiquement dans
   `%APPDATA%/Fahmi2/` et `%LOCALAPPDATA%/Fahmi2/`. **Aucune intervention
   manuelle requise.**

## Mise à jour vers une nouvelle version

1. Télécharger la nouvelle version `.zip`
2. Fermer Fahmi2 si ouvert
3. Décompresser le nouveau `.zip` (peut écraser l'ancien dossier)
4. Relancer `Fahmi2.exe`

Les données utilisateur (`%APPDATA%/Fahmi2/`) sont **automatiquement
préservées** et migrées si nécessaire par le ``MigrationRunner`` interne.
