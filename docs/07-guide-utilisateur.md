# Fahmi2 — Guide utilisateur

Document destiné à l'utilisateur final non-technicien. Démarrage en moins
de 10 minutes.

## 1. Qu'est-ce que Fahmi2 ?

Fahmi2 transforme automatiquement vos cours — **vidéos, fichiers audio, liens
YouTube ou documents texte** (PDF, Word, Markdown, txt) — en documents écrits
structurés en Markdown, avec un glossaire et un document consolidé, dans la
langue de votre choix (FR ou EN).

L'application tourne **entièrement sur votre poste** : pas de serveur, pas
de cloud sauf si vous choisissez explicitement OpenAI Whisper cloud ou
DeepSeek (les contenus envoyés au cloud le sont alors exclusivement par
ces deux APIs, sous vos clés).

## 2. Installation

1. Téléchargez `Fahmi2-X.Y.Z-win64.zip`.
2. Décompressez-le dans un dossier (par exemple, sur votre Bureau ou dans
   `C:\Apps\Fahmi2\`).
3. Double-cliquez sur **`Fahmi2.exe`**.
4. Au tout premier lancement, Windows peut afficher *« Windows a protégé
   votre PC »* (éditeur inconnu). Cliquez sur **« Plus d'infos »** puis
   **« Exécuter quand même »**. Cet avertissement n'apparaîtra qu'une seule
   fois.

Vous y êtes. Pas d'installation système, pas de droits administrateur.

## 3. Première configuration : clés API

Pour fonctionner, l'application a besoin d'une ou deux clés d'API que vous
devez obtenir auprès des fournisseurs :

- **Clé DeepSeek** (obligatoire) — pour la reformulation et la
  structuration. Inscrivez-vous sur https://platform.deepseek.com et
  générez une clé.
- **Clé OpenAI** (optionnelle) — uniquement si vous utilisez Whisper
  cloud pour la transcription. Inscrivez-vous sur
  https://platform.openai.com.

**Pour les saisir** :

1. Menu **Édition → Paramètres globaux**.
2. Collez vos clés dans les champs correspondants.
3. Cliquez sur **Save**.

Vos clés sont **chiffrées sur votre disque** par le système Windows
(DPAPI). Elles ne peuvent être déchiffrées que par votre compte Windows.

## 4. Créer un projet

**Fichier → Nouveau projet** : donnez un **nom** et choisissez un **emplacement**
(dossier de travail du projet), puis cliquez sur **OK**. Le projet apparaît dans
la liste à gauche.

Sélectionnez-le, puis dans l'onglet **Génération** cliquez sur **⚙ Réglages** pour
configurer la génération (vue à 6 catégories) :

| Catégorie | Champs |
|-----------|--------|
| **Entrée & langues** | Dossier d'entrée (vidéos/audios/documents) · Liens YouTube · Ordre & exclusion des sources · Langues du document (langues produites + laquelle est la **principale**/originale) |
| **Style** | Style (`décontracté`/`standard`/`professionnel`/`académique`) · **Mode de consolidation** (Ordonné : un chapitre par source, dans l'ordre ; ou Refonte thématique : l'IA réorganise et fusionne tout par thèmes, comme une synthèse — l'ordre des sources n'a alors plus d'effet) · Directives libres |
| **Transcription** | Provider STT (`openai_cloud` sans GPU, sinon `faster_whisper_local`) · *Transcriptions en parallèle* (cloud) |
| **Modèle & coût** | Modèle LLM (`deepseek-v4-flash` pour démarrer) · Plafond budget · *Appels LLM en parallèle* |
| **Phases** | Thinking, effort, température, retries par phase LLM (avancé) |
| **Export** | Formats d'export proposés : Markdown / PDF / HTML / Word (`.docx`) (aucun par défaut) |

Validez : l'aperçu des sources détectées s'affiche dans le cockpit.

## 5. Lancer le traitement

1. Sélectionnez votre projet dans la liste à gauche.
   L'application présente deux onglets : **Génération** (le cockpit ci-dessous) et
   **Supports pédagogiques** (flashcards, QCM, fiches… à générer une fois la
   Génération terminée — voir §8).
2. (Optionnel mais recommandé) Cliquez sur **💵 Estimer le coût** pour
   voir le budget prévu avant de lancer. Le dialogue affiche les vidéos
   détectées, la durée totale, une **décomposition par phase** (en tenant
   compte du mode raisonnement si activé) et un **total sous forme de
   fourchette indicative** (≈ X, fourchette ±33 %), avec un avertissement
   si le haut de fourchette peut dépasser le plafond.
3. Cliquez sur **▶ Lancer** en haut.

La grille au centre commence à se remplir :

- Une **ligne par vidéo**.
- Une **colonne par phase** (8 colonnes : STT, Termes, Glossaire,
  Reformul., Structur., Consolid., Traduction, Cohérence).
- Chaque case montre l'avancement avec **couleur + symbole** :
  - `·` gris : en attente
  - `▶` bleu : en cours
  - `✓` vert : terminé
  - `✗` rouge : échec (rare, voir [Dépannage](#10-dépannage))
  - `↷` indigo : sauté (déjà fait au précédent run)

En haut, **5 cartes** affichent :

- **Statut** du projet (En cours / En pause / Terminé…)
- **Vidéos** terminées (ex: *« 3 / 12 »*)
- **Phases** terminées (ex: *« 15 / 96 »*)
- **Durée** écoulée (mise à jour en direct chaque seconde)
- **Coût** cumulé en USD (avec plafond si défini)

En bas, le panneau **Logs** liste les dernières actions et messages,
colorés par niveau (gris/orange/rouge).

## 6. Mettre en pause ou annuler

- **⏸ Pause** : interrompt le traitement à la prochaine étape sûre. Vous
  pouvez fermer l'application — le travail est sauvegardé.
- **▶ Reprendre** : reprend exactement là où vous vous étiez arrêté. Aucun
  travail n'est refait.
- **✕ Annuler** : marque le run comme annulé. Vous pourrez relancer plus
  tard si vous le souhaitez.
- **↺ Réinitialiser** : supprime **tout ce qui a été généré** pour l'onglet
  courant (livrables et historique pour la Génération ; supports pour les Supports
  pédagogiques), après confirmation. Irréversible ; indisponible pendant un run.

Dans la liste des projets (gauche), chaque projet est préfixé par deux icônes de
statut — **G** (Génération) puis **P** (Supports pédagogiques) — reflétant le
dernier état de chaque fonctionnalité (créé, en cours ▶, terminé ✓, échec ✗,
annulé ⊘) ; survolez pour le détail.

## 7. Récupérer les fichiers produits

Quand le projet est terminé (statut **Terminé**), cliquez sur le bouton
**📂 Dossier de sortie** en haut à droite : l'explorateur Windows
s'ouvre directement sur le bon dossier. Vous y trouverez :

```
<emplacement>/generation/output/
├── consolidated.fr.md     ← Le document consolidé en français (navigable)
├── consolidated.en.md     ← Le document consolidé en anglais (si demandé)
├── glossary.fr.md         ← Le glossaire en français (tableau)
├── glossary.en.md         ← Le glossaire en anglais
└── per-video/
    ├── fr/
    │   ├── XXX.md         ← Un fichier par vidéo (FR)
    │   └── …
    └── en/
        └── …
```

**Document consolidé** : titre global, introduction, **sommaire
cliquable** vers chaque chapitre et sous-section, chapitres
**numérotés hiérarchiquement** (1, 1.1, 1.1.1…), conclusion.
Insertions sémantiques élégantes : 📝 Remarque, 💡 Exemple, 📖
Définition, 🎯 Exercice.

**Glossaire** : tableau **Terme / Acronyme / Signification /
Définition**. La colonne *Signification* reste dans la langue
d'origine de l'acronyme (par exemple ROI = *Return On Investment*,
même dans un glossaire en français).

Tous les fichiers sont en **Markdown**, lisibles dans n'importe quel
éditeur (Bloc-notes, VS Code, Typora, Obsidian…). Le sommaire avec
liens cliquables s'affiche directement dans VS Code, Obsidian, GitHub,
GitLab, etc.

**Exporter en PDF, HTML ou Word** : le bouton **📦 Exporter** (en haut à droite)
écrit le document consolidé et le glossaire — un fichier par langue
(`consolidated.{langue}`, `glossary.{langue}`) — dans le format choisi
(**Markdown**, **PDF**, **HTML** ou **Word `.docx`**), vers un dossier de votre
choix. Cochez d'abord les formats voulus dans **⚙ Réglages → Export** (aucun n'est
coché par défaut). Le HTML est un document autonome, ouvrable dans un navigateur ;
le PDF gère aussi le **chinois** et l'**arabe** (droite-à-gauche).

## 8. Générer des supports de révision

Une fois la Génération terminée, l'onglet **Supports pédagogiques** transforme le
document consolidé et le glossaire en matériel de révision : flashcards, QCM,
vrai/faux, textes à trous, questions ouvertes, fiches de révision, points clés et
examen blanc.

> **Prérequis** : avoir lancé au moins une fois la **Génération** sur le projet
> (un document consolidé et un glossaire doivent exister). Les supports sont
> produits **à partir** de ce contenu.

### Configurer

Sélectionnez le projet, ouvrez l'onglet **Supports pédagogiques**, puis cliquez
sur **⚙ Réglages** (même vue à catégories que la Génération) :

| Catégorie | Champs |
|-----------|--------|
| **Supports** | Types à générer (flashcards, QCM, fiches…) · corrigé séparé pour les supports évaluatifs |
| **Difficulté** | Public cible (requis) · objectif Bloom (`Auto` / `Restituer` / `Comprendre & Appliquer` / `Analyser & au-delà`) · directives pédagogiques libres · densité (`léger` / `standard` / `dense`) |
| **Langues** | Langues des supports (par défaut : celles effectivement produites par la Génération) |
| **Modèle & coût** | Modèle LLM · mode raisonnement · plafond de coût · *Tâches en parallèle* |

### Estimer et générer

1. (Recommandé) **💵 Estimer le coût** : affiche le budget prévu (par support ×
   langue × chapitre, selon la densité et le mode raisonnement).
2. **▶ Lancer** : la table de progression se remplit (une ligne par support ×
   langue). Une **pastille d'état** colorée en haut indique la fraîcheur d'un
   coup d'œil : *⚙ À configurer* → *⚠ Génération requise* → *● Prêt à générer*
   → *✓ Supports à jour* (vert) → *⟳ Supports à régénérer* (ambre).

Si vous relancez la Génération plus tard, les supports existants sont marqués
**périmés** : régénérez-les pour les réaligner sur le nouveau contenu. Les
supports déjà à jour sont **sautés** (pas de re-génération inutile).

### Récupérer et exporter

Les supports sont écrits sous `<emplacement>/pedagogy/{support}/{langue}/`
(`.json` structuré + `.md` lisible, plus `.corrige.md` pour les sujets évaluatifs
avec corrigé séparé). Vous pouvez les éditer directement.

Le bouton **📦 Exporter** propose les formats que vous avez cochés dans les
réglages (« ⚙ Réglages → Export → Formats d'export proposés ») :

- **Anki (`.apkg`)** : paquet importable dans Anki — sous-decks par support,
  cartes Basic / Cloze / QCM, étiquettes (support / langue / niveau / chapitre).
  Les ré-imports ne créent pas de doublons (identifiants stables). La mise en
  forme Markdown des cartes (listes, gras) est rendue en HTML dans Anki.
- **Markdown** : un fichier par support et par corrigé, par langue.
- **PDF** : mêmes documents, prêts à imprimer (chinois et arabe gérés).
- **HTML** : document autonome (ouvrable dans un navigateur, mise en forme incluse).
- **Word (`.docx`)** : mêmes documents, éditables dans Word/LibreOffice.

## 9. Dialoguer avec votre cours

Une fois la Génération terminée, l'onglet **Dialogue** vous permet de **poser des
questions** sur votre cours et d'obtenir des réponses **citées**, en langage
naturel.

> **Prérequis** : avoir lancé au moins une fois la **Génération** (un document
> consolidé doit exister). Sinon, l'onglet vous invite à le faire.

1. Sélectionnez le projet, ouvrez l'onglet **Dialogue**.
2. Tapez votre question en bas, cliquez **Envoyer** (ou Entrée).
3. La réponse s'écrit progressivement, **mise en forme** (gras, listes, tableaux).
   Par défaut, l'assistant répond **uniquement d'après votre cours** et indique ses
   **sources** ; cliquez une source pour lire l'extrait. S'il ne trouve pas
   l'information, il répond « Ce point n'est pas couvert par le cours. »
4. Le **coût** de l'échange s'affiche sous la réponse (et le **cumul** de la
   conversation). Il est complet : il comprend la réponse **et** les embeddings du
   retrieval sémantique (le mode **lexical**, lui, est gratuit).

Vous pouvez ouvrir plusieurs **conversations** (bouton **＋ Nouvelle
conversation**) ; elles sont conservées même après fermeture de l'application.
Pour en **supprimer** une, faites un **clic droit** dessus dans la liste →
*« Supprimer la conversation »* (confirmation demandée).

Le bouton **⚙ Réglages** permet de choisir le mode de réponse (strict, ou
« augmenté » qui complète avec des connaissances générales), la méthode de
recherche dans le cours, le modèle LLM **et** le modèle d'embedding (recherche
sémantique) — voir [04-parametrage.md](04-parametrage.md) §3ter.

## 10. Dépannage

### *« Windows a protégé votre PC »*

Normal au 1er lancement. Cliquer *« Plus d'infos »* → *« Exécuter quand
même »*. Cela ne reviendra pas.

### *« GPU NVIDIA introuvable »*

Vous avez sélectionné le mode local sans avoir de GPU NVIDIA. Ouvrez l'onglet
**Génération → ⚙ Réglages → Transcription** et basculez sur `openai_cloud`.

### *« Clé DeepSeek invalide »*

Vérifiez la clé dans **Édition → Paramètres globaux** (copier-coller
recommandé pour éviter les espaces parasites).

### *« Limite de débit DeepSeek atteinte »*

L'application réessaie automatiquement. Aucune action requise.

### *« Plafond de budget atteint »*

Vous avez fixé un plafond et il est atteint. Pour continuer :

1. Menu **Édition → Paramètres globaux** (ou reéditer le projet).
2. Augmentez ou supprimez le plafond.
3. Revenez sur le projet, cliquez sur **▶ Reprendre**.

### Une vidéo a échoué (case `✗`)

Double-cliquez sur la case rouge pour voir le détail de l'erreur. Pour
relancer juste cette phase : cliquer *« Rejouer cette phase »* dans la
fenêtre de détail.

### L'application a planté

Relancez `Fahmi2.exe`. L'état est sauvegardé : votre projet est intact,
cliquez **▶ Reprendre** pour continuer.

## 11. Mise à jour de l'application

Quand une nouvelle version est disponible :

1. Téléchargez le nouveau `.zip`.
2. Fermez Fahmi2 si ouvert.
3. Décompressez le nouveau `.zip` (vous pouvez écraser l'ancien dossier).
4. Relancez `Fahmi2.exe`.

Vos projets et vos clés sont **automatiquement conservés**. Si une
adaptation interne est nécessaire (mise à jour de la base), elle est
appliquée automatiquement avec une sauvegarde préalable de sécurité.

## 12. Désinstaller

1. Supprimez le dossier où vous aviez décompressé Fahmi2.
2. Si vous voulez aussi effacer **tous vos projets et clés** :
   - Dans l'explorateur Windows, tapez `%APPDATA%\Fahmi2` dans la barre
     d'adresse et appuyez sur Entrée → supprimer ce dossier.
   - Idem avec `%LOCALAPPDATA%\Fahmi2`.

Rien d'autre ne reste sur votre système.

## 13. Astuces

### Tester avant un gros traitement

Avant de lancer un projet sur 50 vidéos, créez un projet « test » avec 2-3
vidéos seulement, en `deepseek-v4-flash` sans thinking. Vérifiez la
qualité du rendu avant de lancer le projet définitif (peut-être en
`deepseek-v4-pro` avec thinking pour la qualité maximale).

### Estimer le coût avant chaque lancement

Le bouton **💵 Estimer le coût** affiche le budget prévu en quelques
secondes. **Important** : si vous activez le mode raisonnement
(*thinking*) sur les phases, le coût peut être 2 à 6× supérieur. Le
calcul d'estimation en tient compte.

### Plafond budget par sécurité

Mettez toujours un plafond de coût, même large. Si quelque chose ne va pas
(par exemple un appel LLM qui boucle), le plafond limite les dégâts.

### Personnaliser les prompts

Si vous voulez ajuster finement le ton ou le format au-delà des
*Directives stylistiques*, ouvrez **Édition → Modifier les prompts…**
Sélectionnez un prompt à gauche, éditez le texte à droite,
cliquez **💾 Enregistrer**. Pour revenir à la version d'origine
livrée avec l'application, cliquez sur **↩ Réinitialiser au défaut**.
Pas besoin de redémarrer : le nouveau prompt est utilisé au prochain
lancement. Le catalogue couvre les **phases de génération** **et** les
prompts des **supports pédagogiques** (`pedagogy_*`) : vous personnalisez
de la même façon la consigne de génération des flashcards, QCM, fiches, etc.

### Conserver les artefacts intermédiaires

Le dossier `<emplacement>/generation/` contient les fichiers de travail. Si vous
voulez juste les livrables finaux, vous pouvez supprimer ce dossier après
récupération. Mais conservez-le si vous pensez ré-éditer ou rejouer
certaines phases.

### Style du rendu

Si le rendu ne vous plaît pas (trop sec, trop verbeux, etc.), modifiez le
champ **Directives stylistiques** dans l'onglet **Génération → ⚙ Réglages → Style**
et relancez.
Pas besoin de tout refaire — la reprise saute les phases déjà bien faites.

### Glossaire homogène

Le glossaire est construit en deux passes (extraction puis réconciliation
cross-vidéos). Plus votre dossier contient de vidéos sur le même domaine,
plus le glossaire sera riche et cohérent. Les acronymes (ROI, PIB,
IFRS…) sont accompagnés de leur **signification d'origine** en plus de
la définition — celle-ci reste dans la langue où l'acronyme a été forgé
(*Return On Investment* pour ROI, même dans un glossaire FR).

## 14. Confidentialité

- **Aucune télémétrie** n'est envoyée par l'application.
- **Vos contenus ne sortent jamais de votre poste** sauf vers les APIs que
  vous avez explicitement configurées (DeepSeek + éventuellement OpenAI
  pour Whisper cloud).
- **Vos clés API sont chiffrées** sur disque par Windows DPAPI : seul
  votre compte Windows peut les lire.

## 15. Besoin d'aide ?

- Pour les questions fonctionnelles : voir
  [01-presentation-fonctionnelle.md](01-presentation-fonctionnelle.md).
- Pour le détail des paramètres : voir
  [04-parametrage.md](04-parametrage.md).
- Pour le pilotage avancé (logs, sauvegardes…) : voir
  [05-exploitation.md](05-exploitation.md).
