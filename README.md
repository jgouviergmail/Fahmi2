# Fahmi2

Application desktop Windows qui transforme des vidéos de cours oraux (MP4) en
documents Markdown structurés (fidélité au discours, reformulation soignée,
glossaire, document consolidé multilingue FR/EN).

> **Statut** : v1 en cours de développement. Voir
> [docs/superpowers/specs/](docs/superpowers/specs/) pour le design détaillé
> et [docs/superpowers/plans/](docs/superpowers/plans/) pour les plans
> d'implémentation.

## Public visé

- Un enseignant produisant régulièrement des vidéos de cours et souhaitant
  les transformer en supports écrits structurés réutilisables.
- Utilisateur non-expert : tout est paramétrable via l'interface graphique,
  aucune édition de fichier n'est nécessaire au quotidien.

## Capacités v1

- Pipeline **8 phases** robuste (extraction audio → STT → 7 phases LLM
  cohérentes) avec **checkpointing fin** : aucun travail perdu en cas
  d'interruption.
- 2 providers STT : **faster-whisper-large-v3-turbo** local (GPU NVIDIA
  requis) ou **OpenAI Whisper** cloud.
- 2 modèles LLM **DeepSeek v4** : `deepseek-v4-flash` (rapide/économique) ou
  `deepseek-v4-pro` (capacité supérieure). Activation du mode `thinking` et
  température configurables **par phase**.
- 2 langues de sortie supportées : **FR** et **EN** — le document est
  produit dans la langue source puis traduit pour les autres.
- 4 styles de rendu : décontracté / standard / professionnel / académique +
  directives libres.
- **Estimation pré-run** du coût + **plafond budget** avec arrêt propre.
- **Concept de Projet persistant** avec historique de runs et reprise.
- **Stockage chiffré** des clés API via Windows DPAPI.
- **Logs structurés** JSONL + panneau temps réel filtrable.

## Installation (utilisateur final)

1. Télécharger `Fahmi2-<version>-win64.zip` (cf. [Packaging](#packaging))
2. Décompresser dans un dossier de votre choix (ex: `C:\Apps\Fahmi2\`)
3. Double-cliquer sur `Fahmi2.exe`
4. Au 1er lancement, **SmartScreen** Windows affichera un avertissement :
   cliquer *« Plus d'infos »* → *« Exécuter quand même »* (une seule fois)

Les données (projets, paramètres, clés API chiffrées) sont stockées
automatiquement dans `%APPDATA%/Fahmi2/`. Aucune installation système requise.

## Démarrage rapide

1. **Configurer les clés API** : menu *Édition* → *Paramètres globaux* :
   - Clé OpenAI (pour STT cloud)
   - Clé DeepSeek (pour les phases LLM)
2. **Créer un projet** : menu *Fichier* → *Nouveau projet* :
   - Nom du projet
   - Dossier d'entrée contenant les vidéos MP4
   - Langue source du contenu (FR/EN)
   - Langues de sortie demandées (cochez celles désirées)
   - Style de rendu + directives libres
   - Provider STT (cloud recommandé sans GPU NVIDIA)
   - Modèle LLM (flash recommandé pour démarrer)
   - Plafond budget optionnel
3. **Lancer le projet** : sélectionner le projet dans la sidebar, cliquer
   sur *« ▶ Lancer »*. La matrice vidéos × phases se remplit en temps réel.
4. **Récupérer les livrables** : à la fin du run, ouvrir le dossier de sortie
   (par défaut `<dossier_entrée>/.fahmi2/output/`). On y trouve :
   - `consolidated.{lang}.md` — document consolidé par langue
   - `glossary.{lang}.md` — glossaire par langue
   - `per-video/{lang}/{video_id}.md` — un document par vidéo et par langue

## Mise à jour

1. Télécharger la nouvelle version `.zip`
2. Fermer Fahmi2 si ouvert
3. Décompresser le nouveau `.zip` (peut écraser l'ancien dossier)
4. Relancer `Fahmi2.exe`

Les données utilisateur sont automatiquement préservées et migrées si
nécessaire.

## Pour les développeurs

### Pré-requis

- Python **3.11 ou 3.12** (pas 3.13 pour l'instant)
- Windows 11 (10 minimum) pour tester DPAPI
- ffmpeg dans le PATH (pour les tests qui touchent à l'extraction audio)
- GPU NVIDIA + CUDA (optionnel, pour tester STT local)

### Installation

```powershell
git clone <url>
cd Fahmi2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pre-commit install
```

### Tests

```powershell
pytest                                  # toute la suite
pytest tests/unit                       # unitaires
pytest tests/e2e                        # end-to-end
pytest --cov=src/fahmi2 --cov-report=html  # couverture
```

### Linter / type checker

```powershell
ruff check .
ruff format .
mypy src tests
```

### Lancer l'app en mode dev

```powershell
python -m fahmi2.ui.app_main
```

## Packaging

Cf. [packaging/README.md](packaging/README.md) pour la procédure complète
(PyInstaller `--onedir`, bundle ffmpeg, génération du `.zip` portable).

## Architecture

Architecture en couches inspirée des principes hexagonaux :

```
src/fahmi2/
├── core/         # logging, errors, retry, config, migrations, retrieval, ids
├── domain/       # entités pures (Project, Run, PhaseExecution, Glossary, …)
├── pipeline/     # PipelineEngine + 8 handlers de phase
├── infra/        # adapters (STT, LLM, ffmpeg, SQLite WAL, DPAPI, prompts)
├── app/          # use-cases (ProjectService, RunOrchestrator, CostEstimator…)
└── ui/           # PySide6 (MainWindow, widgets, dialogues, QtEventBus)
```

Voir [docs/superpowers/specs/2026-05-19-fahmi2-design.md](docs/superpowers/specs/2026-05-19-fahmi2-design.md)
pour le design complet.

## Licence

Propriétaire.
