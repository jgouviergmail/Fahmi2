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

- prend en entrée un **dossier de sources hétérogènes** — **vidéos** (MP4,
  MKV, MOV, WebM…), **fichiers audio** (WAV, MP3, M4A, FLAC…), **documents
  texte** (PDF, Word, Markdown, txt) — et/ou des **liens YouTube** (vidéos
  unitaires), avec **contrôle de l'ordre** de traitement et possibilité
  d'**exclure** certaines sources ;
- produit en sortie **un document consolidé** par langue de sortie demandée,
  accompagné des **documents par source** et d'un **glossaire** ;
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

Un **Projet** dans Fahmi2 = une **identité minimale** (nom + emplacement) à
laquelle s'attachent des réglages **par fonctionnalité** + un historique de runs.
L'application est organisée en **onglets de fonctionnalité** : **Génération**
(vidéos → documents), **Supports pédagogiques** (document consolidé + glossaire
→ flashcards, QCM, fiches, examen blanc…) et **Dialogue** (chat conversationnel
ancré sur le corpus : questions en langage naturel, réponses **citées** et
diffusées **en streaming**, fidélité configurable strict/augmenté, retrieval
lexical ou sémantique, conversations persistées). L'onglet Supports pédagogiques propose
des **réglages** (⚙ : supports, difficulté, langues, modèle & coût), un bouton
**Générer** et **Estimer le coût**, une **table de progression** (support × langue)
et un **bandeau d'état** (« génération requise » / « prêt » / « à jour » /
« périmé »). Les supports sont écrits sous `<emplacement>/pedagogy/`. Un bouton
**Exporter** propose 5 formats : **Anki `.apkg`** (flashcards, textes à trous, QCM ;
ré-import sans doublon), **Markdown**, **PDF**, **HTML** et **Word (`.docx`)** — ces
quatre derniers produisant **un fichier par support et par corrigé**
(`<support>.<langue>.<ext>` / `<support>.<langue>.corrige.<ext>`), chacun autonome.

- Création d'un projet via un **dialogue minimal** (nom + emplacement) ; les
  réglages de génération se configurent ensuite depuis l'onglet **Génération →
  ⚙ Réglages** ;
- **Historique** complet des runs visibles dans la sidebar ;
- Possibilité de **rouvrir** un projet ancien, voir son rapport, ou le
  relancer.

### 4.2 Pipeline de traitement

Pour chaque projet, le **pipeline en 8 phases** transforme les sources en
documents :

| Phase | Description |
|-------|-------------|
| 0. STT | Transcription audio → texte (Whisper local ou cloud ; les documents texte sont extraits sans STT) |
| 1. Termes | Extraction des termes techniques candidats par source |
| 2. Glossaire | Réconciliation cross-sources pour produire un glossaire master |
| 3. Reformulation | Reformulation écrite fidèle, par source, en langue source |
| 4. Structuration | Mise en forme Markdown avec titres, intro, conclusion, admonitions sémantiques (remarques, exemples, définitions, exercices) |
| 5. Consolidation | Assemblage du document consolidé selon le **mode choisi** (cf. §4.3) : **ordonné** (1 source = 1 chapitre, contenu recopié) ou **refonte thématique** (le LLM agrège/restructure transversalement par thème) |
| 6. Traduction | Production des artefacts dans toutes les langues de sortie demandées |
| 7. Cohérence | Passe finale de relecture des méta-éléments |

### 4.3 Paramétrage métier

L'utilisateur configure **via l'interface** (et **uniquement** via l'interface) :

- **Clés API** : OpenAI (pour Whisper cloud), DeepSeek (pour les phases LLM).
- **Provider STT** : Whisper local (GPU NVIDIA requis) ou OpenAI cloud (gère les
  longues vidéos via compression Opus + découpage automatiques, transparent).
- **Modèle LLM** : DeepSeek v4 Flash ou Pro.
- **Mode raisonnement** (`thinking` activé / désactivé), **niveau de
  raisonnement** (`HIGH` / `MAX`) et **température**, configurables
  **par phase LLM** indépendamment.
- **Langues du document** (français, anglais, allemand, espagnol, italien,
  chinois, arabe) : langues produites + **langue principale** (l'originale, rédigée
  directement ; les autres en sont traduites).
- **Style de rendu** : décontracté / standard / professionnel / académique.
- **Mode de consolidation** : **ordonné** (1 source = 1 chapitre, contenu recopié
  dans l'ordre choisi) ou **refonte thématique** (le LLM agrège et restructure
  transversalement les contenus de toutes les sources par thème — synthèse
  journalistique, rigueur sur le fond / souplesse sur la forme ; en ce mode,
  l'ordre des sources est sans effet).
- **Directives stylistiques libres** en texte.
- **Plafond budget** optionnel avec arrêt automatique propre.
- **Surcouche utilisateur des prompts** via éditeur intégré
  (menu **Édition → Modifier les prompts…**) : tous les templates des 7
  phases LLM (dont les **3 prompts du mode thématique**), des **8 supports
  pédagogiques** et des **3 prompts du Dialogue** peuvent être personnalisés sans
  toucher au code, avec validation Jinja2 et retour au défaut bundlé d'un clic.

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
- **Exporter** les livrables de la génération (document **consolidé** et
  **glossaire**, un fichier par langue) en **Markdown**, **PDF**, **HTML** ou
  **Word (`.docx`)** vers un dossier choisi. Les formats proposés se cochent dans
  **⚙ Réglages → Export** (aucun par défaut — opt-in).
- **Traitement parallèle** : les phases par source (transcription cloud,
  extraction de termes, reformulation, structuration) traitent plusieurs sources
  simultanément, et les phases finales parallélisent traduction et cohérence ;
  le nombre d'appels concurrents est réglable. La transcription **locale** reste
  séquentielle (un seul GPU).

### 4.5 Visualisation de l'avancement

L'interface principale (cockpit dense, thème **Clair Fluent**) affiche en
temps réel :

- **Une matrice 2D** : une ligne par source, une colonne par phase. Chaque
  cellule affiche le statut (en attente, en cours, succès, échec, sauté)
  avec un symbole **et une couleur** (vert succès, bleu en cours, gris
  attente, rouge échec, indigo sauté). Au survol : détail (timestamps,
  coût, retries, erreur éventuelle). En-têtes courts et lisibles (STT,
  Termes, Glossaire, Reformul., Structur., Consolid., Traduction,
  Cohérence).
- **Six cartes d'indicateurs** : Statut, Sources, Phases, Langues, **Durée**,
  Coût. Chaque carte = icône + titre + valeur en grand + sous-info. La
  carte Durée est mise à jour chaque seconde tant que le Run tourne.
- **Un panneau de logs** filtrable par sévérité, avec coloration
  (INFO gris, WARN orange, ERREUR rouge, FATAL rouge gras), horodatage
  compact `HH:MM:SS` et police monospace.

### 4.6 Livrables produits

À l'issue d'un run, le dossier `output/` contient pour chaque langue :

- `consolidated.{lang}.md` — document consolidé navigable :
  - Titre global, **résumé exécutif** (abstract synthétique), puis introduction générale.
  - **Sommaire automatique** complet avec ancres GFM cliquables vers
    chaque section.
  - Chapitres et sections **numérotés hiérarchiquement** (1, 1.1, 1.1.1).
  - Contenu des sources recopié tel quel (pas de réécriture par le LLM).
  - **Admonitions élégantes** : 📝 Remarque, 💡 Exemple, 📖 Définition,
    🎯 Exercice (blockquotes Markdown avec emoji, plus lisibles que les
    GFM `[!NOTE]` bruts). Les emoji s'affichent en Markdown, HTML et Word ; ils
    sont **omis à l'export PDF** (le moteur de rendu ne sait pas dessiner les
    emoji couleur — le texte de l'admonition, lui, reste intact).
  - Conclusion générale.
- `glossary.{lang}.md` — glossaire en **tableau Markdown 4 colonnes**
  trié alphabétiquement :
  - **Terme** (forme longue), **Acronyme** (`PIB`, `ROI`, `IFRS`…),
    **Signification** (expansion littérale de l'acronyme dans sa langue
    d'origine — *Return On Investment* pour ROI, même dans un glossaire
    FR), **Définition** (contextuelle).
- `per-video/{lang}/<source_id>.md` — un document Markdown autonome par
  source, avec son propre titre, intro, conclusion et admonitions
  sémantiques.

Tous les fichiers sont en **Markdown UTF-8**, ouvrables dans n'importe quel
éditeur, dans VS Code ou Obsidian. L'**export intégré** produit en plus, à la
demande, des versions **PDF**, **HTML** et **Word (`.docx`)** (cf. § 4.4).

### 4.7 Dialogue (chat ancré sur le corpus)

Un troisième onglet, **Dialogue**, permet d'**interroger le cours** en langage
naturel une fois la génération produite. Les réponses sont **ancrées** sur le
document consolidé et le glossaire, **citées** (chapitre › section, cliquables) et
**diffusées en streaming**.

- **Fidélité configurable** : *strict* (réponse uniquement à partir du cours,
  refus poli hors-corpus) ou *augmenté* (complément de connaissances générales
  clairement balisé).
- **Recherche de passages** : lexicale (hors-ligne) ou sémantique (embeddings
  OpenAI, **modèle configurable**), avec un mode **automatique** et une
  reformulation de requête à la demande.
- **Langue au choix par conversation** : si la génération a produit plusieurs
  langues, un sélecteur fixe la langue d'une nouvelle conversation — le Dialogue
  **lit, cite et répond** dans cette langue, glossaire cité entièrement localisé
  (terme + définition).
- **Conversations** multiples persistées par projet, **supprimables** ; **coût**
  par message et cumulé **exhaustif** (réponse + embeddings + reformulation).
- Réglages (fidélité, retrieval, modèles LLM/embedding) et **prompts éditables**
  comme le reste.

## 5. Promesses de qualité

### 5.1 Fidélité au discours

- En mode de consolidation **ordonné** (défaut), le pipeline **ne réécrit
  jamais** le contenu détaillé : les chapitres sont les sorties structurées des
  sources individuelles, recopiées telles quelles (1 source = 1 chapitre).
- En mode **refonte thématique**, le LLM **réorganise et reformule** les contenus
  par thème, mais sous une règle stricte de **rigueur sur le fond** : interdiction
  d'inventer ou d'ajouter des faits, préservation des chiffres/données/raisonnements
  (garantie par un relevé factuel tracé + un double contrôle de couverture), et
  **conflits entre sources présentés** au lecteur sans arbitrage. La souplesse ne
  porte que sur la **forme** (fusion, déduplication, transitions, structure).
- Dans les deux modes, le LLM est explicitement instruit de **ne pas inventer**
  de contenu absent des sources.

### 5.2 Cohérence terminologique

- Un **glossaire master** est construit en deux passes (extraction puis
  réconciliation) à partir des termes extraits indépendamment de chaque
  source.
- Les termes pertinents sont ré-injectés en contexte LLM lors de la
  reformulation, de la structuration et de la traduction pour garantir
  l'orthographe et le sens cohérents à travers tout le batch.
- **Localisation des termes par langue** : pour chaque langue produite, les termes
  du glossaire sont traduits vers leur **équivalent métier consacré** (« Bilan » →
  « Balance sheet », « Bilanz »…), **sauf** les termes internationaux, noms propres,
  marques ou normes (IFRS, WACC, ROI, Big Four…) qui sont conservés tels quels — la
  décision se prenant terme par terme. Le **même terme localisé** est utilisé dans le
  glossaire, le document consolidé, les supports pédagogiques et le Dialogue.
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

- 7 langues, dans les deux sens : **français, anglais, allemand, espagnol,
  italien, chinois, arabe**.
- 2 providers STT (FasterWhisper local + OpenAI cloud).
- 1 fournisseur LLM (**DeepSeek v4**, deux modèles).
- 4 styles de rendu.
- Formats de sortie : génération et supports pédagogiques exportables en
  **Markdown**, **PDF**, **HTML** et **Word (`.docx`)** ; les supports ajoutent
  l'**Anki `.apkg`**. Le rendu PDF gère le **chinois** (police système Microsoft
  YaHei, **retours à la ligne** automatiques) et l'**arabe** (droite-à-gauche +
  liaison contextuelle) ; l'**arabe** est aussi rendu **droite-à-gauche en Word**
  (bidi + inversion des colonnes du tableau). Le **glossaire** s'exporte en
  **paysage** (PDF et Word).
- **Dialogue** : chat ancré sur le corpus (citations + streaming), retrieval
  lexical (hors-ligne) ou sémantique (embeddings OpenAI ; recommandé pour le
  chinois).
- Plateforme : **Windows 11** (10 minimum).

### Hors v1

- Multi-utilisateur, collaboration, cloud sync.
- Édition manuelle des transcriptions dans l'UI.
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
