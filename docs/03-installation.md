# Fahmi2 — Guide d'installation

## 1. Installation utilisateur final

### 1.1 Pré-requis matériels

- **Windows 11** (Windows 10 minimum, 64-bit).
- **8 Go de RAM** minimum recommandés.
- **3 Go d'espace disque libre** (application + cache modèle Whisper si
  utilisé en local).
- **GPU NVIDIA** compatible CUDA **uniquement** si vous souhaitez utiliser
  la transcription locale (faster-whisper). **Optionnel** sinon : la
  transcription via OpenAI cloud fonctionne sur n'importe quelle machine.

### 1.2 Procédure d'installation

1. **Télécharger** le fichier `Fahmi2-<version>-win64.zip` fourni.
2. **Décompresser** dans un dossier de votre choix (ex: `C:\Apps\Fahmi2\`,
   ou directement sur le bureau).
   - Windows : clic droit sur le `.zip` → *« Extraire tout… »* → choisir
     le dossier de destination → *« Extraire »*.
3. **Ouvrir** le dossier extrait et **double-cliquer sur `Fahmi2.exe`**.
4. **Premier lancement** :
   - Windows affichera un écran bleu **SmartScreen** indiquant
     *« Windows a protégé votre PC »* (« Éditeur inconnu »).
   - Cliquez sur **« Plus d'infos »** puis **« Exécuter quand même »**.
   - Cet avertissement n'apparaîtra plus aux lancements suivants.

C'est tout. Aucune installation système, aucune dépendance à installer,
aucun droit administrateur requis. ffmpeg est inclus dans l'archive.

### 1.3 Créer un raccourci sur le bureau (optionnel)

Clic droit sur `Fahmi2.exe` → *« Envoyer vers »* → *« Bureau (créer un
raccourci) »*.

### 1.4 Données utilisateur

Au premier lancement, l'application crée automatiquement :

| Chemin | Contenu |
|--------|---------|
| `%APPDATA%\Fahmi2\` | Projets, clés API chiffrées, prompts override, base SQLite, logs |
| `%LOCALAPPDATA%\Fahmi2\` | Cache des modèles téléchargés (Whisper local uniquement) |
| `HKCU\Software\Fahmi2` (registre) | Préférences UI (taille fenêtre, dernier projet) |

Ces données **survivent aux mises à jour** de l'application.

### 1.5 Mise à jour

1. Télécharger la nouvelle version `.zip`.
2. **Fermer Fahmi2** si l'application est ouverte.
3. **Remplacer le dossier de l'application** par le contenu décompressé du
   nouveau `.zip`. Vous pouvez supprimer l'ancien dossier en entier puis
   décompresser — aucune donnée ne s'y trouve.
4. Relancer `Fahmi2.exe`.

Les projets, paramètres et clés API restent **automatiquement préservés**
dans `%APPDATA%\Fahmi2\`. Si une migration de schéma est nécessaire, elle
est appliquée automatiquement avec sauvegarde préalable.

### 1.6 Désinstallation

1. Supprimer le dossier où vous avez décompressé Fahmi2.
2. **Si vous souhaitez aussi effacer vos données** (projets, clés API…) :
   - Supprimer `%APPDATA%\Fahmi2\` (entrer dans la barre d'adresse de
     l'explorateur Windows).
   - Supprimer `%LOCALAPPDATA%\Fahmi2\`.
   - Optionnel : ouvrir `regedit`, naviguer dans
     `HKEY_CURRENT_USER\Software\Fahmi2` et supprimer la clé.

Aucune trace n'est laissée ailleurs sur le système.

## 2. Installation développeur (build depuis les sources)

### 2.1 Pré-requis logiciels

- **Python 3.11 ou 3.12** (pas 3.13 — voir [pyproject.toml](../pyproject.toml)).
  - Téléchargement : https://www.python.org/downloads/
  - Cocher *« Add Python to PATH »* lors de l'installation.
- **Git** : https://git-scm.com/downloads
- **PowerShell 7+** recommandé (PowerShell 5.1 fonctionne aussi).
- **ffmpeg** dans le PATH **uniquement pour les tests** (le packaging
  télécharge sa propre copie). Sur Windows :
  `winget install --id=Gyan.FFmpeg -e` ou `choco install ffmpeg`.

### 2.2 Cloner et préparer le venv

```powershell
git clone <url-du-repo> Fahmi2
cd Fahmi2

# Créer un venv en utilisant Python 3.12 explicitement (recommandé)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Installer le projet en mode éditable avec les dépendances de dev
python -m pip install --upgrade pip
pip install -e ".[dev]"
pip install pyinstaller>=6.10

# Installer les hooks pre-commit
pre-commit install
```

### 2.3 Vérifier l'installation

```powershell
pytest -q
ruff check .
mypy src tests
```

Tous doivent réussir sans erreur. Cf.
[06-procedures-techniques.md](06-procedures-techniques.md) pour le détail
de chaque commande.

### 2.4 Lancer l'application en mode dev

```powershell
python -m fahmi2.ui.app_main
```

## 3. Build de l'archive de distribution

Cf. [packaging/README.md](../packaging/README.md) pour le détail.

Procédure rapide depuis le venv activé :

```powershell
# Tout en une commande : télécharge ffmpeg + build + zip
.\packaging\build.ps1
.\packaging\make-portable-zip.ps1
```

Le `.zip` final apparaît dans `dist/Fahmi2-<version>-win64.zip`.

## 4. Dépannage de l'installation

### 4.1 « Cette application ne peut pas s'exécuter sur votre PC »

- Vérifier que vous êtes bien sur **Windows 10/11 64-bit** (la version 32-bit
  n'est pas supportée).
- Réessayer en exécutant **en tant qu'administrateur** (clic droit sur
  `Fahmi2.exe` → *« Exécuter en tant qu'administrateur »*). Note : aucune
  fonction de l'app n'exige réellement les droits admin, c'est un test de
  diagnostic.

### 4.2 SmartScreen revient à chaque lancement

C'est généralement parce que le dossier d'extraction est sur un emplacement
réseau ou un volume amovible avec attribut « Mark-of-the-Web » persistant.
Solution : déplacer le dossier vers un emplacement local
(ex: `C:\Apps\Fahmi2\`).

### 4.3 Erreur « Windows protected your PC: Editor unknown »

Comportement normal au 1er lancement. Cliquer *« Plus d'infos »* puis
*« Exécuter quand même »*. C'est uniquement parce que l'application n'est
pas signée par un certificat commercial.

### 4.4 « Le programme s'est arrêté de fonctionner »

Consulter le fichier de logs `%APPDATA%\Fahmi2\projects\<id>\events.jsonl`
pour le détail. Si le problème persiste, joindre ce fichier au rapport
d'incident.

### 4.5 Antivirus bloque `Fahmi2.exe` ou ses dépendances

C'est rare avec PyInstaller `--onedir` (contrairement à `--onefile` qui
déclenche souvent les faux positifs). Si cela arrive :

- Ajouter une exception pour le dossier d'installation dans votre
  antivirus.
- Vérifier le hash SHA256 du `.zip` téléchargé contre celui publié pour
  écarter toute corruption.
