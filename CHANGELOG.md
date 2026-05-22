# Changelog

Toutes les évolutions notables du projet Fahmi2.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et le projet adhère à [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Non publié]

### Ajouté — Export documentaire de la Génération

- Nouveau bouton **Exporter** dans l'onglet Génération : écrit le **document
  consolidé** et le **glossaire** (un fichier par langue) en **Markdown / PDF /
  HTML** vers un dossier choisi. Formats configurables dans **⚙ Réglages → Export**
  (`GenerationSettings.export_formats`, **opt-in** : aucun coché par défaut).

### Modifié — Export des supports pédagogiques (granularité)

- Les exports **Markdown / PDF / HTML** produisent désormais **un fichier par
  support et par corrigé** (`<support>.<langue>.<ext>` /
  `<support>.<langue>.corrige.<ext>`), au lieu d'un document agrégé par langue.
  Chaque HTML est un document autonome. L'export **Anki `.apkg`** est inchangé.
- **Factorisation** : cœur d'écriture partagé `app/document_export.py`
  (`write_documents`) + helper UI `ui/_export_ui.py` ; `infra/export/markdown_pdf`
  devient un pur *renderer* (suppression de `assemble_markdown`).

### Corrigé — STT cloud (OpenAI Whisper) : fichiers volumineux & langue

- **Support des fichiers > 25 Mo** : l'audio est désormais **compressé en Opus**
  (24 kbps mono) avant l'envoi à OpenAI, et **découpé aux silences** si nécessaire
  (cours > ~2 h), puis les transcriptions sont recollées. Le STT cloud fonctionne
  donc pour **toute durée** de cours (la limite OpenAI de 25 Mo plafonnait l'audio
  brut à ~13 min). Bénéfice : l'upload est **bien plus rapide** (un WAV de 22 Mo
  → Opus ~3 Mo), ce qui supprime la lenteur qui pouvait passer pour un blocage.
- **Langue détectée** : correction du parsing de la langue renvoyée par OpenAI
  Whisper (nom complet « french » au lieu du code ISO « fr »), qui faisait
  échouer toute transcription cloud.
- **Robustesse** : timeout client OpenAI explicite ; encodeur `libopus` garanti
  dans le ffmpeg bundlé (vérifié au build).

### Ajouté — Parallélisation des traitements (génération + pédagogie)

- **Supports pédagogiques en parallèle** : l'orchestrateur traite les unités
  *(langue × support)* concurremment via un pool de threads borné. Nouveau réglage
  **« Tâches en parallèle »** (`llm_workers`, défaut 16, plage 1–64).
- **Pipeline de génération parallélisé** : les phases **par vidéo** (STT cloud,
  extraction de termes, reformulation, structuration) sont traitées concurremment ;
  les phases finales parallélisent la traduction *(langue × document)*, la passe de
  cohérence *(par langue)* et les résumés de consolidation. Réglages
  **« Transcriptions en parallèle »** (`stt_cloud_workers`, défaut 3, plage 1–8) et
  **« Appels LLM en parallèle »** (`llm_workers`, défaut 16, plage 1–64). Le STT
  **local** reste séquentiel (1 GPU). Le déterminisme des documents et les points de
  reprise (checkpoint) sont préservés ; le plafond de coût est *best-effort* en
  parallèle (léger dépassement possible par les requêtes déjà en vol).
- **Timeout client DeepSeek** porté à 600 s (absorbe les requêtes lentes sous
  keep-alive serveur).

### Ajouté — Sidebar : statut par projet & bouton « Réinitialiser »

- **Icônes de statut dans la sidebar** : chaque projet est préfixé par le statut du
  dernier run de **génération** (G) puis de **pédagogie** (P) — ex. `G ✓ / P ▶  Nom` —,
  rafraîchies en direct quand un run démarre ou se termine (infobulle détaillée).
- **Bouton « Réinitialiser »** (par onglet) : supprime tout ce qui a été généré pour
  la fonctionnalité — livrables disque **et** historique en base (runs/phases) pour
  la génération ; dossier des supports (artefacts + manifeste + état) pour la
  pédagogie. Confirmation obligatoire ; désactivé pendant un run.

### Ajouté — Dashboards : homogénéité génération / pédagogie

- **Statut d'exécution pédagogie persisté** (`pedagogy/run_state.json`) : la
  pédagogie expose désormais un `RunStatus` homogène avec la génération (créé / en
  cours / terminé / échec / annulé / pause), persisté sur disque (l'orchestrateur
  l'écrit `RUNNING` au démarrage puis le statut final), donc lisible hors session.
- **Dashboard pédagogie** : la tuile **Statut** affiche « En cours » pendant la
  génération ; nouvelle **tuile Durée** (rafraîchie en direct).
- **Dashboard génération** : nouvelle **tuile Langues** (langues de sortie).

### Modifié — Pédagogie : régénération alignée sur la génération

- **Relancer régénère** : « Générer » sur un ensemble de supports **complet** (tous
  présents et à jour) les **régénère** (écrase), comme relancer la Génération après
  un run terminé — au lieu de tout skipper (qui donnait une impression de blocage).
  Un ensemble **incomplet** (interruption, plafond atteint) reste **repris** (les
  supports frais sont conservés, seuls les manquants sont générés). Le bandeau
  « Supports à jour » indique désormais que relancer les régénère.

### Modifié — Pédagogie : exports & langue (retours d'usage)

- **Ordre pédagogique des exports** (Markdown / PDF / HTML) : les documents agrégés
  présentent d'abord les supports d'**apprentissage** du plus général au plus précis
  (fiche → points clés → flashcards), puis les **exercices** du plus précis au plus
  général (cloze → vrai/faux → QCM → questions ouvertes → examen blanc).
- **Langue de sortie renforcée (tous les supports)** : les **8 prompts** de
  supports insistent désormais pour rédiger **intégralement dans la langue cible**
  (traduire le contenu source au lieu de le recopier, ne pas recopier les
  formulations sources) — généralise à tous les types (QCM, vrai/faux, cloze,
  questions ouvertes, examen blanc, flashcards, fiche, points clés) ce qui était
  partiel ; corrige des supports restés dans la langue du document quand la langue
  cible différait.

### Corrigé — Export PDF : couleur des titres

- Les **titres** du PDF sont désormais en **noir gras** (au lieu du rouge `#960000`
  par défaut de fpdf2) et les **puces** en gris foncé — rendu plus sobre et lisible.

### Ajouté — Export HTML & section dédiée

- **Export HTML** : nouveau format d'export des supports — un document HTML
  **autonome** (UTF-8, feuille de style intégrée) ouvrable dans un navigateur,
  agrégé par langue (sujet / corrigé séparés).
- **Section « Export » dédiée** dans les réglages pédagogie : les formats d'export
  (Anki / Markdown / PDF / HTML) ont leur propre catégorie, déplacés hors de
  « Modèle & coût ».

### Corrigé — Panneau de logs : filtre de niveau

- Le sélecteur **« Niveau minimum »** re-filtre désormais l'**affichage existant**
  (et plus seulement les nouveaux events) : monter le seuil masque les lignes sous
  le niveau, le rebaisser les fait réapparaître (tous les events sont conservés).

### Modifié — Pédagogie : qualité & mise en forme des supports

- **Mise en forme enrichie** : les supports exploitent davantage le Markdown
  (fiches et examens aérés — sous-titres, listes, paragraphes séparés ; flashcards
  et justifications mieux structurées). L'export **Anki** convertit désormais le
  Markdown des champs en **HTML** (listes/gras rendus proprement) ; les exports
  Markdown et PDF sont inchangés. Le texte des cartes à trous (cloze) reste brut
  (mécanique de trous préservée).
- **Prompts affinés (pertinence)** : directives ciblées par type de support
  (distracteurs homogènes et non devinables en QCM ; affirmations non triviales en
  vrai/faux ; trous sur notions porteuses en cloze ; questions d'analyse en
  questions ouvertes ; points clés hiérarchisés ; examen à difficulté progressive),
  pour des contenus plus pertinents. Les overrides `%APPDATA%/Fahmi2/prompts/`
  restent prioritaires.

### Corrigé — Pédagogie : langue & dashboard (retours d'usage)

- **Langue cible non bloquante** : on peut générer des supports dans une langue
  (ex. EN) même si la Génération n'a produit qu'une autre langue (ex. FR) — le LLM
  rédige dans la langue cible à partir du contenu disponible. Le bandeau d'état ne
  bloque plus dès qu'**au moins un** document consolidé existe (toute langue). La
  fraîcheur suit le mtime du **document de contenu réellement utilisé** (plus de
  faux « périmé » pour un support généré depuis une autre langue). Logique de
  résolution de langue de contenu centralisée (`pedagogy/sources.resolve_content_language`,
  partagée par l'orchestrateur et le bandeau d'état).
- **Dashboard pédagogie reconstruit à la sélection** : revenir sur un projet déjà
  généré réaffiche l'**état de la dernière exécution** (supports terminés + coût,
  lus depuis les artefacts disque) au lieu d'une grille vide — à parité avec le
  dashboard Génération.

### Corrigé — Revue de code (cohérence dashboards)

- **Tuile « Coût » pédagogie** : affiche désormais le **plafond** et l'**accent
  visuel** (warning ≥ 80 %, danger ≥ 100 %), à parité avec le dashboard Génération.
- **Prévisualisation pédagogie** : à la sélection d'un projet configuré, la matrice
  supports × langues s'affiche **en attente** (au lieu d'une grille vide), cohérent
  avec l'aperçu des vidéos détectées côté Génération.
- **DRY / cohérence** : libellés et accents des statuts de Run centralisés
  (`ui/status_labels`, partagés par les deux bandes de tuiles) ; ordre **canonique**
  des supports dans le dialogue d'estimation ; gras réservé aux **totaux** de la
  matrice ; matrice passée en lecture seule (plus de surlignage de sélection partiel) ;
  constantes de dimensions de `CostMatrixView` centralisées.
- **Documentation** : `docs/02` et `CLAUDE.md` réalignés (suppression de
  `glossary_terms` / `GlossaryReconciler`, ajout des composants partagés
  `CostMatrixView` / `StatCard` / `cost_matrix`).

### Modifié — Estimation de coût (Lot 3d)

- **Estimation pré-run granulaire + fourchette** : le dialogue « Estimer le coût »
  décompose le budget **par phase** (génération) / **par support** (pédagogie) et
  affiche le total sous forme de **fourchette ±33 %** (« estimation indicative » :
  `≈ $X` + `fourchette $low – $high`), avec un **avertissement** si le haut de
  fourchette peut dépasser le plafond. Les deux dialogues partagent le même rendu
  (`ui/cost_estimate_dialog`). `CostEstimation.per_phase_usd` et
  `low_usd`/`high_usd` ajoutés (constante partagée `ESTIMATE_UNCERTAINTY_RATIO`).

### Modifié — Dashboard génération (Lot 3c)

- **Matrice Génération migrée vers le composant partagé `CostMatrixView`** :
  affiche désormais le **coût par cellule** (phase × vidéo, discret) et les
  **totaux** (par vidéo, par phase, général). Les phases batch portent leur coût
  dans le total de colonne (coût au niveau du run). Nouvelle requête
  `SqliteState.list_phase_cells` (statut + coût par phase × vidéo). L'ancien widget
  `RunMatrixView` et le QSS `#runMatrix` sont supprimés.

### Modifié — Dashboard pédagogie (Lot 3b)

- **Dashboard Supports pédagogiques aligné sur la Génération** : la table plate
  est remplacée par une **bande de tuiles** (Statut / Supports / Langues / Coût) et
  une **matrice 2D supports × langues** (statut + coût par cellule + totaux, via
  `CostMatrixView`). Le **bandeau de fraîcheur** est conservé.

### Ajouté — Briques UI partagées dashboards (Lot 3a)

- **`CostMatrixView`** (+ viewmodel `CostMatrixSnapshot`) : matrice de coût
  générique (lignes × colonnes) où chaque cellule porte **statut + coût**, avec
  **totaux** (ligne / colonne / général). Socle commun aux dashboards Génération et
  Pédagogie (cohérence + DRY). Coût par cellule rendu en secondaire (petit, gris),
  totaux mis en avant.
- **`StatCard`** : carte d'indicateur réutilisable extraite de `stats_strip`
  (icône + valeur + sous-info + accent), socle des bandes de tuiles des deux
  dashboards. Aucun changement de rendu de la bande Génération existante.

### Supprimé — Pédagogie (Lot 1c)

- **Support `flashcards_glossary` retiré** : c'était le glossaire reformaté en
  cartes (valeur de transformation quasi nulle). La pédagogie compte désormais
  **8 types de supports** (tous LLM). Le glossaire reste un document de référence
  et alimente l'injection terminologique des prompts. Les réglages persistés
  référant l'ancien support sont tolérés (type inconnu ignoré à la lecture).

### Modifié — Pédagogie (Lot 1c)

- **Langues des supports découplées de la génération (#4)** : l'onglet propose
  **toutes** les langues supportées ; les supports sont rédigés par le LLM dans la
  langue choisie même si le document source est dans une autre langue.
  L'orchestrateur résout une langue de contenu (doc consolidé existant : la cible,
  sinon la langue source, sinon la première produite) distincte de la langue cible.

### Corrigé — Glossaire homogène (Lot 1b)

- **Flashcards de glossaire vides / injection terminologique vide** : la pédagogie
  lit désormais le glossaire **sur disque** (`glossary_master.json`), exactement
  comme le pipeline (`load_glossary_master`), au lieu d'une table SQLite jamais
  peuplée. Les générateurs LLM reçoivent à nouveau les termes dans leurs prompts.

### Supprimé — Glossaire homogène (Lot 1b)

- **Anomalie de persistance du glossaire** : suppression de la table SQLite
  `glossary_terms` (migration `DROP TABLE` idempotente), des méthodes
  `upsert_glossary_term` / `list_glossary_terms`, et du service mort
  `GlossaryReconciler`. Le parsing du glossaire master et le rendu Markdown
  (`parse_glossary_master_terms`, `render_glossary_markdown_table`) remontent dans
  `domain/glossary.py` (réutilisés par pipeline et pédagogie). Aucun document
  généré n'a de table de contenu en DB : le glossaire suit le même traitement
  (artefact disque + `PhaseExecution`).

### Ajouté — Finitions UI (Lot 1a)

- **Conserver l'audio** : nouvelle case « Conserver les fichiers audio extraits »
  dans Réglages → Transcription (décochée par défaut = suppression après STT,
  comportement inchangé ; cocher conserve les `.wav`). Câblée sur le champ existant
  `GenerationSettings.delete_audio_after_stt`.

### Corrigé — Finitions UI (Lot 1a)

- **Visibilité des onglets** : la barre d'onglets de fonctionnalité (Génération /
  Supports pédagogiques) est désormais stylée (QSS) — l'onglet inactif est
  distinct (fond gris clair), l'onglet sélectionné est blanc avec un soulignement
  accent. Auparavant les onglets inactifs se fondaient dans le fond.

### Corrigé — Revue de code (SP1–SP3)

- **Export Anki** : les tags sont désormais assainis (les espaces deviennent `_`).
  Un terme de glossaire multi-mots (« Intelligence artificielle ») ne fait plus
  échouer l'export `.apkg` (`genanki` refuse les tags contenant un espace).
- **Suppression d'un projet** : tous les onglets sont notifiés
  (`MainWindow.notify_project_deleted`) — l'onglet Supports pédagogiques ne
  conserve plus une référence au projet supprimé (qui pouvait le **ressusciter**
  en base lors d'un enregistrement de réglages).
- **Réglages de génération** : modifier la génération ne **perd plus** les réglages
  Supports pédagogiques (reconstruction du `Project` via `with_generation`).
- **Formats d'export** : le menu « 📦 Exporter » ne propose plus que les formats
  **réellement cochés** dans les réglages (`PedagogySettings.export_formats`).
- **Robustesse parsing LLM** : un QCM/cloze de schéma invalide (index hors borne,
  trop de propositions, réponses vides) lève une `LLMError` typée au lieu d'une
  exception non gérée ; `read_artifact` ignore proprement un artefact d'item
  corrompu (retourne `None`).
- **Plafond de coût pédagogie** : le statut `PAUSED` est désormais documenté et le
  journal indique explicitement « plafond de coût atteint ».
- **Divers** : menu « ? → À propos » fonctionnel (nom + version) ; libellé
  « Formats d'export » dans les réglages ; helper d'ouverture de dossier mutualisé
  (`ui/_file_explorer`) ; suppression de magic numbers (estimateur de coût).

### Ajouté — Export Markdown / PDF (SP3/02)

- **Export Markdown et PDF** des supports depuis l'onglet pédagogique : le bouton
  « 📦 Exporter » propose désormais 3 formats (Anki / Markdown / PDF).
- Documents **agrégés par langue**, **sujet / corrigé séparés** (`supports.{lang}.md`,
  `supports.{lang}.corrige.md`, et variantes `.pdf`).
- Rendu PDF pur-python (`markdown` → HTML → `fpdf2`) avec police Unicode système ; repli
  Markdown si aucune police n'est résolue. Nouvelles dépendances **`markdown`**, **`fpdf2`**.

### Ajouté — Export Anki `.apkg` (SP3/01)

- **Export Anki** depuis l'onglet pédagogique (bouton « 📦 Exporter ») : les supports
  générés sont convertis en paquet `.apkg` (genanki) — flashcards (glossaire + concepts)
  → note **Basic**, textes à trous → note **Cloze**, QCM → note **custom**.
- **GUID stables** (ré-import sans doublon), **sous-decks par support**
  (`<Projet>::<support>`), **tags** (support, langue, niveau, chapitre).
- Adapter `infra/anki/genanki_exporter.py`, désérialisation `pedagogy/artifact_reader.py`,
  service `app/pedagogy_export.py`. Nouvelle dépendance **`genanki`**.

### Ajouté — Onglet Supports pédagogiques (SP2/04)

- **Onglet pédagogique réel** (remplace le stub) : barre d'actions (Réglages,
  Estimer, Générer, Pause/Reprendre/Annuler, Ouvrir le dossier), **bandeau d'état**
  (non configuré / génération requise / prêt / à jour / périmé) et **table de
  progression** (support × langue, statut, coût).
- **Réglages master-detail** (`PedagogySettingsView`) : Supports (+ corrigé séparé),
  Difficulté (public, Bloom, densité, directives), Langues (produites), Modèle & coût
  (modèle, thinking, température, plafond, formats d'export).
- **Estimation de coût** (`PedagogyCostEstimator`) par support × langue × chapitre
  selon densité et thinking ; **plafond de coût** appliqué par l'orchestrateur
  (arrêt propre à la frontière sûre).
- **`PedagogyController`** (worker `QThread`, pause/annulation) + **`PedagogyQtEventBus`**
  bridgeant les événements vers la table de progression et le panneau de logs.
- Viewmodels testables sans Qt (`PedagogyProgressViewModel`, `PedagogyStateViewModel`),
  helpers `pedagogy/sources.py` + heuristiques de coût partagées `app/_cost_common.py`.

### Corrigé

- L'édition d'un projet (renommage) n'efface plus les réglages **Supports
  pédagogiques** (`Project.pedagogy`).

### Ajouté — Générateurs de supports LLM (SP2/03)

- **8 générateurs LLM** : flashcards concepts, QCM, vrai/faux, cloze, questions
  ouvertes, fiche de révision, points clés (par chapitre) et examen blanc
  (document entier). Chacun parse une réponse **JSON typée** vers les entités de
  `domain/supports.py` et rend du Markdown.
- **8 prompts `pedagogy_*.j2` éditables** via « Édition → Modifier les prompts »
  (catalogue `PromptsService`), paramétrés par public cible, objectif Bloom,
  densité, directives et glossaire.
- **Corrigés séparés** : les supports évaluatifs marqués « corrigé séparé »
  produisent un fichier `<support>.corrige.md` distinct du sujet.
- **Dé-biaisage QCM** déterministe (répartition de la position de la bonne
  réponse sur l'ensemble des questions).
- **Retry LLM** mutualisé avec le pipeline : `default_classify` remonté dans
  `core/retry/classification.py` ; événement `SupportRetryAttempt`.
- Socle `pedagogy/generators/_base.py` (bases génériques par chapitre + mixin
  évaluatif), factory `build_default_support_registry()` (9 générateurs).

### Ajouté — Générateur de supports de révision (SP2/02)

- **Socle pédagogie** (`pedagogy/`) : `SupportGenerator` (ABC) + `SupportContext` (DI),
  `SupportGeneratorRegistry` (ordre canonique des 9 supports), parseur de chapitres du
  document consolidé, events pédagogie, **manifeste de fraîcheur** (`pedagogy/manifest.json`)
  et sérialisation d'artefacts.
- **Orchestrateur dédié léger** `SupportsOrchestrator` (`app/`) : génération par
  langue × support, écriture JSON + Markdown sous `<emplacement>/pedagogy/`, events,
  **reprise coarse** (skip des supports frais), pause/annulation.
- **Première tranche verticale** : générateur **flashcards glossaire** (sans LLM,
  recto = terme/acronyme, verso = définition), depuis le glossaire du dernier run
  *COMPLETED*.
- **Helpers LLM/JSON généralisés** (`infra/llm/invocation.py`) réutilisés par les
  handlers de phase ; `EventBus` rendu **générique** (`EventBus[E]`) pour porter aussi
  les événements pédagogie.
- `ProjectService.get_last_completed_run` + `create_project(pedagogy=…)` ; constantes
  de chemins centralisées (`GENERATION_OUTPUT_SUBDIR`, `consolidated_doc_filename`).

### Corrigé

- Un run de **génération** n'efface plus les réglages **Supports pédagogiques**
  (`Project.pedagogy`) à sa fin (régression introduite par SP2/01).

### Modifié — Coquille multi-fonctionnalités (SP1)

- **Interface à onglets** : la zone projet est désormais une `QTabWidget` peuplée
  par un `FeatureRegistry` — onglet **Génération** (cockpit existant) + onglet
  **Supports pédagogiques** (*stub*, à implémenter).
- **`Project` réduit à l'identité** (nom + emplacement, immuable) ; les paramètres
  métier vivent dans `GenerationSettings` (extrait de l'ancien `ProjectSettings`).
- **Création de projet minimale** (nom + emplacement) ; réglages de génération
  édités depuis l'onglet **Génération → ⚙ Réglages** (vue master-detail réutilisable
  `SettingsView`).
- **Workspace par fonctionnalité** : les artefacts de génération vivent sous
  `<emplacement>/generation/` (livrables sous `…/generation/output/`).
- **Persistance** : blob `projects.settings_json` en **v2**
  (`{version, workspace_folder, generation, pedagogy}`) avec migration *lenient*
  v1→v2 à la lecture (aucun déplacement de fichier).
- **Interne** : `RunController` → `GenerationController` (découplé du `MainWindow`) ;
  nouveau package `ui/features/`.

## [0.2.0] — 2026-05-19

Itération majeure UI + qualité de rendu du document consolidé + édition
des prompts + précision de l'estimation de coût.

### Ajouté

#### UI — thème et cockpit
- **Thème Clair Fluent** (Windows 11) : feuille de style QSS globale
  cohérente (palette accent `#0078d4`, surfaces blanches sur fond
  `#f5f7fb`), `QCheckBox::indicator` stylisé avec glyphe ✓ SVG inline.
- **StatsStrip refondu en 5 cartes** : Statut, Vidéos, Phases, Durée,
  Coût. Chaque carte = icône + titre + valeur en grand + sous-info. La
  carte **Durée** est mise à jour en direct chaque seconde par un
  `QTimer` interne tant que le Run est `RUNNING` ou `PAUSED`.
- **Run matrix colorée** : pastilles colorées par `PhaseStatus` (vert
  ✓, bleu ▶, gris ·, rouge ✗, indigo ↷), en-têtes courts lisibles
  (STT, Termes, Glossaire, Reformul., Structur., Consolid., Traduction,
  Cohérence), alignement centré.
- **Logs colorés par sévérité** (INFO gris, WARN orange, ERREUR rouge,
  FATAL rouge gras), heure compacte `HH:MM:SS`, monospace.
- **ProjectHeaderBar** : titre projet 17 px gras, boutons typés
  primary / default / danger avec hover et curseur pointer.

#### Document consolidé — élégance et navigation
- **Numérotation hiérarchique** : `# 1. Titre`, `## 1.1 Section`,
  `### 1.1.1 Sous-section`. Les numérotations LLM existantes
  (`1. `, `1.2 `, `1.2.3 - `, `1) `) sont décapées avant réécriture.
  Les blocs ``` ``` ``` sont préservés.
- **Sommaire automatique** complet (chapitres + `##` + `###`) avec
  ancres GFM cliquables et indentation hiérarchique.
- **Admonitions élégantes** : `[!NOTE]` / `[!TIP]` / `[!IMPORTANT]`
  remplacés par blockquote + emoji (📝 Remarque, 💡 Exemple, 📖
  Définition, 🎯 Exercice).

#### Glossaire — colonne expansion d'acronyme
- **Format tableau Markdown** : `| Terme | Acronyme | Signification |
  Définition |` (FR) / `| Term | Acronym | Meaning | Definition |`
  (EN).
- **Colonne `Signification`** : expansion littérale de l'acronyme
  dans sa langue d'origine (ex. *ROI* → *Return On Investment*,
  *PIB* → *Produit Intérieur Brut*). **Jamais traduite** : un
  glossaire FR contiendra `Return On Investment` pour ROI, et un
  glossaire EN contiendra `Produit Intérieur Brut` pour PIB.
- Nouveau champ `acronym_expansion` sur le domain `Term`, persisté en
  SQLite via soft migration `ALTER TABLE`.

#### Estimation de coût — prise en compte du thinking
- **Bouton « 💵 Estimer le coût »** dans le header bar. Au clic :
  scan du dossier d'entrée, probe ffprobe de chaque vidéo, popup
  détaillé (vidéos, durée totale, coût STT, coût LLM, total, plafond
  avec marge ou dépassement coloré).
- **`CostEstimator` revu** : accepte `phases_config` et applique un
  multiplicateur empirique sur les `completion_tokens` selon le
  `reasoning_effort` :
  - thinking off → ×1.0
  - thinking on (sans effort) → ×2.5
  - thinking on, **HIGH** → ×3.5
  - thinking on, **MAX** → ×6.0
- Calibrage validé sur cas réel : 2 vidéos × 19 min 27 s en HIGH sur
  toutes les phases → estimation $0.0304 vs coût réel observé ~$0.03.

#### Édition des prompts depuis l'UI
- **Menu Édition → Modifier les prompts…** ouvre `PromptsEditorDialog`
  (splitter sidebar + éditeur monospace).
- Liste des 8 templates LLM (phases 1-7 + sous-prompt 5a) avec
  astérisque ` *` si override actif.
- Boutons **Enregistrer** (validation Jinja2 obligatoire — refus si
  syntaxe invalide) et **Réinitialiser au défaut** (suppression de
  l'override avec confirmation).
- Protection contre la perte de modifications : confirmation au
  changement de phase si des modifications ne sont pas sauvegardées.
- Nouveau service `PromptsService` (app/) qui sert d'API stable pour
  le dialogue.

### Modifié

- **`SqliteState.upsert_phase_execution`** : gère explicitement le cas
  `video_id IS NULL` (phases batch) via `DELETE + INSERT`. SQLite
  traite `NULL` comme distinct dans une contrainte `UNIQUE`, donc le
  `ON CONFLICT(run_id, phase_id, video_id)` ne se déclenchait jamais
  pour les phases batch — des doublons s'accumulaient et la matrice
  pouvait afficher RUNNING même après SUCCEEDED. Migration soft
  nettoyante des doublons existants au démarrage.
- **`RunController._refresh_views_with_last_run`** : reset des vues
  (snapshots vides) si le projet sélectionné n'a pas encore de Run,
  pour éviter d'afficher l'état d'un Run appartenant à un autre
  projet.
- **`ProjectsSidebar.contextMenuEvent`** : utilise
  `viewport().mapFromGlobal(event.globalPos())` pour rester insensible
  au padding QSS sur `QListWidget` (cause : le menu contextuel
  Modifier / Supprimer ne s'affichait plus après l'application du
  thème).
- **`StatsSnapshot`** : ajout des champs `started_at`, `finished_at`,
  `elapsed_seconds` (driver de la carte Durée live).

### Corrigé

- Confirmation de suppression de projet jamais valide (utilisait `is`
  au lieu de `==` pour comparer un retour `QMessageBox.StandardButton`).
- Doublons accumulés dans `phase_executions` pour les phases batch sur
  les DBs préexistantes (voir migration soft ci-dessus).
- Estimation de coût massivement sous-estimée quand le mode thinking
  était activé (facteur 2 à 6 d'écart).

### Métriques

- 445+ tests passants (+40 par rapport à 0.1.0).
- `mypy --strict` et `ruff` propres sur 186+ fichiers source.

## [0.1.0] — 2026-05-19

Première version (alpha). Pipeline complet fonctionnel, UI cockpit dense,
packaging Windows portable opérationnel.

### Ajouté

#### Socle technique
- Hiérarchie d'exceptions typées (`Fahmi2Error` + 9 spécialisations) avec
  codes stables et registre de messages localisés FR.
- `RetryPolicy` exponentielle bornée avec jitter et `with_retry` runner.
- Logging structuré JSONL + sink Qt + redaction globale automatique des
  secrets enregistrés.
- `MigrationRunner` générique forward-only + migration baseline v0→v1.

#### Domaine
- Entités immuables (`Project`, `Run`, `VideoExecution`, `PhaseExecution`,
  `Term`, `Glossary`) + `ProjectSettings` exhaustifs avec validations
  cross-champs.
- Identifiants ULID typés (`ProjectId`, `RunId`, `VideoId` via base
  partagée `_UlidIdBase`).
- Machines d'état Run et Phase avec validation des transitions.

#### Infra
- `SqliteState` mode WAL avec 1 connexion par thread, `busy_timeout`,
  retry `SQLITE_BUSY`, test de concurrence 4 threads × 100 writes.
- `FsArtifactStore` avec writes atomiques (`.tmp` puis `rename`).
- `DPAPISecretsStore` Windows (chiffrement DPAPI utilisateur).
- `FFmpegExtractor` (subprocess avec pré-check ffprobe sur la piste audio).
- 2 providers STT : `FasterWhisperAdapter` (CUDA requis) +
  `OpenAIWhisperAdapter` (verbose JSON, mapping erreurs).
- `DeepSeekAdapter` (SDK OpenAI compatible, mode `thinking` via
  `extra_body`).
- `TfidfGlossaryRetriever` (scikit-learn cosine similarity).
- `PromptLoader` avec surcouche utilisateur `%APPDATA%/Fahmi2/prompts/` +
  8 templates Jinja2 par défaut bundlés.
- Constantes tarifaires DeepSeek v4 (Flash + Pro) centralisées dans
  `_pricing.py`.

#### Pipeline
- `PipelineEngine` avec checkpoint SQLite par phase, retry policy,
  événements typés, pause/cancel coopératif via `PauseToken`.
- `EventBus` thread-safe + 6 types d'événements (`RunStarted`,
  `PhaseStarted`, `PhaseProgress`, `PhaseFinished`, `RetryAttempt`,
  `RunFinished`).
- 8 handlers de phase :
  - Phase 0 STT (extraction audio + transcription)
  - Phase 1 extraction termes glossaire
  - Phase 2 réconciliation glossaire (batch)
  - Phase 3 reformulation (avec injection top-K glossaire)
  - Phase 4 structuration Markdown (admonitions sémantiques)
  - Phase 5 consolidation (résumés intermédiaires + méta-éléments, contenu
    des chapitres recopié tel quel)
  - Phase 6 traduction (copies pour langue source, LLM pour autres)
  - Phase 7 cohérence finale par langue

#### App services
- `ProjectService` CRUD projets.
- `RunOrchestrator` lifecycle Run (scan vidéos automatique, exécution
  pipeline, persistance, pause/cancel/resume).
- `CostEstimator` heuristique pré-run STT + LLM par phase et langue.
- `GlossaryReconciler` (import payload, load, render Markdown).
- `SecretsService` wrapper avec redaction logs auto.
- `HardwareProbe` (détection CUDA/GPU).
- `VideoScanner` (extensions `.mp4 .m4v .mkv .mov .webm`).

#### UI PySide6
- `MainWindow` cockpit dense (sidebar projets + header bar + stats strip +
  matrice vidéos × phases + dock logs).
- `RunMatrixViewModel` et `StatsStripViewModel` testables sans Qt.
- `QtEventBus` adapter EventBus → Signal Qt.
- `NewProjectDialog` assistant 1-page avec blocage STT local sans GPU.
- `GlobalSettingsDialog` (clés API + thème).
- Point d'entrée `app_main.py` avec DI complet.

#### Packaging
- Spec PyInstaller `--onedir` avec validation stricte de la présence de
  ffmpeg.
- `packaging/fetch-ffmpeg.ps1` télécharge automatiquement ffmpeg portable
  (build officiel essentials) avec vérification SHA256.
- `packaging/build.ps1` orchestration complète (fetch → clean → build).
- `packaging/make-portable-zip.ps1` génération de l'archive de distribution.
- Résolution runtime du chemin ffmpeg bundlé (`sys.frozen` + `_MEIPASS`).

#### Documentation
- Spec design complète : `docs/superpowers/specs/2026-05-19-fahmi2-design.md`.
- 12 plans d'implémentation taggés `milestone-01` à `milestone-12`.
- Suite documentaire utilisateur : présentation fonctionnelle, présentation
  technique, README, installation, paramétrage, exploitation, procédures
  techniques, guide utilisateur final.

### Métriques

- 405+ tests passants.
- Couverture globale ≥ 87 %.
- `mypy --strict` et `ruff` propres sur 177+ fichiers source.

### Limitations connues

- 2 langues uniquement (FR/EN).
- Format de sortie Markdown uniquement.
- 1 fournisseur LLM (DeepSeek).
- Pas d'auto-update.
- Pas de signature de code (avertissement SmartScreen au 1er lancement).
- Multi-utilisateur non supporté.
