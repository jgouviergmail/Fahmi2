# Fahmi2

> Transformez vos cours — **vidéos, fichiers audio, liens YouTube ou documents
> texte** — en documents Markdown structurés, glossaire compris, multilingue, en
> quelques heures et sans intervention manuelle.

Application desktop Windows, mono-utilisateur, **installation en double-clic**
(aucune dépendance système à installer, ffmpeg bundlé). Pipeline en 8 phases
(ingestion polymorphe — transcription Whisper ou extraction de texte — puis
7 phases LLM DeepSeek v4), entièrement paramétrable via l'interface graphique.

## Capacités

- **Entrées polymorphes** : vidéos (MP4, MKV, MOV, WebM…), fichiers audio (WAV,
  MP3, M4A, FLAC, OGG…), **liens YouTube** (vidéos unitaires ; l'audio est
  téléchargé par yt-dlp) et **documents texte** (PDF, Word, Markdown, txt —
  reformulés comme une transcription orale, ou insérés tels quels). Sources
  mixtes acceptées dans un même projet.
- **Ordre & exclusion des sources** : l'ordre de traitement (donc l'ordre des
  chapitres du document final) est réglable par glisser-déposer ; toute source
  peut être exclue puis réincluse.
- 2 langues de sortie : **français** et **anglais**.
- 2 providers STT : **faster-whisper-large-v3-turbo** local (GPU NVIDIA) ou
  **OpenAI Whisper** cloud — ce dernier gère **toute durée de cours**
  (compression Opus + découpage aux silences automatiques pour franchir la
  limite des 25 Mo d'OpenAI, de façon transparente).
- 2 modèles LLM : **DeepSeek v4 Flash** (économique) ou **Pro** (capacité
  supérieure). Mode raisonnement (`thinking` + `reasoning_effort`
  HIGH/MAX) et température configurables **par phase**.
- 4 styles de rendu : décontracté / standard / professionnel / académique +
  directives libres.
- **Document consolidé navigable** : titres numérotés hiérarchiquement
  (1, 1.1, 1.1.1), sommaire automatique avec ancres cliquables,
  admonitions élégantes (blockquote + emoji).
- **Glossaire en tableau** 4 colonnes Terme / Acronyme / Signification /
  Définition, avec l'expansion d'acronyme conservée dans sa langue
  d'origine (ROI = *Return On Investment* même dans un glossaire FR).
- **Estimation de coût pré-run** prenant en compte le thinking par
  phase + **plafond budget** avec arrêt propre.
- **Édition des prompts** depuis l'UI (menu Édition → Modifier les
  prompts…) avec validation Jinja2 et restauration au défaut.
- **Checkpointing fin par phase** : aucun travail perdu en cas de pause,
  annulation ou crash.
- **Traitement parallèle** : vidéos (phases per-vidéo) et supports pédagogiques
  traités concurremment, avec un nombre de workers réglable, pour réduire le
  délai sur les gros lots.
- **Concept de Projet persistant** avec historique de runs et reprise.
- **Stockage chiffré** des clés API (Windows DPAPI).

## Documentation

| Document | Pour qui ? |
|----------|------------|
| [Présentation fonctionnelle](docs/01-presentation-fonctionnelle.md) | Décideur / utilisateur souhaitant comprendre la valeur |
| [Présentation technique](docs/02-presentation-technique.md) | Architecte / développeur souhaitant comprendre l'implémentation |
| [Installation](docs/03-installation.md) | Utilisateur final + développeur |
| [Paramétrage](docs/04-parametrage.md) | Utilisateur final (configuration complète) |
| [Exploitation](docs/05-exploitation.md) | Utilisateur quotidien (suivi, incidents, livrables) |
| [Procédures techniques](docs/06-procedures-techniques.md) | Développeur / mainteneur |
| [Guide utilisateur](docs/07-guide-utilisateur.md) | Utilisateur final non-technicien (démarrage rapide) |
| [CHANGELOG](CHANGELOG.md) | Historique des versions |
| [Spec design v1](docs/superpowers/specs/2026-05-19-fahmi2-design.md) | Architecture détaillée |
| [Plans d'implémentation](docs/superpowers/plans/) | Détail des jalons d'implémentation |
| [Packaging](packaging/README.md) | Build et distribution |

## Démarrage rapide (utilisateur final)

1. Téléchargez `Fahmi2-X.Y.Z-win64.zip`.
2. Décompressez où vous voulez (ex: `C:\Apps\Fahmi2\`).
3. Double-cliquez sur `Fahmi2.exe`.
4. Au 1er lancement, cliquez sur *« Plus d'infos »* → *« Exécuter quand
   même »* lorsque SmartScreen le demande.
5. **Édition → Paramètres globaux** : saisir vos clés API (DeepSeek
   obligatoire, OpenAI optionnel).
6. **Fichier → Nouveau projet** : donner un nom + choisir l'emplacement du
   projet, valider.
7. Onglet **Génération → ⚙ Réglages** : choisir le dossier d'entrée (vidéos,
   audios et/ou documents) et/ou coller des liens YouTube, ordonner ou exclure
   les sources, puis régler les langues, le style et le modèle ; valider.
8. (Optionnel) Cliquer sur **💵 Estimer le coût** pour voir le budget
   avant le lancement.
9. Cliquer sur **▶ Lancer**. Récupérer les livrables Markdown à la fin
   via le bouton **📂 Dossier de sortie** (ou dans
   `<emplacement>/generation/output/`).

Voir [docs/07-guide-utilisateur.md](docs/07-guide-utilisateur.md) pour le
guide détaillé.

## Démarrage rapide (développeur)

```powershell
# Cloner et préparer
git clone <url> Fahmi2
cd Fahmi2
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install pyinstaller>=6.10
pre-commit install

# Vérifier
pytest
ruff check .
mypy src tests

# Lancer en mode dev
python -m fahmi2.ui.app_main

# Builder le .zip portable
.\packaging\build.ps1
.\packaging\make-portable-zip.ps1
```

Voir [docs/06-procedures-techniques.md](docs/06-procedures-techniques.md)
pour le détail.

## Architecture

Architecture en couches inspirée des principes hexagonaux :

```
src/fahmi2/
├── core/         logging, errors, retry, config, migrations, retrieval, ids
├── domain/       entités pures (Project, Run, PhaseExecution, Glossary, …)
├── pipeline/     PipelineEngine + 8 handlers de phase
├── infra/        adapters (STT, LLM, ffmpeg, SQLite WAL, DPAPI, prompts)
├── app/          use-cases (ProjectService, RunOrchestrator, CostEstimator…)
└── ui/           PySide6 (MainWindow à onglets, features/, widgets, dialogues)
```

Voir [docs/02-presentation-technique.md](docs/02-presentation-technique.md)
pour le détail complet.

## Statut

**v1.0.0** — pipeline complet fonctionnel, UI cockpit dense
thème Clair Fluent, packaging Windows portable opérationnel, document
consolidé navigable (numérotation hiérarchique + sommaire), glossaire
en tableau avec colonne Signification, édition des prompts depuis l'UI,
estimation de coût alignée sur l'usage réel (thinking pris en compte).
Cf. [CHANGELOG.md](CHANGELOG.md).

Interface réorganisée en **onglets de fonctionnalité** (Génération + Supports
pédagogiques : 8 types de supports de révision générés à partir du document
consolidé et du glossaire) ; identité projet réduite à nom + emplacement, réglages
par fonctionnalité.

Export des supports en **Anki `.apkg`** (flashcards / cloze / QCM, ré-import sans
doublon), **Markdown**, **PDF** et **HTML** (documents autonomes, sujet / corrigé
séparés).

830 tests passants, `mypy --strict` et `ruff` propres sur 321 fichiers.

## Licence

Propriétaire.
