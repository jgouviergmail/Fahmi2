# Fahmi2

> Transformez vos cours — **vidéos, fichiers audio, liens YouTube ou documents
> texte** (PDF, Word, Markdown, txt) — en un **document Markdown consolidé et
> structuré** (reformulé, chapitré, **glossaire**, **multilingue** : français,
> anglais, allemand, espagnol, italien, chinois, arabe),
> assemblé **dans l'ordre** des sources ou par **refonte thématique** transversale.
> Puis exploitez ce corpus sans effort : **supports de révision** (flashcards,
> QCM, fiches, examen blanc…, exports Anki/PDF/HTML/Word) et **Dialogue** (chat ancré
> sur le cours, réponses **citées**). Le tout en **quelques minutes** et **sans
> intervention manuelle**.

Application desktop Windows, mono-utilisateur, **installation en double-clic**
(aucune dépendance système à installer, ffmpeg bundlé). Interface organisée en
**onglets de fonctionnalité** — **Génération** · **Supports pédagogiques** ·
**Dialogue**. La génération repose sur un pipeline en 8 phases (ingestion
polymorphe — transcription Whisper ou extraction de texte — puis 7 phases LLM
DeepSeek v4), entièrement paramétrable via l'interface graphique.

## Capacités

- **Entrées polymorphes** : vidéos (MP4, MKV, MOV, WebM…), fichiers audio (WAV,
  MP3, M4A, FLAC, OGG…), **liens YouTube** (vidéos unitaires ; l'audio est
  téléchargé par yt-dlp) et **documents texte** (PDF, Word, Markdown, txt —
  reformulés comme une transcription orale, ou insérés tels quels). Sources
  mixtes acceptées dans un même projet.
- **Ordre & exclusion des sources** : l'ordre de traitement (donc l'ordre des
  chapitres du document final) est réglable par glisser-déposer ; toute source
  peut être exclue puis réincluse.
- **Mode de consolidation** : **ordonné** (1 source = 1 chapitre, contenu recopié
  dans l'ordre choisi) ou **refonte thématique** — le LLM agrège et restructure
  transversalement les contenus de tous les entrants par thème, à la manière d'une
  synthèse journalistique (rigueur sur le fond : aucun fait inventé, conflits entre
  sources présentés ; souplesse sur la forme : fusion, déduplication, transitions).
- 7 langues de sortie : **français**, **anglais**, **allemand**, **espagnol**,
  **italien**, **chinois**, **arabe** (STT, glossaire, supports et Dialogue
  inclus). Note : pour le chinois, le Dialogue privilégie le retrieval **sémantique**
  (la recherche lexicale est peu adaptée aux langues sans espaces).
- 2 providers STT (**modèle configurable par provider**) : **faster-whisper**
  local (GPU NVIDIA ; `large-v3-turbo` par défaut, ou `large-v3`/`medium`/`small`,
  téléchargés à la demande) ou **OpenAI** cloud (`whisper-1` par défaut, ou
  `gpt-4o-transcribe`/`gpt-4o-mini-transcribe`) — ce dernier gère **toute durée de
  cours** (compression Opus + découpage aux silences automatiques pour franchir la
  limite des 25 Mo d'OpenAI, de façon transparente).
- 2 modèles LLM : **DeepSeek v4 Flash** (économique) ou **Pro** (capacité
  supérieure). Mode raisonnement (`thinking` + `reasoning_effort`
  HIGH/MAX) et température configurables **par phase**.
- **Dialogue (chat ancré sur le corpus)** : pose des questions en langage naturel
  sur un cours généré. Réponses **citées** (chapitre › section, cliquables) et
  **diffusées en streaming**, mode **strict** (corpus seul, refus hors-corpus) ou
  **augmenté**. Retrieval **lexical** (TF-IDF, hors-ligne) ou **sémantique**
  (embeddings OpenAI, **modèle configurable**) avec stratégie **AUTO** + expansion
  de requête. Conversations multiples **persistées et supprimables** ; **coût
  cumulé exhaustif** (réponse + embeddings + reformulation).
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
- **Traitement parallèle** : sources (phases per-source) et supports pédagogiques
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

**v1.4.0** — **5 langues supplémentaires** (allemand, espagnol, italien, chinois,
arabe → **7 au total**, en entrée comme en sortie, pour les 3 fonctionnalités) ;
**export Word (`.docx`)** pour la Génération et les Supports pédagogiques ; **rendu
PDF du chinois** (police Microsoft YaHei, coupe de ligne automatique) **et de
l'arabe** (droite-à-gauche + liaison contextuelle, y compris en Word) ;
**localisation terminologique du glossaire** par langue cible (phase 6) ;
**normalisation du rendu des tableaux** (Markdown/PDF/HTML/DOCX).

**v1.3.0** — **mode de consolidation « refonte thématique »** (le LLM agrège et
restructure transversalement les contenus par thème, à côté du mode ordonné par
défaut ; rigueur sur le fond / souplesse sur la forme) ; le **Dialogue recharge
automatiquement** son corpus après régénération (plus de citations périmées) ; la
**suppression d'un projet** efface aussi son dossier workspace sur disque. v1.2.0 :
nouvel onglet **Dialogue** (chat ancré sur le corpus : réponses citées + streaming,
retrieval lexical/sémantique, coût exhaustif, conversations persistées/supprimables) ;
**modèles configurables** (LLM, embeddings, STT) ; plafond de sortie au maximum du
modèle (anti-troncature) sur **tous** les appels DeepSeek. v1.1.0 : entrants élargis
(**vidéos, audio, YouTube, documents texte**)
avec ordre/exclusion des sources. Socle v1.0.0 : pipeline complet, UI cockpit
thème Clair Fluent, packaging Windows portable, document consolidé navigable,
glossaire en tableau, édition des prompts, estimation de coût alignée sur l'usage.
Cf. [CHANGELOG.md](CHANGELOG.md).

Interface réorganisée en **onglets de fonctionnalité** (Génération + Supports
pédagogiques : 8 types de supports de révision générés à partir du document
consolidé et du glossaire + **Dialogue** : chat conversationnel ancré sur le
corpus, réponses citées et diffusées en streaming, retrieval lexical ou
sémantique) ; identité projet réduite à nom + emplacement, réglages
par fonctionnalité.

Export des supports en **Anki `.apkg`** (flashcards / cloze / QCM, ré-import sans
doublon), **Markdown**, **PDF**, **HTML** et **Word (`.docx`)** (documents
autonomes, sujet / corrigé séparés). Le rendu PDF gère le **chinois** (police
Microsoft YaHei système, retours à la ligne automatiques) et l'**arabe**
(droite-à-gauche + liaison contextuelle) ; le **glossaire** s'exporte en paysage
(PDF et Word).

1053 tests passants, `mypy --strict` et `ruff` propres sur 389 fichiers.

## Licence

Propriétaire.
