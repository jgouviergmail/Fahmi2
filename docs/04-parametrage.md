# Fahmi2 — Guide de paramétrage

Cette documentation détaille tous les paramètres disponibles dans Fahmi2 et
leurs implications.

## 1. Paramètres globaux (toute l'application)

Accès : menu **Édition → Paramètres globaux**.

### 1.1 Clés API

| Clé | Usage | Obtention |
|-----|-------|-----------|
| **Clé OpenAI** | Provider STT cloud (Whisper) | https://platform.openai.com/api-keys |
| **Clé DeepSeek** | Toutes les phases LLM | https://platform.deepseek.com/api-keys |

Les clés sont **chiffrées via Windows DPAPI** et stockées dans
`%APPDATA%\Fahmi2\secrets.dat`. Elles ne sont jamais visibles en clair sur
disque ni dans les logs. Seul l'utilisateur Windows qui les a saisies peut
les déchiffrer (le fichier `secrets.dat` ne fonctionne pas sur une autre
machine ou sous un autre compte).

### 1.2 Thème

- `system` (recommandé) : suit le thème Windows en cours.
- `light` : thème clair forcé.
- `dark` : thème sombre forcé.

### 1.3 Niveau de logs UI

Niveau plancher affiché dans le panneau Logs. Par défaut `INFO`. Les
événements plus bas sont silencieusement filtrés à l'affichage (mais
toujours écrits dans le fichier `events.jsonl`).

## 2. Paramètres d'un projet

L'**identité** du projet (nom + emplacement) se définit via **Fichier → Nouveau
projet** (renommage via *Éditer* dans la sidebar ; l'emplacement est immuable
après création). Tous les autres paramètres ci-dessous sont les **réglages de
génération**, édités depuis l'onglet **Génération → ⚙ Réglages** (vue
master-detail) ; ils incluent le **dossier des vidéos**.

### 2.1 Identification

| Paramètre | Description |
|-----------|-------------|
| **Nom** | Libre, sert d'étiquette dans la sidebar. Ex: « Cours macroéconomie L3 ». |
| **Emplacement** | Dossier de travail du projet (artefacts + livrables). Immuable après création. |

> Le **dossier des vidéos** (source) est un réglage de génération : il se choisit
> dans l'onglet **Génération → ⚙ Réglages → Entrée & langues**.

### 2.2 Langues

| Paramètre | Description |
|-----------|-------------|
| **Langue source** | Langue parlée dans les vidéos. Le pipeline produit d'abord le document master dans cette langue puis traduit vers les autres langues de sortie. |
| **Langues de sortie** | Cocher chaque langue désirée. La langue source est toujours incluse. Si vous cochez uniquement EN alors que la source est FR, FR sera automatiquement ajouté. |

### 2.3 Style

| Paramètre | Description |
|-----------|-------------|
| **Style** | `décontracté`, `standard`, `professionnel`, ou `académique`. Affecte le ton, le vocabulaire et le niveau de formalisme. |
| **Directives stylistiques** | Texte libre qui sera concaténé aux prompts. Ex: « voix professorale, ton chaleureux mais rigoureux, éviter le jargon ». |

### 2.4 Providers

| Paramètre | Description | Coût indicatif |
|-----------|-------------|----------------|
| **Provider STT** | `faster_whisper_local` (GPU NVIDIA requis) ou `openai_cloud`. En mode cloud, l'audio est **compressé en Opus** (et découpé aux silences si > ~2 h) pour respecter la limite **25 Mo** d'OpenAI Whisper — transparent, toute durée, et l'upload est bien plus rapide. | Local : gratuit / Cloud : ~0,006 $/min |
| **Modèle LLM** | `deepseek-v4-flash` (rapide/économique) ou `deepseek-v4-pro` (capacité supérieure). | Flash : ~0,14-0,28 $/Mt / Pro : ~0,435-0,87 $/Mt |

**Blocage automatique** : si vous sélectionnez `faster_whisper_local` sans
GPU CUDA détecté, l'application affichera un avertissement et basculera
automatiquement sur `openai_cloud`. Ce comportement est délibéré : la
transcription locale en CPU pur prendrait des dizaines d'heures pour un
batch normal.

### 2.5 Configuration par phase

Pour chaque phase LLM (phases 1 à 7), vous pouvez configurer :

| Paramètre | Description | Plage | Recommandation |
|-----------|-------------|-------|----------------|
| **Thinking activé** | Mode raisonnement DeepSeek (envoie `{"thinking": {"type": "enabled"}}`). Le modèle produit des tokens de raisonnement avant la réponse finale. | bool | Off par défaut, on pour phases critiques (structuration, consolidation, cohérence) |
| **Effort de raisonnement** | Niveau d'effort transmis à DeepSeek (envoie `{"reasoning_effort": "high"}` ou `"max"`). Pris en compte uniquement si Thinking est coché. | `(défaut serveur)` / `HIGH` / `MAX` | `HIGH` pour la plupart des cas, `MAX` pour les phases les plus difficiles ou en cas de qualité insuffisante |
| **Température** | Variabilité de la sortie LLM | 0.0 — 2.0 | 0.2-0.4 pour structuration ; 0.0-0.2 pour traduction ; 0.3-0.6 pour reformulation |
| **Max retries** | Tentatives en cas d'erreur transitoire | 0 — ∞ | 5 par défaut |

**⚠ Impact coût du thinking.** Activer le thinking peut multiplier le
coût d'une phase par 2 à 6 selon le niveau d'effort, car les tokens de
raisonnement sont facturés au tarif `output` standard. L'estimation
pré-run en tient compte (voir section 2.6 ci-dessous).

### 2.6 Plafond budget et estimation pré-run

| Paramètre | Description |
|-----------|-------------|
| **Plafond USD** | Coût maximum autorisé pour le run. À 0 ou non défini : pas de plafond. Sinon, le run se met en pause propre dès que le coût cumulé approche du plafond. |

L'arrêt est toujours **propre** : jamais d'interruption au milieu d'un
appel LLM en cours. La pause se produit à la prochaine frontière sûre.

**Estimation pré-run accessible à tout moment** depuis la barre
d'en-tête (bouton **💵 Estimer le coût**). Le dialogue présente une
**décomposition par phase** et un **total sous forme de fourchette ±33 %**
(« estimation indicative »), avec un avertissement si le haut de fourchette
peut dépasser le plafond. Le calcul intègre :

- La durée audio totale des vidéos détectées (probe `ffprobe`).
- Le provider STT (`faster_whisper_local` = gratuit, `openai_cloud` =
  $0.006/min).
- Le modèle LLM (grille tarifaire Flash vs Pro).
- Le nombre de langues de sortie + de traductions nécessaires.
- **La configuration par phase** : `thinking_enabled` et
  `reasoning_effort` sont traduits en un multiplicateur appliqué aux
  tokens de complétion estimés :

| `thinking_enabled` | `reasoning_effort` | Multiplicateur output |
|---|---|---|
| `false` | (n/a) | ×1.0 |
| `true` | (défaut serveur) | ×2.5 |
| `true` | `HIGH` | ×3.5 |
| `true` | `MAX` | ×6.0 |

L'écart résiduel est de l'ordre de ±20 % selon le contenu des vidéos.

### 2.7 Paramètres avancés

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| **Emplacement (workspace)** | Dossier de travail choisi à la création. Les artefacts de génération vont sous `<emplacement>/generation/` (livrables sous `<emplacement>/generation/output/`). | choisi à la création |
| **Delete audio after STT** | Supprime les WAV extraits après transcription | `True` (économise du disque) |
| **Transcriptions en parallèle** (`stt_cloud_workers`) | Transcriptions STT cloud simultanées (effectif ; sans effet en STT local : 1 GPU). Réglable 1–8 (page Transcription). | 3 |
| **Appels LLM en parallèle** (`llm_workers`) | Appels LLM simultanés du pipeline (phases per-video + traduction/cohérence/résumés). Effectif ; la limite DeepSeek étant par concurrence, une valeur élevée reste sûre. Réglable 1–64 (page Modèle & coût). | 16 |
| **Formats d'export** (`export_formats`) | Formats proposés par le bouton **Exporter** de l'onglet Génération (page **Export**) : **Markdown / PDF / HTML**. À l'export, le **consolidé** et le **glossaire** sont écrits, un fichier par langue, dans le format choisi (`consolidated.{lang}.<ext>`, `glossary.{lang}.<ext>`). | aucun (opt-in) |

## 3. Surcouche des prompts (avancé)

Les prompts LLM par défaut peuvent être personnalisés sans toucher au
code source. Deux moyens : l'**éditeur intégré** (recommandé) ou le dépôt
manuel d'un fichier `.j2`.

### 3.1 Via l'éditeur intégré (recommandé)

Menu **Édition → Modifier les prompts…** ouvre un dialogue dédié :

- **Sidebar gauche** : liste des 8 templates LLM (phases 1-7 +
  sous-prompt 5a). Un astérisque ` *` est ajouté en face d'un template
  pour lequel un override est actif.
- **Description** courte de chaque phase et de son rôle dans le
  pipeline.
- **Bandeau d'état** : *« 📦 Prompt par défaut »* ou *« ✏️ Override
  personnalisé actif »*.
- **Éditeur monospace** avec coloration QSS, taille redimensionnable.
- **Bouton « 💾 Enregistrer »** : valide la syntaxe Jinja2 avant
  écriture dans `%APPDATA%\Fahmi2\prompts\`. Refus immédiat si le
  template contient une erreur de syntaxe, avec affichage du message
  d'erreur Jinja2 brut.
- **Bouton « ↩ Réinitialiser au défaut »** : supprime l'override (après
  confirmation) et restaure le template bundlé.
- Confirmation au changement de phase si des modifications ne sont pas
  sauvegardées (évite la perte involontaire).

Les overrides sont actifs **au prochain lancement de la phase**.

### 3.2 Via dépôt manuel (alternatif)

Pour les workflows scriptés, vous pouvez déposer directement les
fichiers :

1. Le dossier `%APPDATA%\Fahmi2\prompts\` est créé automatiquement au
   premier lancement.
2. Y déposer un fichier `.j2` (Jinja2) avec le **même nom** que le
   template par défaut. Templates disponibles :
   - `phase_1_term_extraction.j2`
   - `phase_2_glossary_reconciliation.j2`
   - `phase_3_reformulation.j2`
   - `phase_4_structuration.j2`
   - `phase_5_consolidation.j2`
   - `phase_5_video_summary.j2`
   - `phase_6_translation.j2`
   - `phase_7_coherence.j2`
3. Le prompt sera utilisé automatiquement au prochain run.

### 3.3 Variables disponibles dans chaque template

| Template | Variables clés |
|----------|----------------|
| `phase_1_term_extraction` | `source_language_label`, `style_label`, `style_directives`, `transcription_text` |
| `phase_2_glossary_reconciliation` | `source_language_label`, `style_label`, `style_directives`, `candidates_json` |
| `phase_3_reformulation` | `output_language_label`, `style_label`, `style_directives`, `glossary_terms`, `transcription_text` |
| `phase_4_structuration` | `output_language_label`, `style_label`, `style_directives`, `glossary_terms`, `reformulated_text` |
| `phase_5_video_summary` | `output_language_label`, `structured_markdown` |
| `phase_5_consolidation` | `output_language_label`, `style_label`, `style_directives`, `summaries_json` |
| `phase_6_translation` | `source_language_label`, `target_language_label`, `style_label`, `style_directives`, `glossary_terms`, `source_markdown` |
| `phase_7_coherence` | `output_language_label`, `style_label`, `style_directives`, `glossary_terms`, `consolidated_markdown` |
| `pedagogy_flashcards_concepts` | `output_language_label`, `audience_label`, `bloom_label`, `density_label`, `pedagogy_directives`, `glossary_terms`, `chapter_title`, `chapter_markdown` |
| `pedagogy_qcm` | *(idem flashcards concepts)* |
| `pedagogy_true_false` | *(idem flashcards concepts)* |
| `pedagogy_cloze` | *(idem flashcards concepts)* |
| `pedagogy_open_questions` | *(idem flashcards concepts)* |
| `pedagogy_revision_sheet` | *(idem flashcards concepts)* |
| `pedagogy_key_points` | *(idem flashcards concepts)* |
| `pedagogy_mock_exam` | `output_language_label`, `audience_label`, `bloom_label`, `density_label`, `pedagogy_directives`, `glossary_terms`, `consolidated_markdown` |

> Les 8 templates `pedagogy_*` (supports de révision) s'éditent dans le **même
> éditeur** (Édition → Modifier les prompts) que les phases de génération.

### 3.4 Validation et restauration

- L'éditeur intégré refuse d'enregistrer une syntaxe invalide.
- Si un override déposé manuellement est invalide, le `PromptLoader`
  retombe automatiquement sur le template par défaut et logge
  `PROMPT.INVALID_OVERRIDE` (consultable dans le panneau Logs).
- **Restaurer le défaut** : via le bouton *« ↩ Réinitialiser au défaut »*
  dans l'éditeur, ou en supprimant manuellement le fichier `.j2` dans
  `%APPDATA%\Fahmi2\prompts\`. Important : « défaut » = le template
  bundlé avec la version installée de l'application ; il n'y a pas de
  notion de « version d'usine » historique.

## 3bis. Réglages des supports pédagogiques

Onglet **Supports pédagogiques → ⚙ Réglages** (vue master-detail) :

| Catégorie | Réglages |
|-----------|----------|
| **Supports** | Sélection parmi les 8 types ; case « corrigé séparé » sur les supports évaluatifs (QCM, vrai/faux, cloze, questions ouvertes, examen blanc). |
| **Difficulté** | Public cible (découverte / lycée / licence / master-expert), objectif Bloom (auto / restituer / comprendre & appliquer / analyser & au-delà), densité (légère / standard / dense), directives libres. |
| **Langues** | Toutes les langues supportées : les supports sont rédigés dans la langue choisie même si le document source est dans une autre langue (l'orchestrateur résout une langue de contenu à partir d'un `consolidated.{lang}.md` existant). |
| **Modèle & coût** | Modèle LLM, mode raisonnement + niveau d'effort, température, **plafond budget** (interrompt proprement ; en génération parallèle, léger dépassement toléré par les requêtes déjà en vol), **tâches en parallèle** (défaut 16, plage 1–64 : nombre d'appels LLM concurrents pour générer les supports — la limite DeepSeek étant par concurrence, une valeur élevée reste sûre ; le parallélisme effectif est borné par le nombre de supports × langues). |
| **Export** | Formats proposés au bouton **Exporter** : Anki (`.apkg`), Markdown, PDF, HTML. Le Markdown des champs est converti en HTML à l'export Anki ; Markdown/PDF/HTML produisent **un fichier par support et par corrigé**. |

Le bouton **Estimer le coût** donne un ordre de grandeur (par support × langue ×
chapitre, selon densité et thinking) ; **Générer** lance la génération (progression
par support × langue, reprise *coarse* des supports déjà à jour) ; **Ouvrir le
dossier** ouvre `<emplacement>/pedagogy/` ; **Exporter** propose 4 formats :
- **Anki `.apkg`** (flashcards → Basic, textes à trous → Cloze, QCM → note custom ;
  GUID stables, sous-decks par support, tags support/langue/niveau/chapitre) ;
- **Markdown**, **PDF** et **HTML** : **un fichier par support et par corrigé**,
  nommés `<support>.<langue>.<ext>` et `<support>.<langue>.corrige.<ext>`
  (le HTML est un document autonome avec feuille de style intégrée).

## 4. Variables d'environnement (debug)

L'application respecte les variables Windows standards :

| Variable | Effet |
|----------|-------|
| `APPDATA` | Dossier racine des données utilisateur. Défaut : `%USERPROFILE%\AppData\Roaming`. |
| `LOCALAPPDATA` | Dossier racine du cache. Défaut : `%USERPROFILE%\AppData\Local`. |
| `USERPROFILE` | Profil utilisateur. Utilisé en fallback si `APPDATA`/`LOCALAPPDATA` sont absents. |

Ces variables permettent de **rediriger les données utilisateur** vers un
autre emplacement (utile pour les tests ou les installations atypiques).

## 5. Recommandations par usage

### 5.1 Petit projet de test (1-5 vidéos courtes)

- Provider STT : `openai_cloud` (rapide et négligeable en coût)
- Modèle LLM : `deepseek-v4-flash`
- Thinking : désactivé partout
- Température : 0.3 partout
- Plafond budget : 1 $

### 5.2 Production académique (30-50 vidéos)

- Provider STT : `faster_whisper_local` si GPU disponible (gratuit), sinon
  `openai_cloud`
- Modèle LLM : `deepseek-v4-pro` (qualité supérieure)
- Thinking activé + `HIGH` pour phases 4 (structuration), 5
  (consolidation), 7 (cohérence). `MAX` réservé si la qualité reste
  insuffisante (×6 sur l'output).
- Température : 0.2 pour traduction, 0.4 ailleurs
- Style : `académique`
- Plafond budget : 20-30 $ (vérifier d'abord avec **💵 Estimer le coût**)

### 5.3 Itération rapide sur un cours en cours d'écriture

- Provider STT : `openai_cloud`
- Modèle LLM : `deepseek-v4-flash`
- Style : `standard` ou personnalisé via directives
- Plafond budget : 5 $
- Utiliser la **reprise** : modifier les prompts via l'éditeur intégré
  (Édition → Modifier les prompts…), relancer uniquement les phases
  impactées en supprimant manuellement les artefacts correspondants
  dans `workspace/`.
