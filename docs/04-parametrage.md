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

Accès : menu **Fichier → Nouveau projet** (ou édition d'un projet existant).

### 2.1 Identification

| Paramètre | Description |
|-----------|-------------|
| **Nom** | Libre, sert d'étiquette dans la sidebar. Ex: « Cours macroéconomie L3 ». |
| **Dossier d'entrée** | Dossier contenant les vidéos source. Doit exister et être accessible en lecture. |

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
| **Provider STT** | `faster_whisper_local` (GPU NVIDIA requis) ou `openai_cloud`. | Local : gratuit / Cloud : ~0,006 $/min |
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
| **Thinking activé** | Mode raisonnement DeepSeek (chain-of-thought visible) | bool | Off par défaut, on pour phases critiques (consolidation, traduction) |
| **Température** | Variabilité de la sortie LLM | 0.0 — 2.0 | 0.2-0.4 pour structuration ; 0.0-0.2 pour traduction ; 0.3-0.6 pour reformulation |
| **Max retries** | Tentatives en cas d'erreur transitoire | 0 — ∞ | 5 par défaut |

### 2.6 Plafond budget

| Paramètre | Description |
|-----------|-------------|
| **Plafond USD** | Coût maximum autorisé pour le run. À 0 ou non défini : pas de plafond. Sinon, le run se met en pause propre dès que le coût cumulé approche du plafond. |

L'arrêt est toujours **propre** : jamais d'interruption au milieu d'un
appel LLM en cours. La pause se produit à la prochaine frontière sûre.

### 2.7 Paramètres avancés

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| **Workspace folder** | Dossier de travail (artefacts intermédiaires) | `<input_folder>/.fahmi2/` |
| **Delete audio after STT** | Supprime les WAV extraits après transcription | `True` (économise du disque) |
| **stt_cloud_workers** | Threads parallèles pour STT cloud | 3 |
| **llm_workers** | Threads parallèles pour LLM | 4 |

## 3. Surcouche des prompts (avancé)

Les prompts par défaut bundlés dans l'application peuvent être surchargés
par fichier-utilisateur.

### Procédure

1. Créer le dossier `%APPDATA%\Fahmi2\prompts\` s'il n'existe pas (créé
   automatiquement au premier lancement).
2. Y déposer un fichier `.j2` (Jinja2) avec le **même nom** que le template
   par défaut. Templates disponibles :
   - `phase_1_term_extraction.j2`
   - `phase_2_glossary_reconciliation.j2`
   - `phase_3_reformulation.j2`
   - `phase_4_structuration.j2`
   - `phase_5_consolidation.j2`
   - `phase_5_video_summary.j2`
   - `phase_6_translation.j2`
   - `phase_7_coherence.j2`
3. Le prompt sera utilisé automatiquement au prochain run.

### Variables disponibles dans chaque template

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

### Validation

Si la surcouche contient une **erreur de syntaxe Jinja2**, l'application
revient automatiquement sur le template par défaut et logge un événement
`PROMPT.INVALID_OVERRIDE` que vous pouvez consulter dans le panneau Logs.

### Restaurer le défaut

Supprimer le fichier `.j2` dans `%APPDATA%\Fahmi2\prompts\`. L'application
reprend immédiatement le template bundlé au prochain run.

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
- Thinking : activé pour phases 4 (structuration), 5 (consolidation),
  7 (cohérence)
- Température : 0.2 pour traduction, 0.4 ailleurs
- Style : `académique`
- Plafond budget : 20-30 $

### 5.3 Itération rapide sur un cours en cours d'écriture

- Provider STT : `openai_cloud`
- Modèle LLM : `deepseek-v4-flash`
- Style : `standard` ou personnalisé via directives
- Plafond budget : 5 $
- Utiliser la **reprise** : modifier les prompts via override, relancer
  uniquement les phases impactées en supprimant manuellement les artefacts
  correspondants dans `workspace/`.
