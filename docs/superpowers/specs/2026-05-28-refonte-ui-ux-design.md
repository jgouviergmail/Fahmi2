# Refonte UI/UX — design

> Objet : élever l'interface de Fahmi2 à un niveau **moderne, élégant, peaufiné**
> et **clair pour l'utilisateur final**, sans toucher au domaine, aux services,
> ni au pipeline. Baseline conservée (thème clair, accent bleu Windows), mode
> sombre ajouté, langage visuel « cartes », passe complète sur les libellés et
> les tooltips. Tout est validé écran par écran sur **captures Qt réelles**.

## 1. Contexte & objectifs

L'interface actuelle souffre de plusieurs défauts visibles dès la capture
baseline : libellés bruts (`decontracte`, « Cancel »), formulaires plats avec
« : » systématiques, pages déséquilibrées (grand vide à droite/en bas),
hiérarchie typographique faible, statuts cryptiques dans la sidebar (« G ✓ /
P ▶ »), conversation rendue en simples paragraphes, jargon technique imposé à
l'utilisateur final (« Provider STT », « Retrieval », « top-K », « thinking »).
Le fonctionnel est solide : on n'y touche pas. On ne change que la
**présentation, les libellés et les tooltips**.

Objectifs :

1. Élever l'allure générale au niveau d'un produit moderne (cartes, ombres
   douces, air, hiérarchie typographique forte).
2. Rendre les écrans **compréhensibles par un utilisateur final non technique**.
3. Apporter un **mode sombre** activable (le sélecteur des Paramètres globaux
   devient effectif, par défaut « Système »).
4. **Zéro régression** : tous les `objectName`, signaux, méthodes publiques,
   viewmodels, contrôleurs, domaine et services restent intacts. Les tests
   `pytest` / `ruff` / `mypy` sont verts à chaque lot.

## 2. Principes directeurs

- **Baseline rehaussée, pas remplacée** : on conserve l'identité Clair Fluent
  Windows 11 (palette + accent `#0078d4`) ; on durcit la cohérence, la
  hiérarchie et le rythme.
- **Cartes plutôt que formulaires plats** : sections de réglages regroupées
  dans des cartes blanches à ombre douce sur fond gris doux.
- **Air & rythme** : grille d'espacement 4 px (4/8/12/16/20/24/28).
- **Hiérarchie typographique** : titre de page (20/700), titre de carte
  (14/700), libellé de champ (13), texte d'aide (12 muted), micro-label
  majuscules (11/700 letter-spacing). Une seule famille (Segoe UI), poids et
  tailles font la hiérarchie.
- **Sans « : »** sur les étiquettes de formulaire. Le ratio
  étiquette/champ + l'alignement font la lisibilité.
- **Plain language** : on parle utilisateur, pas plumbing. « Moteur de
  transcription », pas « Provider STT ».
- **Tooltip systématique** sur tout contrôle dont la conséquence n'est pas
  évidente.
- **Validation par capture Qt réelle** (offscreen-équivalent : `widget.grab()`
  sans afficher la fenêtre, avec polices système). Avant/après pour chaque
  écran dans `.ui-review/`.

## 3. Système de design

### 3.1 Tokens — Mode clair (baseline conservée)

| Token | Valeur | Usage |
|---|---|---|
| `--bg` | `#f5f7fb` | Fond fenêtre / page |
| `--surface` | `#ffffff` | Surface des cartes, menus, popovers |
| `--surface-soft` | `#fbfcfe` | Liste de navigation des réglages |
| `--border` | `#d6dae0` | Bordure de champ |
| `--border-card` | `#e9ecf1` | Bordure de carte |
| `--divider` | `#eef0f4` | Séparateurs fins |
| `--text-1` | `#1f2328` | Texte principal |
| `--text-2` | `#57606a` | Libellés secondaires |
| `--text-3` | `#8b95a1` | Aide, micro-info |
| `--accent` | `#0078d4` | Accent primaire (Windows blue) |
| `--accent-hover` | `#1086e8` | Hover du primaire |
| `--accent-pressed` | `#006abf` | Pressed du primaire |
| `--accent-soft` | `#e3f0fb` | Sélection nav, pilule |
| `--accent-strong` | `#0a4f93` | Texte sur fond `--accent-soft` |
| `--success` / `--success-bg` | `#1a7f37` / `#e6f6ec` | Statuts OK |
| `--warning` / `--warning-bg` | `#b45309` / `#fef3c7` | Statuts attention |
| `--danger` / `--danger-bg` | `#cf222e` / `#fcebec` | Statuts erreur / destructif |
| `--shadow-card` | `rgba(15,23,42,0.10)` blur 22, dy 4 | Ombre de carte |

### 3.2 Tokens — Mode sombre (nouveau)

Tokens dérivés pour préserver la même hiérarchie de contraste et l'identité
bleu Windows, en remontant l'accent pour la lisibilité sur sombre.

| Token | Valeur | Usage |
|---|---|---|
| `--bg` | `#11151c` | Fond fenêtre / page |
| `--surface` | `#1a1f27` | Surface des cartes |
| `--surface-soft` | `#161b22` | Liste de navigation |
| `--surface-elevated` | `#222831` | Menus, popovers, tooltips |
| `--border` | `#2a2f38` | Bordure de champ |
| `--border-card` | `#262b34` | Bordure de carte |
| `--divider` | `#232831` | Séparateurs fins |
| `--text-1` | `#e6e9ef` | Texte principal |
| `--text-2` | `#9aa3b2` | Libellés secondaires |
| `--text-3` | `#6e7787` | Aide, micro-info |
| `--accent` | `#4aa3ee` | Accent (remontée de luminosité) |
| `--accent-hover` | `#67b3f1` | Hover |
| `--accent-pressed` | `#3a93de` | Pressed |
| `--accent-soft` | `#15314d` | Sélection, pilule |
| `--accent-strong` | `#9cc8f4` | Texte sur fond `--accent-soft` |
| `--success` / `--success-bg` | `#3fb950` / `#122c1a` | Statuts OK |
| `--warning` / `--warning-bg` | `#d29922` / `#2c1f0f` | Statuts attention |
| `--danger` / `--danger-bg` | `#f85149` / `#2c1419` | Statuts erreur |
| `--shadow-card` | `rgba(0,0,0,0.45)` blur 24, dy 6 | Ombre de carte |

### 3.3 Échelle typographique

| Rôle | Taille | Graisse | Couleur | Cas d'usage |
|---|---|---|---|---|
| Page title | 20 px | 700 | `--text-1` | Titre d'écran de réglages, en-tête de dialogue |
| Card title | 14 px | 700 | `--text-1` | Titre de section dans une carte |
| Card description | 12 px | 400 | `--text-3` | Description sous un card title |
| Field label | 13 px | 500 | `--text-1` | Étiquette de champ |
| Body | 13 px | 400 | `--text-1` | Corps |
| Hint | 12 px | 400 | `--text-3` | Texte d'aide sous un champ |
| Micro-label | 11 px | 700 | `--text-3`, ls .6 | Titres de carte stats, en-têtes de tableau |

### 3.4 Espacement, rayons, états

- **Grille** : multiples de 4 px. Marges de carte 18–22, formulaire vertical
  12–14, horizontal 16–20.
- **Rayons** : champs/boutons **8 px**, cartes **14 px**, pilule de
  navigation **9 px**.
- **États** :
  - *Hover* champ : `border-color: var(--text-2)` (équivalent `#b6bec8`).
  - *Focus* champ : `border: 2px solid var(--accent)` avec **compensation de
    padding** (`padding: -1px`) pour ne pas faire « sauter » la taille du
    contrôle (technique éprouvée).
  - *Disabled* : opacité du texte + neutralisation du background.
  - *Pressed* boutons : assombrissement de 1 cran.

### 3.5 Composants

#### 3.5.1 Boutons
- 3 rôles, propriété Qt `role`, déjà en place : `primary` (accent),
  `default` (neutre), `danger` (rouge discret).
- Tailles : `padding: 8px 18px`, `min-height: 22px`, `border-radius: 9px`,
  `font-weight: 500` (600 sur `primary`).
- États hover/pressed/disabled définis pour les 3 rôles, light + dark.
- **Curseur** : main (`PointingHandCursor`) — déjà fait dans
  `make_role_button`.

#### 3.5.2 Champs (`QLineEdit`, `QPlainTextEdit`, `QTextEdit`, `QComboBox`,
`QSpinBox`, `QDoubleSpinBox`)
- Bordure 1 px, focus 2 px (anneau), arrondi 8 px, padding 7×11, hauteur min
  20 px.
- `QComboBox::drop-down` : sans bordure, 22 px de large.
- `selection-background-color` aligné sur `--accent-soft`.

#### 3.5.3 Cases à cocher / radios
- Indicateur 16 × 16, arrondi 4 px ; coche SVG blanche embedded (déjà OK).
- Espacement libellé 8 px ; libellé sans « : » et plain language.

#### 3.5.4 Cartes (`Card`)
- `QFrame` `objectName="card"`, fond `--surface`, bordure 1 px
  `--border-card`, arrondi 14 px, `QGraphicsDropShadowEffect` (blur 22, dy 4,
  couleur `--shadow-card`).
- Padding interne 20×22, spacing 12.
- Titre obligatoire (`#cardTitle`), sous-titre optionnel (`#cardDesc`).

#### 3.5.5 Liste de navigation des réglages
(`#settingsCategoryList`)
- Fond `--surface-soft`, séparation droite `--divider`.
- Item : padding 11×13, arrondi 9 px, marge 3 px.
- Sélection : background `--accent-soft`, texte `--accent-strong`, gras.
- Hover : background plus clair, texte `--text-1`.

#### 3.5.6 Tuiles de stats (`StatCard`)
- Arrondi 12 px, bordure `--border-card`, padding 14×10.
- Icône (10 px, accent), titre micro-label (11/700 majuscule),
  valeur (20 px / 700), sous-info (11/400 muted).
- Variantes d'accent par propriété `accent` : running / success / warning /
  danger / neutral.

#### 3.5.7 Onglets (`QTabWidget`)
- Tab non sélectionné : fond `--divider`, texte `--text-2`.
- Hover : fond `--accent-soft`, texte `--accent-strong`.
- Sélectionné : fond `--surface`, texte `--accent`, soulignement 2 px
  `--accent` (on conserve l'underline familier ; pas de pilule sur les
  onglets principaux pour ne pas concurrencer la nav de réglages).
- Padding 9×20, espacement 4 px.

#### 3.5.8 Matrice de coût (peinte en code)
- Délégué de cellule existant conservé. Palette des statuts harmonisée avec
  les tokens (light + dark) ; mêmes 5 statuts.
- En-tête de tableau : fond `--surface`, texte `--text-2` micro-label, lignes
  séparées par `--divider`.

#### 3.5.9 Tooltips
- Fond `--text-1` (sombre sur clair, clair sur sombre via tokens), texte
  blanc, arrondi 6 px, padding 6×8. Déjà en place ; ajusté pour dark.

#### 3.5.10 Scrollbars
- Très sobres (déjà en place), largeur 10, poignée arrondie.

#### 3.5.11 Boîtes de dialogue
- Boutons standard de Qt **traduits en français** via helper
  `frenchify_button_box(box)` qui remplace les textes des boutons standard
  (`Ok` reste « OK », `Save` → « Enregistrer », `Cancel` → « Annuler »,
  `Close` → « Fermer », `Yes/No` → « Oui/Non », `Discard` → « Abandonner »).

#### 3.5.12 Iconographie
- Emojis Unicode conservés (rendu couleur fidèle via Segoe UI Emoji, zéro
  dépendance / packaging).
- Convention d'usage :
  - **Boutons principaux d'action** (header bar) : 1 emoji + libellé.
  - **Boutons secondaires de dialogue** (Enregistrer, Annuler) : sans
    emoji.
  - **Tuiles de stats / sidebar** : un glyphe Unicode monochrome (●, ▶, ✓,
    ⏸) pas un emoji couleur, pour cohérence avec la valeur.
  - **Titres d'écran** : pas d'emoji.

## 4. Mode sombre — mécanisme

Trois modes, basculement en direct :

```
ThemeMode := SYSTEM | LIGHT | DARK
```

- **SYSTEM** (défaut) : lit
  `QGuiApplication.styleHints().colorScheme()` (Qt 6.5+) et applique le
  thème correspondant. Écoute `colorSchemeChanged` pour suivre les
  changements OS en cours d'exécution.
- **LIGHT** / **DARK** : force.

### 4.1 Structure des fichiers QSS

```
src/fahmi2/ui/theme/
  light_fluent.qss      # baseline rehaussée
  dark_fluent.qss       # nouveau, miroir token-pour-token
  __init__.py           # apply_theme(app, mode)
```

Les deux QSS sont **structurés à l'identique** (mêmes sélecteurs, valeurs
issues des tables tokens correspondantes), pour qu'un changement de structure
soit fait des deux côtés en miroir.

### 4.2 Persistance

Préférence stockée dans `AppPaths.appdata/ui_prefs.json` :

```json
{ "theme_mode": "system" }
```

Lecture/écriture par un mini `UiPreferences` (purement UI), chargé au
démarrage par `app_main`, branché sur la combo « Thème » de
`GlobalSettingsDialog`. **Aucun impact sur le domaine, les services, le
pipeline ou la pédagogie.**

### 4.3 Application au runtime
- Au démarrage : `apply_theme(app, prefs.theme_mode)`.
- À la sélection dans le dialogue : enregistre la préférence + appelle
  `apply_theme` + propage le re-polish aux fenêtres ouvertes
  (`QApplication.allWidgets()` → `style().unpolish/polish`).

## 5. Briques UI partagées (nouveau module `ui/_components.py`)

API publique (toute construction UI passe par ces helpers pour cohérence) :

```python
def card(
    parent: QWidget | None,
    *,
    title: str,
    description: str | None = None,
) -> tuple[QFrame, QVBoxLayout]:
    """Carte standard (fond, bordure, ombre, header)."""

def page_header(
    parent: QWidget | None,
    *,
    title: str,
    description: str | None = None,
) -> QWidget:
    """En-tête d'écran de réglages : titre 20/700 + description grise."""

def field_hint(parent: QWidget | None, text: str) -> QLabel:
    """Texte d'aide gris 12 px sous un champ."""

def section_label(parent: QWidget | None, text: str) -> QLabel:
    """Micro-label 11/700 majuscules letter-spacing."""

def frenchify_button_box(box: QDialogButtonBox) -> None:
    """Remplace les libellés des boutons standard Qt par leur version FR."""

def install_shadow(widget: QWidget) -> None:
    """Applique l'ombre de carte standard via QGraphicsDropShadowEffect."""
```

Les `objectName` (`card`, `cardTitle`, `cardDesc`, `settingsPageTitle`,
`settingsPageDesc`, `fieldHint`, `sectionLabel`) sont **strictement
réservés** au styling QSS — pas de logique applicative qui s'y accroche.

## 6. Conventions de libellés & tooltips

### 6.1 Règles

1. **Aucun « : »** en fin d'étiquette de formulaire.
2. **Casse phrase** (première lettre majuscule, reste minuscule sauf noms
   propres) : « Modèle de génération », pas « MODÈLE DE GÉNÉRATION ».
3. **Verbes à l'infinitif** sur les boutons d'action : Lancer, Pause,
   Reprendre, Annuler, Enregistrer, Exporter, Réinitialiser.
4. **Terminologie unifiée** :
   - **Source** (pas « vidéo », « média », « entrée » : on est polymorphe).
   - **Document consolidé** (pas « consolidé », « livrable »).
   - **Glossaire** (pas « termes »).
   - **Support** (pas « fiche » sauf quand c'est le type de support).
   - **Conversation** (pas « dialogue » sauf l'onglet).
   - **Génération** (le run), **Supports pédagogiques** (l'onglet).
5. **Plain language** : on bannit le jargon technique côté utilisateur. Les
   noms de modèles techniques (DeepSeek, GPT-4o…) restent dans les combos
   parce que l'utilisateur les compare ; mais on n'expose pas « Provider
   STT », « Retrieval », « top-K », « thinking ».
6. **Pas de valeurs brutes d'enum** : tout `StrEnum` exposé en UI passe par
   un mapping libellé (`*_LABELS`).
7. **Tooltip systématique** : une phrase (≤ 140 caractères) qui explique la
   **conséquence**, pas la définition. Ex. : *« Décochez pour insérer les
   documents déjà rédigés sans reformulation (coût nul). »*

### 6.2 Glossaire — termes transverses

| Avant | Après |
|---|---|
| Provider STT | Moteur de transcription |
| Modèle local | Modèle hors-ligne (GPU) |
| Modèle cloud | Modèle en ligne (OpenAI) |
| STT local / STT cloud | Transcription locale / Transcription en ligne |
| Retrieval | Recherche de passages |
| Stratégie de retrieval | Méthode de recherche |
| Lexical (TF-IDF, hors-ligne) | Mots-clés (hors-ligne) |
| Sémantique (embeddings OpenAI) | Sens (en ligne, OpenAI) |
| Auto (sémantique si possible…) | Automatique (sens si clé OpenAI, mots-clés sinon) |
| Embedding (model) | Modèle de vectorisation |
| Top-K / Passages (top-K) | Nombre de passages cités |
| Expansion de requête | Reformulation automatique de la question |
| Fidélité | Mode de réponse |
| Ancré strict | Strict — réponses tirées du cours uniquement |
| Augmenté | Étendu — complète au-delà du cours |
| Grounding | Mode de réponse |
| Mode raisonnement (thinking) | Réflexion approfondie |
| Effort de raisonnement | Intensité de réflexion |
| Niveau d'effort | Intensité de réflexion |
| Reasoning (HIGH / MAX) | Élevée / Maximale |
| Température | Température (laissé : standard LLM, compris) |
| Plafond budget | Budget maximal |
| Cost ceiling | Budget maximal |
| Appels LLM en parallèle | Traitements IA simultanés |
| Tâches en parallèle | Traitements simultanés |
| Transcriptions en parallèle | Transcriptions simultanées |
| Phases LLM (titre du widget) | Phases IA (libellé d'écran) |
| Configuration des phases LLM | Réglages par phase IA |
| Max retries | Tentatives en cas d'erreur |
| Public cible | Public visé |
| Objectif (Bloom) | Objectif pédagogique |
| Densité | Quantité de contenu |
| Directives stylistiques | Consignes de style |
| Directives | Consignes |
| corrigé séparé | Corrigé dans un document séparé |
| Préréglage de style | Préréglage de style (libellé OK) |
| Style preset values: decontracte/standard/professionnel/academique | Décontracté / Standard / Professionnel / Académique |
| Mode de consolidation | Mode d'assemblage |
| Ordonné (1 source = 1 chapitre) | Conserver l'ordre — 1 source = 1 chapitre |
| Refonte thématique | Synthèse thématique |
| Dossier d'entrée | Dossier des sources |
| Liens YouTube | Vidéos YouTube |
| Conserver les fichiers audio extraits | Conserver les fichiers audio (utile pour réécouter) |
| Reformuler les documents texte | Reformuler les documents (PDF, Word…) |
| Formats d'export | Formats à exporter |
| Clé OpenAI | Clé API OpenAI |
| Clé DeepSeek | Clé API DeepSeek |
| Thème | Apparence |
| Nom | Nom du projet |
| Emplacement | Dossier du projet |
| Parcourir… | Choisir… |
| Provider | Moteur |
| Configurer la génération | Configurer la génération (OK) |
| Réglages de la génération | Réglages de la génération (OK) |

### 6.3 Glossaire — boutons d'action

| Avant | Après |
|---|---|
| ⚙️  Réglages | ⚙️ Réglages |
| 💵  Estimer le coût | 💵 Estimer le coût |
| 🚀  Lancer | 🚀 Lancer la génération (header) / 🚀 Lancer (compact) |
| ⏸️  Pause | ⏸️ Mettre en pause |
| ▶️  Reprendre | ▶️ Reprendre |
| ❌  Annuler | ❌ Annuler l'exécution |
| 📂  Dossier de sortie | 📂 Ouvrir le dossier produit |
| 📦  Exporter | 📦 Exporter |
| 🗑️  Réinitialiser | 🗑️ Tout réinitialiser |
| ＋ Nouvelle conversation | ＋ Nouvelle conversation (OK) |
| Envoyer (chat) | Envoyer |
| OK / Cancel / Save / Close (Qt standard) | OK / Annuler / Enregistrer / Fermer |

### 6.4 Glossaire — statuts (déjà bons, conservés)

Run : Créé · En cours · En pause · Terminé · Échec · Annulé. (`status_labels.py`)
Phase : En attente · En cours · Réussie · Échec · Sautée. (à harmoniser depuis
`PhaseStatus`)
Support : En attente · En cours · Généré · À jour · Échec. (`pedagogy_labels.py`)

## 7. Inventaire des écrans — structure cible

Pour chaque écran : la structure passe en **page header + cartes**, les
libellés appliquent §6, les tooltips sont présents. Captures avant/après dans
`.ui-review/` à chaque livraison.

### 7.1 Réglages — Génération
**Réorganisation des catégories** (libellés affichés modifiés ; les
constantes internes `_CAT_*` peuvent être ajustées en cohérence — pure UI) :

1. *Sources* (anciennement « Entrée & langues ») — cartes « Dossier des sources », « Vidéos YouTube », « Langues du document », « Ordre & exclusions ».
2. *Style* — cartes « Mise en forme », « Documents texte ».
3. *Transcription* — carte « Moteur de transcription », carte « Modèle », carte « Performance » (parallélisme + conservation audio).
4. *Génération IA* (anciennement « Modèle & coût ») — cartes « Modèle », « Budget maximal », « Performance ».
5. *Phases IA* (anciennement « Phases ») — table actuelle reformatée en carte unique avec sous-titres.
6. *Export* — carte unique listant les formats à exporter.

### 7.2 Réglages — Supports pédagogiques
1. *Supports* — carte « Types de supports » (grille + corrigé séparé).
2. *Difficulté* — cartes « Public et objectif », « Quantité de contenu », « Consignes ».
3. *Langues* — carte « Langues à produire ».
4. *Génération IA* — cartes « Modèle », « Budget », « Performance ».
5. *Export* — carte « Formats à exporter ».

### 7.3 Réglages — Dialogue
Le dialogue actuel à un seul formulaire devient une page master-detail à 3
catégories : *Mode de réponse* (fidélité, top-K) · *Recherche de passages*
(méthode, expansion, modèle de vectorisation) · *Génération IA* (modèle,
réflexion, température). Chaque page = 1–2 cartes.

### 7.4 Paramètres globaux
Trois cartes : *Clés API* (OpenAI, DeepSeek, avec icône cadenas et hint sur
le stockage DPAPI) · *Apparence* (combo « Apparence » : Système / Clair /
Sombre — désormais fonctionnel) · *À propos* (version + lien repo).

### 7.5 Nouveau / Renommer projet
Une seule carte centrée 480 px : champ « Nom du projet », champ « Dossier
du projet » + bouton « Choisir… », helpers explicatifs.

### 7.6 Éditeur de prompts
Layout splitter conservé. **Liste à gauche** : section labels groupant par
fonctionnalité (Génération, Pédagogie, Dialogue), pilule de sélection.
**Panneau de droite** : page header (titre du template, description),
bandeau « Override actif / Défaut » en pastille colorée, éditeur monospace
dans une carte, boutons d'action (Enregistrer / Réinitialiser au défaut)
sous la carte.

### 7.7 Cockpit Génération (onglet)
Structure conservée (header bar + stats strip + matrice). Refonte
visuelle :

- **Header bar** : libellés homogénéisés (§6.3), groupe gauche
  « préparation/exécution » et groupe droit « résultats » séparés visuellement
  par une **barre verticale fine** plutôt qu'un `addStretch` muet.
- **Stats strip** : tuiles en cartes raffinées (radius 12, bordure, ombre
  *très* discrète sur clair, plus marquée sur sombre).
- **Matrice** : en-tête revu (micro-label majuscules avec letter-spacing),
  palette de statuts alignée sur les tokens (light + dark). Cellule
  conservée en peinture custom (délégué inchangé).

### 7.8 Progression pédagogie
Idem § 7.7, structure conservée. Bandeau d'état (`#pedagogyStateBanner`)
réharmonisé visuellement, libellés clarifiés.

### 7.9 Onglet Dialogue (chat)
**Vraies bulles de chat** rendues dans le `QTextBrowser` :

- Bulle utilisateur : alignée à droite, fond `--accent-soft`, texte
  `--accent-strong`, arrondi 12 px, padding 10×14.
- Bulle assistant : alignée à gauche, fond `--surface`, bordure
  `--border-card`, arrondi 12 px, padding 10×14, ombre douce facultative
  (selon perf).
- Étiquette « Vous » / « Assistant » remplacée par un en-tête bulle discret
  (avatar texte rond 22 px avec initiale + horodatage gris si l'on veut).
- **Sources** rendues dans la bulle sous un séparateur fin, en chips
  cliquables (un par chapitre cité), pas une `<ul>` brute.
- **Bandeau « pas de corpus »** réharmonisé (carte centrée avec icône).
- **Champ de saisie** : QPlainTextEdit auto-grow (jusqu'à 4 lignes), bouton
  Envoyer primaire ; raccourci `Ctrl+Entrée`.
- **Liste de conversations à gauche** : pilule de sélection, badge langue
  ([fr], [en]…) en chip discret en tête de l'entrée.
- **Libellé de coût cumulé** repositionné dans un petit pied de panneau
  avec micro-label « Coût cumulé » + valeur.

### 7.10 Sidebar projets
Statuts cryptiques `G ✓ / P ▶  Nom` remplacés par :

```
●  Nom du projet
   Génération en cours · Supports à jour
```

- Pastille colorée à gauche (token success/running/warning/danger/neutral).
- Nom du projet en `--text-1` 13/600.
- Sous-libellé en `--text-3` 11 résumant les statuts en clair.
- Au hover : background `--accent-soft`. Sélection : bordure gauche 3 px
  `--accent` + background `--accent-soft`.
- Item rendu par un délégué simple (peinture conservée par `QListWidget`).

### 7.11 Dock Logs
- En-tête de dock : titre + filtre « Niveau minimum » à droite (déjà
  proche, on rend cohérent).
- Zone de logs : conservée monospace, palette adaptée light/dark.
- Aucune action ajoutée (scope discipline : on n'introduit pas de nouveau
  comportement, on rend ce qui existe lisible et cohérent).

### 7.12 Fenêtre principale (`MainWindow`)
- Splitter horizontal conservé.
- **Menus FR consistants** : Fichier · Édition · Affichage · Aide
  (« ? » → « Aide »).
- Item d'« À propos » remanié (lien dépôt + version).

### 7.13 Estimation de coût
Le dialogue HTML actuel passe en composant Qt natif avec :
- Carte « Détail » (lignes par phase / support).
- Carte « Total » (valeur ≈ + fourchette + plafond + verdict coloré).
- Bouton « Compris » (au lieu de OK par défaut).

### 7.14 Boîtes de message (`QMessageBox`)
Helper appliqué partout (`frenchify_button_box`) : « Oui / Non »,
« Annuler », « Abandonner », « Enregistrer », « Fermer ».

## 8. Lots de livraison

Chaque lot se termine par : (1) captures Qt avant/après dans `.ui-review/`
pour validation utilisateur, (2) `pytest` + `ruff check .` + `mypy src tests`
verts.

- **Lot 0 — Fondations** (1 PR)
  - QSS clair refondu + tokens documentés en commentaire.
  - QSS sombre miroir (nouveau).
  - `ui/theme/__init__.py` : `apply_theme(app, mode)`, suivi du thème
    système, helper de re-polish.
  - `ui/_components.py` : `card`, `page_header`, `field_hint`,
    `section_label`, `frenchify_button_box`, `install_shadow`.
  - `app/ui_preferences.py` : lecture/écriture `ui_prefs.json` sous
    `AppPaths.appdata`.
  - `app_main` : chargement de la préférence + application.
  - Banc de capture pérennisé sous `scripts/ui_captures.py` (générer toutes
    les captures avant/après).

- **Lot 1 — Écrans de réglages** (1 PR)
  - Génération · Pédagogie · Dialogue · Globaux · Nouveau projet ·
    Éditeur de prompts.
  - Application du glossaire §6.2/§6.3 sur ces écrans.
  - Tooltips standardisés.
  - Captures avant/après pour les 6 écrans.

- **Lot 2 — Cockpits & dashboards** (1 PR)
  - Cockpit Génération, Progression Pédagogie, Sidebar projets, Dock Logs,
    Fenêtre principale, Estimation de coût, Boîtes de message.
  - Captures avant/après.

- **Lot 3 — Onglet Dialogue (bulles)** (1 PR)
  - Refonte du rendu du fil (bulles + chips de sources), saisie multi-ligne
    avec raccourci, liste de conversations, libellé de coût.
  - Captures avant/après en mode clair et sombre.

Ordre conseillé d'exécution : Lot 0 → Lot 1 → Lot 2 → Lot 3.
Chaque lot peut être livré indépendamment et est validé visuellement
avant fusion.

## 9. Méthode de validation (contrat de fidélité)

Pour chaque écran touché :

1. Le banc `scripts/ui_captures.py` produit `before/<screen>.png` (état
   actuel) et `after/<screen>.png` (état refondu) **dans la même PR**.
2. Les deux captures sont déposées dans `.ui-review/` puis dans le PR body.
3. Captures rendues avec :
   - `QApplication` initialisée, thème appliqué (clair **et** sombre pour
     les écrans concernés par le mode sombre).
   - Polices Windows réelles (sans `QT_QPA_PLATFORM=offscreen`, qui ne
     charge pas la fonte ; on rend la fenêtre sans `show()` via `grab()`).
4. **Ce que l'utilisateur valide est exactement ce qui sera livré.**

## 10. Non-régression (engagement précis)

- Aucune modification du domaine (`domain/`), des services (`app/`), du
  pipeline (`pipeline/`), de la pédagogie (`pedagogy/`), du chat (`chat/`),
  des infrastructures (`infra/`) ni du core (`core/`).
- Aucune suppression / renommage / re-signature de signal Qt, méthode
  publique ou propriété de widget. Les `objectName` actuellement utilisés
  par le code (`projectHeaderBar`, `statCard`, `costMatrix`,
  `pedagogyStateBanner`, `settingsCategoryList`, etc.) **restent en place**
  ou sont étendus, jamais supprimés.
- Les tests `pytest-qt` qui vérifient une chaîne de libellé sont mis à jour
  **en même temps** que le libellé (le commit qui change un libellé met à
  jour le test associé — non-régression au sens « ça compile, ça passe »).
- Les `ViewModel` (`ChatViewModel`, `PedagogyStateViewModel`,
  `StatsStripViewModel`, `CostMatrixSnapshot`, …) ne sont pas touchés.
- `pytest`, `ruff check .`, `mypy src tests` verts à la fin de chaque lot.
- **Garde-fou de synchronisation light/dark** : un test unitaire compare
  l'ensemble des sélecteurs présents dans `light_fluent.qss` et
  `dark_fluent.qss`. Toute divergence (sélecteur stylé d'un côté seulement)
  fait échouer la CI — empêche la dérive entre les deux thèmes au fil des
  évolutions.

## 11. Risques et mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Tests `pytest-qt` qui asséneraient un libellé exact | Échec CI | Mise à jour des libellés dans le **même commit** que celui du code UI. |
| Ombre `QGraphicsDropShadowEffect` coûteuse sur cockpit en `RUNNING` (timer 1 s) | Saccades possibles | Limiter l'ombre aux **cartes** (peu nombreuses, statiques). Pas d'ombre sur cellules de matrice ni sur tuiles à valeur live. |
| QSS dark exhaustif | Risque d'oubli d'un sélecteur → fond clair sur dark | Audit visuel par capture ; les deux QSS structurés identiquement, revue diff cher contre cher. |
| Lecture/écriture de `ui_prefs.json` | Régression au démarrage si fichier corrompu | Lecture *lenient* avec repli sur `system` ; écriture atomique. |
| Sélecteur « Apparence » devient effectif | L'utilisateur change la préférence en cours d'exécution | Re-polish global après application ; tests manuels par capture (clair → sombre → clair). |

## 12. Hors scope (volontaire)

- Pas de bundling d'un set d'icônes (SVG/icon-font). On reste sur emoji et
  glyphes Unicode (zéro changement de packaging).
- Pas de changement de la matrice de coût en widgets natifs (le délégué
  custom reste, palette harmonisée).
- Pas d'animations / transitions (QSS ne les gère pas proprement ; restera
  à un éventuel chantier séparé).
- Pas de retravail des onglets d'écrans secondaires sans valeur claire
  (l'estimation de coût bascule en widget mais reste un dialogue modal,
  pas un panneau).
