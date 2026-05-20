# Fahmi2

> Transformez des vidéos de cours oraux (MP4) en documents Markdown
> structurés, glossaire compris, multilingue, en quelques heures et sans
> intervention manuelle.

Application desktop Windows, mono-utilisateur, **installation en double-clic**
(aucune dépendance système à installer, ffmpeg bundlé). Pipeline en 8 phases
(transcription Whisper + 7 phases LLM DeepSeek v4), entièrement
paramétrable via l'interface graphique.

## Capacités v0.2

- 2 langues de sortie : **français** et **anglais**.
- 2 providers STT : **faster-whisper-large-v3-turbo** local (GPU NVIDIA) ou
  **OpenAI Whisper** cloud.
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
| [Plans d'implémentation](docs/superpowers/plans/) | Détail des 12 jalons |
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
7. Onglet **Génération → ⚙ Réglages** : choisir le dossier des vidéos, les
   langues, le style, le modèle ; valider.
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

**v0.2.0** (alpha+) — pipeline complet fonctionnel, UI cockpit dense
thème Clair Fluent, packaging Windows portable opérationnel, document
consolidé navigable (numérotation hiérarchique + sommaire), glossaire
en tableau avec colonne Signification, édition des prompts depuis l'UI,
estimation de coût alignée sur l'usage réel (thinking pris en compte).
Cf. [CHANGELOG.md](CHANGELOG.md).

Interface réorganisée en **onglets de fonctionnalité** (Génération + Supports
pédagogiques : 9 types de supports de révision générés à partir du document
consolidé et du glossaire) ; identité projet réduite à nom + emplacement, réglages
par fonctionnalité.

Export **Anki `.apkg`** des supports (flashcards / cloze / QCM, ré-import sans
doublon).

628 tests passants, `mypy --strict` et `ruff` propres sur 268 fichiers.

## Licence

Propriétaire.
