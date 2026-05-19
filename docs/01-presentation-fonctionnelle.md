# Fahmi2 — Présentation fonctionnelle

## 1. Contexte et problème adressé

Un enseignant en économie et finance produit un volume important de **vidéos
MP4 de cours oraux** (en français ou en anglais). Ce savoir est de qualité
mais reste **captif** du format vidéo : il n'est ni recherchable, ni
réutilisable pour produire des supports écrits, ni formalisé.

Fahmi2 résout ce problème en transformant ces vidéos en **documents Markdown
structurés** qui peuvent servir de référence écrite, de support distribuable,
ou d'entrée pour d'autres outils de mise en forme (DOCX, PDF…).

## 2. Vision produit

Une **application desktop locale** qui :

- prend en entrée **un dossier contenant 10 à 50 vidéos MP4** ;
- produit en sortie **un document consolidé** par langue de sortie demandée,
  accompagné des **documents par vidéo** et d'un **glossaire** ;
- garantit la **fidélité au discours oral** (pas d'hallucination,
  reformulation pure) tout en respectant **les règles de l'art de l'écrit**
  dans la langue cible ;
- s'installe **en un double-clic** et se pilote **entièrement via l'interface
  graphique** (aucune édition de fichier requise).

## 3. Profil de l'utilisateur cible

- **Enseignant** ou **formateur** d'un domaine où la précision terminologique
  compte (économie, finance, sciences, ingénierie).
- Pas d'expertise technique requise : connaissance basique de Windows,
  capacité à saisir une clé API dans un formulaire.
- Travaille sur son **poste personnel** (mono-utilisateur), avec ou sans GPU
  NVIDIA.

## 4. Fonctions principales

### 4.1 Gestion des projets

Un **Projet** dans Fahmi2 = un dossier d'entrée avec ses vidéos + un jeu de
paramètres + un historique de runs (exécutions du pipeline).

- Création d'un projet via un **assistant en une page** ;
- **Historique** complet des runs visibles dans la sidebar ;
- Possibilité de **rouvrir** un projet ancien, voir son rapport, ou le
  relancer.

### 4.2 Pipeline de traitement

Pour chaque projet, le **pipeline en 8 phases** transforme les vidéos en
documents :

| Phase | Description |
|-------|-------------|
| 0. STT | Transcription audio → texte (Whisper local ou cloud) |
| 1. Termes | Extraction des termes techniques candidats par vidéo |
| 2. Glossaire | Réconciliation cross-vidéos pour produire un glossaire master |
| 3. Reformulation | Reformulation écrite fidèle, par vidéo, en langue source |
| 4. Structuration | Mise en forme Markdown avec titres, intro, conclusion, admonitions sémantiques (remarques, exemples, définitions, exercices) |
| 5. Consolidation | Production des méta-éléments (titre global, introduction générale, plan, conclusion générale) pour un document consolidé |
| 6. Traduction | Production des artefacts dans toutes les langues de sortie demandées |
| 7. Cohérence | Passe finale de relecture des méta-éléments |

### 4.3 Paramétrage métier

L'utilisateur configure **via l'interface** (et **uniquement** via l'interface) :

- **Clés API** : OpenAI (pour Whisper cloud), DeepSeek (pour les phases LLM).
- **Provider STT** : Whisper local (GPU NVIDIA requis) ou OpenAI cloud.
- **Modèle LLM** : DeepSeek v4 Flash ou Pro.
- **Mode raisonnement** (`thinking` activé / désactivé), **niveau de
  raisonnement** (`HIGH` / `MAX`) et **température**, configurables
  **par phase LLM** indépendamment.
- **Langue source** + **langues de sortie** (FR / EN en v1).
- **Style de rendu** : décontracté / standard / professionnel / académique.
- **Directives stylistiques libres** en texte.
- **Plafond budget** optionnel avec arrêt automatique propre.
- **Surcouche utilisateur des prompts** via éditeur intégré
  (menu **Édition → Modifier les prompts…**) : tous les templates des 7
  phases LLM peuvent être personnalisés sans toucher au code, avec
  validation Jinja2 et retour au défaut bundlé d'un clic.

### 4.4 Pilotage d'un run

- Lancement, **pause**, **reprise**, **annulation** d'un run via les boutons
  de la barre d'en-tête.
- **Reprise fine par phase** après pause, annulation ou crash : aucun
  travail perdu, le pipeline reprend exactement où il s'était arrêté.
- **Estimation de coût pré-run** : bouton **💵 Estimer le coût** dans
  la barre d'en-tête. Le calcul intègre le modèle, le nombre de langues
  cibles et le **surcoût empirique du mode thinking par phase** selon le
  niveau de raisonnement choisi.
- **Coût cumulé** et **durée live** affichés en temps réel pendant le
  Run.
- **Ouvrir le dossier de sortie** en un clic depuis la barre
  d'en-tête à la fin du Run.

### 4.5 Visualisation de l'avancement

L'interface principale (cockpit dense, thème **Clair Fluent**) affiche en
temps réel :

- **Une matrice 2D** : une ligne par vidéo, une colonne par phase. Chaque
  cellule affiche le statut (en attente, en cours, succès, échec, sauté)
  avec un symbole **et une couleur** (vert succès, bleu en cours, gris
  attente, rouge échec, indigo sauté). Au survol : détail (timestamps,
  coût, retries, erreur éventuelle). En-têtes courts et lisibles (STT,
  Termes, Glossaire, Reformul., Structur., Consolid., Traduction,
  Cohérence).
- **Cinq cartes d'indicateurs** : Statut, Vidéos, Phases, **Durée**,
  Coût. Chaque carte = icône + titre + valeur en grand + sous-info. La
  carte Durée est mise à jour chaque seconde tant que le Run tourne.
- **Un panneau de logs** filtrable par sévérité, avec coloration
  (INFO gris, WARN orange, ERREUR rouge, FATAL rouge gras), horodatage
  compact `HH:MM:SS` et police monospace.

### 4.6 Livrables produits

À l'issue d'un run, le dossier `output/` contient pour chaque langue :

- `consolidated.{lang}.md` — document consolidé navigable :
  - Titre global + introduction générale.
  - **Sommaire automatique** complet avec ancres GFM cliquables vers
    chaque section.
  - Chapitres et sections **numérotés hiérarchiquement** (1, 1.1, 1.1.1).
  - Contenu des vidéos recopié tel quel (pas de réécriture par le LLM).
  - **Admonitions élégantes** : 📝 Remarque, 💡 Exemple, 📖 Définition,
    🎯 Exercice (blockquotes Markdown avec emoji, plus lisibles que les
    GFM `[!NOTE]` bruts).
  - Conclusion générale.
- `glossary.{lang}.md` — glossaire en **tableau Markdown 4 colonnes**
  trié alphabétiquement :
  - **Terme** (forme longue), **Acronyme** (`PIB`, `ROI`, `IFRS`…),
    **Signification** (expansion littérale de l'acronyme dans sa langue
    d'origine — *Return On Investment* pour ROI, même dans un glossaire
    FR), **Définition** (contextuelle).
- `per-video/{lang}/<video_id>.md` — un document Markdown autonome par
  vidéo, avec son propre titre, intro, conclusion et admonitions
  sémantiques.

Tous les fichiers sont en **Markdown UTF-8**, ouvrables dans n'importe quel
éditeur, dans VS Code, Obsidian, ou convertibles vers DOCX/PDF/HTML via
pandoc.

## 5. Promesses de qualité

### 5.1 Fidélité au discours

- Le pipeline **ne réécrit jamais** le contenu détaillé des vidéos lors de
  la consolidation. Les chapitres sont les sorties textuelles structurées
  des vidéos individuelles, recopiées telles quelles.
- Le LLM est explicitement instruit de **ne pas inventer** de contenu non
  présent dans la transcription.

### 5.2 Cohérence terminologique

- Un **glossaire master** est construit en deux passes (extraction puis
  réconciliation) à partir des termes extraits indépendamment de chaque
  vidéo.
- Les termes pertinents sont ré-injectés en contexte LLM lors de la
  reformulation, de la structuration et de la traduction pour garantir
  l'orthographe et le sens cohérents à travers tout le batch.
- L'**expansion d'acronyme** (champ `acronym_expansion`) est conservée
  dans sa langue d'origine et n'est jamais traduite : un glossaire FR
  expose `ROI = Return On Investment`, un glossaire EN expose
  `PIB = Produit Intérieur Brut`. Le prompt de traduction est
  explicitement instruit de préserver le contenu de la colonne
  *Signification* / *Meaning* d'un tableau de glossaire.

### 5.3 Robustesse

- **Checkpointing fin** : chaque phase produit un artefact persistant ; la
  reprise après interruption est immédiate.
- **Retry policy** avec backoff exponentiel sur les erreurs transitoires
  (rate limit, server error, réseau).
- **Logs structurés JSONL** : exploitables post-mortem en cas d'incident.
- **Stockage chiffré** des clés API (Windows DPAPI).

### 5.4 Coût maîtrisé

- **Estimation pré-run** accessible à tout moment depuis la barre
  d'en-tête, qui intègre :
  - Le modèle LLM (Flash vs Pro).
  - Le provider STT (gratuit en local, ~0,006 $/min en cloud).
  - La configuration **phase par phase** : mode thinking et niveau
    de raisonnement, traduits en un multiplicateur empirique appliqué
    aux tokens de sortie (le mode thinking génère typiquement 2 à 6×
    plus de tokens de complétion).
- **Plafond budget** configurable avec **arrêt propre** (jamais d'interruption
  brutale au milieu d'un appel LLM en cours).
- **Tarification DeepSeek transparente** (input cache hit / cache miss /
  output) dans le code source, mise à jour facile.

## 6. Périmètre v1 — limites assumées

### Inclus

- 2 langues : **français et anglais**, dans les deux sens.
- 2 providers STT (FasterWhisper local + OpenAI cloud).
- 1 fournisseur LLM (**DeepSeek v4**, deux modèles).
- 4 styles de rendu.
- Format de sortie : **Markdown** uniquement.
- Plateforme : **Windows 11** (10 minimum).

### Hors v1

- Multi-utilisateur, collaboration, cloud sync.
- Édition manuelle des transcriptions dans l'UI.
- Export PDF / DOCX / HTML natif (conversion externe possible).
- Autres langues que FR / EN.
- Autres LLM que DeepSeek (architecture prête mais non implémenté).
- Auto-update.
- Signature de code (l'EXE n'est pas signé en v1).

## 7. Cas d'usage typiques

### Cas A : prof de macroéconomie L3

- 30 vidéos de cours hebdomadaires de 25 min chacune (~12 h d'audio).
- Souhaite produire un **support PDF complet** consolidé en français pour
  ses étudiants, plus une version anglaise pour le programme international.
- Configuration : STT cloud (~4 $), DeepSeek v4 flash, style académique,
  sortie FR + EN.
- Durée totale : ~3 h. Coût : ~10-15 $ tout compris.

### Cas B : formateur en finance d'entreprise

- 15 vidéos de séminaire de 45 min chacune.
- Souhaite uniquement la version FR, style professionnel, avec un glossaire
  riche pour l'autoformation.
- Configuration : STT local (GPU disponible, gratuit), DeepSeek v4 pro,
  pas de plafond.
- Durée : ~1,5 h. Coût : ~8-12 $ (LLM seul).

## 8. Bénéfices clés

1. **Gain de temps** : ce qui prendrait des dizaines d'heures à transcrire
  et reformuler manuellement se fait en quelques heures, sans intervention.
2. **Cohérence** : terminologie homogène sur 50 vidéos, ce qui est très
  difficile à obtenir manuellement.
3. **Réutilisabilité** : les sorties Markdown peuvent alimenter un site, un
  LMS, une base de connaissances, des supports imprimés.
4. **Maîtrise du coût** : estimation et plafond automatiques, pas de
  surprise sur la facture.
5. **Discrétion** : tout reste local, aucune télémétrie ; les clés API sont
  chiffrées sur disque ; les contenus quittent le poste uniquement quand
  l'utilisateur a choisi un provider cloud.
