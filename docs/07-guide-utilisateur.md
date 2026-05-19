# Fahmi2 — Guide utilisateur

Document destiné à l'utilisateur final non-technicien. Démarrage en moins
de 10 minutes.

## 1. Qu'est-ce que Fahmi2 ?

Fahmi2 transforme automatiquement vos vidéos de cours (MP4) en documents
écrits structurés en Markdown, avec un glossaire et un document consolidé,
dans la langue de votre choix (FR ou EN).

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

Menu **Fichier → Nouveau projet**. Remplissez :

| Champ | Conseil |
|-------|---------|
| **Nom** | Libre. Ex: « Cours d'économie L3 ». |
| **Dossier d'entrée** | Cliquez sur *« Parcourir… »* et sélectionnez le dossier qui contient vos vidéos. |
| **Langue source** | La langue parlée dans vos vidéos (FR ou EN). |
| **Langues de sortie** | Cochez les langues désirées pour le document final. La langue source est automatiquement incluse. |
| **Style** | `décontracté`, `standard`, `professionnel`, ou `académique`. Pour un cours universitaire, choisissez `académique`. |
| **Directives stylistiques** | Optionnel. Ex: *« ton chaleureux, exemples concrets quand possible »*. |
| **Provider STT** | `openai_cloud` si vous n'avez pas de GPU NVIDIA. Sinon, `faster_whisper_local` (gratuit). |
| **Modèle LLM** | `deepseek-v4-flash` pour démarrer (rapide et économique). |
| **Plafond budget** | Optionnel. Mettez par ex. 5 $ pour un premier essai. |

Cliquez sur **OK**. Le projet apparaît dans la liste à gauche.

## 5. Lancer le traitement

1. Sélectionnez votre projet dans la liste à gauche.
2. Cliquez sur **▶ Lancer** en haut.

La grille au centre commence à se remplir :

- Une **ligne par vidéo**.
- Une **colonne par phase** (8 colonnes).
- Chaque case montre l'avancement :
  - `·` en attente
  - `▶` en cours
  - `✓` terminé
  - `✗` échec (rare, voir [Dépannage](#7-dépannage))

En haut, une bande affiche :

- Le statut du projet
- Le compteur de vidéos terminées (ex: *« 3 / 12 vidéos »*)
- Le compteur de phases (ex: *« 15 / 96 phases »*)
- Le coût cumulé en USD

En bas, une liste des dernières actions et messages (Logs).

## 6. Mettre en pause ou annuler

- **⏸ Pause** : interrompt le traitement à la prochaine étape sûre. Vous
  pouvez fermer l'application — le travail est sauvegardé.
- **▶ Reprendre** : reprend exactement là où vous vous étiez arrêté. Aucun
  travail n'est refait.
- **✕ Annuler** : marque le run comme annulé. Vous pourrez relancer plus
  tard si vous le souhaitez.

## 7. Récupérer les fichiers produits

Quand le projet est terminé (statut **COMPLETED**), ouvrez le dossier
d'entrée que vous aviez choisi. Vous y trouverez un sous-dossier
`.fahmi2/output/` :

```
.fahmi2/
└── output/
    ├── consolidated.fr.md     ← Le document consolidé en français
    ├── consolidated.en.md     ← Le document consolidé en anglais
    ├── glossary.fr.md         ← Le glossaire en français
    ├── glossary.en.md         ← Le glossaire en anglais
    └── per-video/
        ├── fr/
        │   ├── XXX.md         ← Un fichier par vidéo (FR)
        │   └── …
        └── en/
            └── …
```

Tous les fichiers sont en **Markdown**, lisibles dans n'importe quel
éditeur (Bloc-notes, VS Code, Typora, Obsidian…).

Pour les convertir en **DOCX, PDF ou HTML**, l'outil libre
[Pandoc](https://pandoc.org) fait ça très bien.

## 7. Dépannage

### *« Windows a protégé votre PC »*

Normal au 1er lancement. Cliquer *« Plus d'infos »* → *« Exécuter quand
même »*. Cela ne reviendra pas.

### *« GPU NVIDIA introuvable »*

Vous avez sélectionné le mode local sans avoir de GPU NVIDIA. Allez dans
les paramètres du projet et basculez sur `openai_cloud`.

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

## 8. Mise à jour de l'application

Quand une nouvelle version est disponible :

1. Téléchargez le nouveau `.zip`.
2. Fermez Fahmi2 si ouvert.
3. Décompressez le nouveau `.zip` (vous pouvez écraser l'ancien dossier).
4. Relancez `Fahmi2.exe`.

Vos projets et vos clés sont **automatiquement conservés**. Si une
adaptation interne est nécessaire (mise à jour de la base), elle est
appliquée automatiquement avec une sauvegarde préalable de sécurité.

## 9. Désinstaller

1. Supprimez le dossier où vous aviez décompressé Fahmi2.
2. Si vous voulez aussi effacer **tous vos projets et clés** :
   - Dans l'explorateur Windows, tapez `%APPDATA%\Fahmi2` dans la barre
     d'adresse et appuyez sur Entrée → supprimer ce dossier.
   - Idem avec `%LOCALAPPDATA%\Fahmi2`.

Rien d'autre ne reste sur votre système.

## 10. Astuces

### Tester avant un gros traitement

Avant de lancer un projet sur 50 vidéos, créez un projet « test » avec 2-3
vidéos seulement, en `deepseek-v4-flash`. Vérifiez la qualité du rendu
avant de lancer le projet définitif (peut-être en `deepseek-v4-pro` pour
la qualité maximale).

### Plafond budget par sécurité

Mettez toujours un plafond de coût, même large. Si quelque chose ne va pas
(par exemple un appel LLM qui boucle), le plafond limite les dégâts.

### Conserver les artefacts intermédiaires

Le dossier `.fahmi2/workspace/` contient les fichiers de travail. Si vous
voulez juste les livrables finaux, vous pouvez supprimer ce dossier après
récupération. Mais conservez-le si vous pensez ré-éditer ou rejouer
certaines phases.

### Style du rendu

Si le rendu ne vous plaît pas (trop sec, trop verbeux, etc.), modifiez le
champ **Directives stylistiques** dans les paramètres du projet et relancez.
Pas besoin de tout refaire — la reprise saute les phases déjà bien faites.

### Glossaire homogène

Le glossaire est construit en deux passes (extraction puis réconciliation
cross-vidéos). Plus votre dossier contient de vidéos sur le même domaine,
plus le glossaire sera riche et cohérent.

## 11. Confidentialité

- **Aucune télémétrie** n'est envoyée par l'application.
- **Vos contenus ne sortent jamais de votre poste** sauf vers les APIs que
  vous avez explicitement configurées (DeepSeek + éventuellement OpenAI
  pour Whisper cloud).
- **Vos clés API sont chiffrées** sur disque par Windows DPAPI : seul
  votre compte Windows peut les lire.

## 12. Besoin d'aide ?

- Pour les questions fonctionnelles : voir
  [01-presentation-fonctionnelle.md](01-presentation-fonctionnelle.md).
- Pour le détail des paramètres : voir
  [04-parametrage.md](04-parametrage.md).
- Pour le pilotage avancé (logs, sauvegardes…) : voir
  [05-exploitation.md](05-exploitation.md).
