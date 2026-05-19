# Guide utilisateur Fahmi2

> Guide rapide pour démarrer avec Fahmi2 en moins de 10 minutes.

## 1. Première ouverture

Au premier lancement, l'application :

1. Crée automatiquement les dossiers `%APPDATA%/Fahmi2/` et
   `%LOCALAPPDATA%/Fahmi2/` pour ses données.
2. Affiche la fenêtre principale (cockpit). La sidebar gauche est vide tant
   qu'aucun projet n'a été créé.

**SmartScreen Windows** affichera un avertissement « Éditeur inconnu » au
premier lancement. Cliquez sur *« Plus d'infos »* puis *« Exécuter quand
même »*. Cela ne se reproduira plus.

## 2. Configurer les clés API

Menu **Édition → Paramètres globaux**.

Renseigner :

- **Clé OpenAI** : nécessaire si vous utilisez le STT cloud (recommandé sans
  GPU NVIDIA). Cf. https://platform.openai.com/api-keys
- **Clé DeepSeek** : nécessaire pour toutes les phases LLM. Cf.
  https://platform.deepseek.com/api-keys
- **Thème** : `system` (recommandé), `light` ou `dark`

Les clés sont chiffrées via Windows DPAPI et stockées dans
`%APPDATA%/Fahmi2/secrets.dat`. Elles ne sont **jamais** visibles en clair
dans les logs.

## 3. Créer un projet

Menu **Fichier → Nouveau projet**. Renseigner :

### Identification

- **Nom** : libre, ex. *« Cours d'économie L3 »*.
- **Dossier d'entrée** : dossier contenant vos vidéos MP4 (`.mp4`, `.m4v`,
  `.mkv`, `.mov`, `.webm` supportés).

### Langues

- **Langue source** : langue parlée dans les vidéos.
- **Langues de sortie** : cochez les langues désirées pour le document final.
  La langue source est toujours incluse.

### Style

- **Style** : `décontracté`, `standard`, `professionnel`, ou `académique`.
- **Directives stylistiques** : champ libre pour préciser (ex. *« voix
  professorale, ton chaleureux mais rigoureux »*).

### Providers

- **Provider STT** :
  - `openai_cloud` (recommandé sans GPU) — ~0.006 $/min audio.
  - `faster_whisper_local` (GPU NVIDIA requis) — gratuit mais nécessite CUDA.
- **Modèle LLM** :
  - `deepseek-v4-flash` — rapide et économique (recommandé pour démarrer).
  - `deepseek-v4-pro` — capacité supérieure, ~3× plus cher.

### Budget

- **Plafond budget** : optionnel. À 0, pas de plafond. Sinon, le run se met
  en pause propre dès que le coût cumulé approche du plafond.

Valider avec **OK**. Le projet apparaît dans la sidebar.

## 4. Lancer un run

1. Sélectionner le projet dans la sidebar.
2. Cliquer sur **▶ Lancer** dans la barre d'en-tête.

### Suivre le run

- **StatsStrip** (en haut) : statut, vidéos traitées, phases complétées,
  coût cumulé / plafond.
- **Matrice** : une ligne par vidéo, une colonne par phase. Les cellules
  affichent :
  - `·` : en attente
  - `▶` : en cours
  - `✓` : terminé avec succès
  - `✗` : échec
  - `↷` : sauté (déjà fait au précédent run)
- **Panneau Logs** (en bas) : événements en direct, filtrables par niveau.

### Mettre en pause / annuler

- **⏸ Pause** : arrêt à la prochaine frontière sûre (entre 2 phases ou
  entre 2 retries). État préservé, **reprise possible** à tout moment.
- **✕ Annuler** : pause + marquage du run en annulé. Les artefacts
  intermédiaires sont conservés.

### Reprise après crash

Si l'application est fermée brutalement (crash, coupure d'alimentation,
etc.), le run est conservé dans la base SQLite. Au prochain lancement,
rouvrez le projet : la matrice indique l'état atteint. Cliquez sur
*« ▶ Lancer »* — le pipeline reprend exactement où il s'était arrêté.

## 5. Récupérer les livrables

Une fois le run en *« COMPLETED »*, ouvrir le dossier de sortie :

```
<dossier_entrée>/.fahmi2/output/
├── consolidated.fr.md            ← document consolidé en FR
├── consolidated.en.md            ← document consolidé en EN (si demandé)
├── glossary.fr.md                ← glossaire FR
├── glossary.en.md                ← glossaire EN
└── per-video/
    ├── fr/
    │   ├── <video_id_1>.md       ← document par vidéo en FR
    │   └── <video_id_2>.md
    └── en/
        ├── <video_id_1>.md       ← idem en EN
        └── ...
```

Tous les fichiers sont en **Markdown UTF-8**, prêts à être ouverts dans :

- VS Code, Obsidian (rendu admonitions GFM natif)
- Pandoc pour conversion vers DOCX/PDF/HTML
- N'importe quel éditeur texte standard

## 6. Dépannage

### *« GPU NVIDIA introuvable »*

Vous avez sélectionné `faster_whisper_local` sans GPU compatible. Passez sur
`openai_cloud` dans les paramètres du projet.

### *« Clé DeepSeek invalide »*

Allez dans **Édition → Paramètres globaux** et corrigez la clé.

### *« Limite de débit DeepSeek atteinte »*

L'application réessaie automatiquement avec un délai croissant. Aucune
action requise.

### *« Plafond de budget atteint »*

Le run a été mis en pause propre. Relevez le plafond dans les paramètres
du projet et relancez le run pour reprendre.

### Le run a échoué sur une phase

Cliquez sur la cellule rouge dans la matrice pour voir le détail de
l'erreur. Le bouton *« Rejouer cette phase »* relance uniquement la phase
échouée (les phases précédentes restent SUCCEEDED).

## 7. Mise à jour de l'application

1. Télécharger la nouvelle version `.zip`
2. Fermer Fahmi2 si ouvert
3. Décompresser le nouveau `.zip` (peut écraser l'ancien dossier)
4. Relancer `Fahmi2.exe`

Vos projets et paramètres sont **automatiquement préservés** dans
`%APPDATA%/Fahmi2/`. Aucune migration manuelle n'est nécessaire — le
``MigrationRunner`` interne s'occupe des éventuels changements de schéma.

## 8. Désinstaller

1. Supprimer le dossier où vous avez décompressé Fahmi2.
2. Si vous souhaitez également effacer vos projets et clés API :
   - Supprimer le dossier `%APPDATA%/Fahmi2/`.
   - Supprimer le dossier `%LOCALAPPDATA%/Fahmi2/` (cache des modèles).
   - Supprimer la clé de registre `HKCU\Software\Fahmi2` via `regedit`.

Aucune trace n'est laissée ailleurs sur le système.
