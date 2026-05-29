<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en" sourcelanguage="fr">
<context>
    <name>AppMain</name>
    <message>
        <location filename="../../ui/app_main.py" line="225"/>
        <source>Supprimer le projet ?</source>
        <translation>Delete the project?</translation>
    </message>
    <message>
        <location filename="../../ui/app_main.py" line="226"/>
        <source>Supprimer le projet « {name} » ?

Cette action supprime ses runs et métadonnées en base, AINSI QUE le dossier du projet et tout son contenu sur disque :
{path}

Le dossier d&apos;entrée (vos fichiers sources) n&apos;est PAS supprimé.

Cette action est irréversible.</source>
        <translation>Delete the project “{name}”?

This deletes its runs and metadata in the database, AS WELL AS the project folder and all its contents on disk:
{path}

The input folder (your source files) is NOT deleted.

This action is irreversible.</translation>
    </message>
</context>
<context>
    <name>ChatBubble</name>
    <message>
        <location filename="../../ui/widgets/_chat_bubble.py" line="94"/>
        <source>Vous</source>
        <extracomment>Rayon des coins arrondis de la bulle (px). Largeur maximale d&apos;une bulle en pourcentage de la largeur disponible. Marges internes de la bulle (px). Espacement vertical entre les enfants de la bulle. Marges autour de chaque bulle (dans le fil scrollable). Style commun (compact) du texte des liens dans une bulle. Style des chips de citation (pastilles cliquables sous une bulle assistant). ``objectName`` réservé aux bulles (utilisé pour cibler le QSS interne qui rend les ``QLabel`` enfants transparents).</extracomment>
        <translation>You</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/_chat_bubble.py" line="96"/>
        <source>Assistant</source>
        <translation>Assistant</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/_chat_bubble.py" line="102"/>
        <source>Sources</source>
        <translation>Sources</translation>
    </message>
</context>
<context>
    <name>ChatController</name>
    <message>
        <location filename="../../ui/chat_controller.py" line="413"/>
        <source>Clé DeepSeek manquante</source>
        <extracomment>Séparateur du préfixe de langue dans la liste des conversations (ex. « EN · Titre »). Une conversation a une langue **fixe** (choisie à sa création) → on l&apos;affiche pour lever toute ambiguïté entre conversations de langues différentes. Empreinte de fraîcheur du corpus : (langue de contenu, mtime consolidé, mtime glossaire). Émis quand une réponse est finalisée (utile aux tests et à l&apos;UI).</extracomment>
        <translation>DeepSeek key missing</translation>
    </message>
    <message>
        <location filename="../../ui/chat_controller.py" line="414"/>
        <source>Renseigne la clé DeepSeek dans « Édition → Paramètres globaux » pour dialoguer.</source>
        <translation>Enter the DeepSeek key under “Edit → Global settings” to dialogue.</translation>
    </message>
    <message>
        <location filename="../../ui/chat_controller.py" line="522"/>
        <source>Supprimer la conversation</source>
        <translation>Delete conversation</translation>
    </message>
    <message>
        <location filename="../../ui/chat_controller.py" line="523"/>
        <source>Supprimer définitivement cette conversation ? Cette action est irréversible.</source>
        <translation>Permanently delete this conversation? This action is irreversible.</translation>
    </message>
    <message>
        <location filename="../../ui/chat_controller.py" line="545"/>
        <source>Aucun projet sélectionné</source>
        <translation>No project selected</translation>
    </message>
    <message>
        <location filename="../../ui/chat_controller.py" line="546"/>
        <source>Sélectionne un projet dans la sidebar avant de configurer.</source>
        <translation>Select a project in the sidebar before configuring.</translation>
    </message>
    <message>
        <location filename="../../ui/chat_controller.py" line="587"/>
        <source>Le dialogue s&apos;est terminé sur une erreur</source>
        <translation>The dialogue ended with an error</translation>
    </message>
</context>
<context>
    <name>ChatSettingsView</name>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="79"/>
        <source>Réglages — Dialogue</source>
        <translation>Settings — Dialogue</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="90"/>
        <source>Reformulation automatique des questions</source>
        <translation>Automatic question rephrasing</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="97"/>
        <source>Activer la réflexion approfondie</source>
        <translation>Enable deep reasoning</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="110"/>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="173"/>
        <source>Mode de réponse</source>
        <translation>Response mode</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="111"/>
        <source>Recherche de passages</source>
        <translation>Passage search</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="112"/>
        <source>Génération IA</source>
        <translation>AI generation</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="144"/>
        <source>Strict — réponses tirées du cours uniquement</source>
        <translation>Strict — answers from the course only</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="147"/>
        <source>Étendu — complète au-delà du cours</source>
        <translation>Extended — supplements beyond the course</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="155"/>
        <source>Automatique (sens si clé OpenAI, mots-clés sinon)</source>
        <translation>Automatic (semantic if OpenAI key, keywords otherwise)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="157"/>
        <source>Mots-clés (hors ligne, TF-IDF)</source>
        <translation>Keywords (offline, TF-IDF)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="158"/>
        <source>Sens (en ligne, OpenAI)</source>
        <translation>Semantic (online, OpenAI)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="167"/>
        <source>Comportement des réponses</source>
        <translation>Response behaviour</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="169"/>
        <source>Définit jusqu&apos;où l&apos;assistant peut s&apos;éloigner du cours dans ses réponses.</source>
        <translation>Defines how far the assistant may stray from the course in its answers.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="179"/>
        <source>Passages cités</source>
        <translation>Cited passages</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="181"/>
        <source>Nombre de passages du cours utilisés pour étayer chaque réponse.</source>
        <translation>Number of course passages used to back each answer.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="185"/>
        <source>Nombre de passages cités</source>
        <translation>Number of cited passages</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="198"/>
        <source>Méthode de recherche</source>
        <translation>Search method</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="200"/>
        <source>Comment l&apos;assistant retrouve les passages pertinents dans le cours.</source>
        <translation>How the assistant finds relevant passages in the course.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="204"/>
        <source>Méthode</source>
        <translation>Method</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="211"/>
        <source>L&apos;assistant reformule la question pour améliorer la recherche. Recommandé.</source>
        <translation>The assistant rephrases the question to improve search. Recommended.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="219"/>
        <source>Modèle de vectorisation</source>
        <translation>Embedding model</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="221"/>
        <source>Modèle OpenAI utilisé pour la recherche par sens. Sans effet en mode « mots-clés » (entièrement hors ligne).</source>
        <translation>OpenAI model used for semantic search. No effect in “keywords” mode (fully offline).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="226"/>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="245"/>
        <source>Modèle</source>
        <translation>Model</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="239"/>
        <source>Modèle de génération</source>
        <translation>Generation model</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="241"/>
        <source>Modèle DeepSeek qui rédige les réponses à partir des passages cités.</source>
        <translation>DeepSeek model that drafts the answers from the cited passages.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="246"/>
        <source>Température</source>
        <translation>Temperature</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="252"/>
        <source>Réflexion approfondie</source>
        <translation>Deep reasoning</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="254"/>
        <source>Active un raisonnement étendu avant la réponse — meilleure qualité, coût plus élevé.</source>
        <translation>Triggers extended reasoning before answering — better quality, higher cost.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/chat_settings_view.py" line="260"/>
        <source>Intensité de réflexion</source>
        <translation>Reasoning intensity</translation>
    </message>
</context>
<context>
    <name>ChatTab</name>
    <message>
        <location filename="../../ui/features/chat_tab.py" line="27"/>
        <source>Dialogue</source>
        <extracomment>Libellé source de l&apos;onglet — résolu à la lecture de :py:attr:`ChatTab.title` (le traducteur n&apos;est pas installé à l&apos;import). Les stubs PySide6 typent ``QT_TRANSLATE_NOOP`` en ``object`` ; on caste car la fonction renvoie son argument textuel tel quel (cf. ``QtCore.QT_TRANSLATE_NOOP`` upstream).</extracomment>
        <translation>Dialogue</translation>
    </message>
    <message>
        <location filename="../../ui/features/chat_tab.py" line="28"/>
        <source>⚙️  Réglages</source>
        <translation>⚙️  Settings</translation>
    </message>
    <message>
        <location filename="../../ui/features/chat_tab.py" line="31"/>
        <source>Configurer le dialogue (fidélité, retrieval, modèle, coût).</source>
        <translation>Configure the dialogue (fidelity, retrieval, model, cost).</translation>
    </message>
</context>
<context>
    <name>ChatView</name>
    <message>
        <location filename="../../ui/widgets/chat_view.py" line="52"/>
        <source>Vous</source>
        <extracomment>Le sélecteur de langue n&apos;a de sens qu&apos;à partir de 2 langues produites (un choix).</extracomment>
        <translation>You</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/chat_view.py" line="54"/>
        <source>Assistant</source>
        <translation>Assistant</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/chat_view.py" line="121"/>
        <source>Langue du corpus pour une nouvelle conversation : lecture, citations et réponse.</source>
        <extracomment>Largeur (%) des bulles utilisateur (alignées à droite). Largeur (%) des bulles assistant (alignées à gauche). Fond et bordure des bulles (HTML inline ; QTextBrowser ne supporte pas ``border-radius`` — on se contente d&apos;un encadré coloré, plus un alignement gauche/droite par ``&lt;table align&gt;``). Couleurs alignées sur les tokens clairs (le thème sombre garde les mêmes contrastes : fond accent doux pour utilisateur, surface bordée pour assistant). Chips de source (pastilles inline cliquables sous une bulle assistant). Couleur de la ligne « Sources » (libellé discret au-dessus des chips). Style du fil : liens lisibles, code et tableaux discrets.</extracomment>
        <translation>Corpus language for a new conversation: reading, citations, and answers.</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/chat_view.py" line="126"/>
        <source>＋ Nouvelle conversation</source>
        <translation>＋ New conversation</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/chat_view.py" line="136"/>
        <source>Lance d&apos;abord une génération pour dialoguer avec ce cours.</source>
        <translation>Run a generation first to dialogue with this course.</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/chat_view.py" line="147"/>
        <location filename="../../ui/widgets/chat_view.py" line="270"/>
        <source>Coût cumulé · ${cost}</source>
        <translation>Cumulative cost · ${cost}</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/chat_view.py" line="150"/>
        <source>Pose une question sur le cours…</source>
        <translation>Ask a question about the course…</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/chat_view.py" line="153"/>
        <source>Envoyer</source>
        <translation>Send</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/chat_view.py" line="295"/>
        <source>Supprimer la conversation</source>
        <translation>Delete conversation</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/chat_view.py" line="423"/>
        <source>Sources</source>
        <translation>Sources</translation>
    </message>
</context>
<context>
    <name>CostEstimateDialog</name>
    <message>
        <location filename="../../ui/cost_estimate_dialog.py" line="77"/>
        <source>Total estimé</source>
        <translation>Estimated total</translation>
    </message>
    <message>
        <location filename="../../ui/cost_estimate_dialog.py" line="79"/>
        <source>fourchette {low} – {high} (±{pct} %)</source>
        <translation>range {low} – {high} (±{pct} %)</translation>
    </message>
    <message>
        <location filename="../../ui/cost_estimate_dialog.py" line="89"/>
        <source>&lt;i&gt;Estimation indicative basée sur des heuristiques DeepSeek (durées, tokens, multiplicateurs par phase et mode thinking). Fourchette ±33 %.&lt;/i&gt;</source>
        <translation>&lt;i&gt;Indicative estimate based on DeepSeek heuristics (durations, tokens, per-phase multipliers, and thinking mode). Range ±33 %.&lt;/i&gt;</translation>
    </message>
    <message>
        <location filename="../../ui/cost_estimate_dialog.py" line="110"/>
        <source>Plafond</source>
        <translation>Cap</translation>
    </message>
    <message>
        <location filename="../../ui/cost_estimate_dialog.py" line="112"/>
        <source>(marge ${margin:.2f})</source>
        <translation>(margin ${margin:.2f})</translation>
    </message>
    <message>
        <location filename="../../ui/cost_estimate_dialog.py" line="120"/>
        <source>(dépassement ${excess:.2f})</source>
        <translation>(overrun ${excess:.2f})</translation>
    </message>
    <message>
        <location filename="../../ui/cost_estimate_dialog.py" line="128"/>
        <source>⚠ le haut de fourchette (${high:.2f}) peut dépasser le plafond.</source>
        <translation>⚠ the top of the range (${high:.2f}) may exceed the cap.</translation>
    </message>
    <message>
        <location filename="../../ui/cost_estimate_dialog.py" line="170"/>
        <source>Estimation du coût</source>
        <translation>Cost estimate</translation>
    </message>
    <message>
        <location filename="../../ui/cost_estimate_dialog.py" line="171"/>
        <source>Décomposition par étape et total estimé. La fourchette ±33 % reflète l&apos;incertitude sur la longueur réelle des sorties IA.</source>
        <translation>Per-step breakdown and estimated total. The ±33 % range reflects uncertainty over the actual length of AI outputs.</translation>
    </message>
    <message>
        <location filename="../../ui/cost_estimate_dialog.py" line="190"/>
        <source>Compris</source>
        <translation>Got it</translation>
    </message>
</context>
<context>
    <name>CostMatrix</name>
    <message>
        <location filename="../../ui/widgets/cost_matrix_view.py" line="39"/>
        <source>Total</source>
        <translation>Total</translation>
    </message>
</context>
<context>
    <name>ExportUI</name>
    <message>
        <location filename="../../ui/_export_ui.py" line="46"/>
        <source>Aucun format d&apos;export</source>
        <translation>No export format</translation>
    </message>
    <message>
        <location filename="../../ui/_export_ui.py" line="47"/>
        <source>Aucun format d&apos;export n&apos;est sélectionné dans les réglages (⚙ Réglages → Export).</source>
        <translation>No export format is selected in the settings (⚙ Settings → Export).</translation>
    </message>
    <message>
        <location filename="../../ui/_export_ui.py" line="57"/>
        <source>Exporter</source>
        <translation>Export</translation>
    </message>
    <message>
        <location filename="../../ui/_export_ui.py" line="58"/>
        <source>Format :</source>
        <translation>Format:</translation>
    </message>
    <message>
        <location filename="../../ui/_export_ui.py" line="78"/>
        <source>Dossier d&apos;export {label}</source>
        <translation>Export folder for {label}</translation>
    </message>
    <message>
        <location filename="../../ui/_export_ui.py" line="89"/>
        <source>Export impossible</source>
        <translation>Export failed</translation>
    </message>
    <message>
        <location filename="../../ui/_export_ui.py" line="96"/>
        <source>Erreur inattendue</source>
        <translation>Unexpected error</translation>
    </message>
    <message>
        <location filename="../../ui/_export_ui.py" line="103"/>
        <source>Rien à exporter</source>
        <translation>Nothing to export</translation>
    </message>
    <message>
        <location filename="../../ui/_export_ui.py" line="104"/>
        <source>Aucun document à exporter. Lancez d&apos;abord la génération pour ce projet.</source>
        <translation>No document to export. Run a generation first for this project.</translation>
    </message>
    <message>
        <location filename="../../ui/_export_ui.py" line="124"/>
        <source>Export terminé</source>
        <translation>Export finished</translation>
    </message>
    <message>
        <location filename="../../ui/_export_ui.py" line="125"/>
        <source>{count} document(s) {label} exporté(s) dans :
{directory}</source>
        <translation>{count} {label} document(s) exported to:
{directory}</translation>
    </message>
</context>
<context>
    <name>FsHelpers</name>
    <message>
        <location filename="../../ui/_fs.py" line="44"/>
        <source>Échec de la suppression du dossier {label} : {path} ({exc})</source>
        <translation>Failed to delete the {label} folder: {path} ({exc})</translation>
    </message>
</context>
<context>
    <name>GenerationController</name>
    <message>
        <location filename="../../ui/generation_controller.py" line="501"/>
        <location filename="../../ui/generation_controller.py" line="680"/>
        <location filename="../../ui/generation_controller.py" line="752"/>
        <location filename="../../ui/generation_controller.py" line="830"/>
        <location filename="../../ui/generation_controller.py" line="969"/>
        <source>Aucun projet sélectionné</source>
        <extracomment>Émis quand le statut du run change (démarrage / fin / échec / réinit.), pour rafraîchir les icônes de la sidebar.</extracomment>
        <translation>No project selected</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="504"/>
        <source>Sélectionne un projet dans la sidebar avant de lancer.</source>
        <translation>Select a project in the sidebar before launching.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="513"/>
        <source>Run déjà en cours</source>
        <translation>Run already in progress</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="516"/>
        <source>Un run est déjà en cours pour ce projet.</source>
        <translation>A run is already in progress for this project.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="533"/>
        <source>Création du run impossible</source>
        <translation>Cannot create the run</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="542"/>
        <source>Erreur inattendue</source>
        <translation>Unexpected error</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="575"/>
        <source>Configuration des providers invalide</source>
        <translation>Invalid provider configuration</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="649"/>
        <source>Annuler le run ?</source>
        <translation>Cancel the run?</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="650"/>
        <source>Annuler le run en cours ?

Le pipeline s&apos;arrêtera à la prochaine frontière sûre. Le dossier de sortie sera ensuite **supprimé** (livrables Markdown générés jusqu&apos;ici) et le cockpit réinitialisé.

Cette action ne supprime pas les fichiers source originaux ni les artefacts intermédiaires de « workspace ».</source>
        <translation>Cancel the run in progress?

The pipeline will stop at the next safe boundary. The output folder will then be **deleted** (Markdown deliverables produced so far) and the cockpit will be reset.

This action does not delete the original source files or the intermediate “workspace” artefacts.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="683"/>
        <source>Sélectionne un projet dans la sidebar avant d&apos;exporter.</source>
        <translation>Select a project in the sidebar before exporting.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="692"/>
        <location filename="../../ui/generation_controller.py" line="764"/>
        <location filename="../../ui/generation_controller.py" line="1162"/>
        <source>Génération non configurée</source>
        <translation>Generation not configured</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="695"/>
        <source>Configurez d&apos;abord la génération (⚙ Réglages).</source>
        <translation>Configure the generation first (⚙ Settings).</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="729"/>
        <source>Aucun dossier de sortie</source>
        <translation>No output folder</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="732"/>
        <source>Le dossier de sortie n&apos;existe pas encore. Lancez d&apos;abord un run pour ce projet.</source>
        <translation>The output folder does not exist yet. Run a generation first for this project.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="755"/>
        <source>Sélectionne un projet dans la sidebar avant d&apos;estimer.</source>
        <translation>Select a project in the sidebar before estimating.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="767"/>
        <location filename="../../ui/generation_controller.py" line="1165"/>
        <source>Configurez d&apos;abord les réglages de génération de ce projet.</source>
        <translation>Configure this project&apos;s generation settings first.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="779"/>
        <source>Dossier d&apos;entrée invalide</source>
        <translation>Invalid input folder</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="833"/>
        <source>Sélectionne un projet dans la sidebar avant de configurer la génération.</source>
        <translation>Select a project in the sidebar before configuring the generation.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="972"/>
        <source>Sélectionne un projet dans la sidebar avant de réinitialiser.</source>
        <translation>Select a project in the sidebar before resetting.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="981"/>
        <source>Run en cours</source>
        <translation>Run in progress</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="982"/>
        <source>Impossible de réinitialiser pendant un run. Annule-le d&apos;abord.</source>
        <translation>Cannot reset while a run is in progress. Cancel it first.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="990"/>
        <source>Réinitialiser la génération ?</source>
        <translation>Reset the generation?</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="993"/>
        <source>Réinitialiser la génération de « {name} » ?

Tous les livrables produits (transcriptions, glossaire, documents) et l&apos;historique des runs en base seront supprimés. Le dossier d&apos;entrée n&apos;est pas touché. Cette action est irréversible.</source>
        <translation>Reset the generation for “{name}”?

All produced deliverables (transcripts, glossary, documents) and the run history in the database will be deleted. The input folder is not touched. This action is irreversible.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="1047"/>
        <source>Le run s&apos;est terminé sur une erreur inattendue</source>
        <translation>The run ended with an unexpected error</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="1149"/>
        <source>Clé DeepSeek manquante</source>
        <translation>DeepSeek key missing</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="1152"/>
        <source>Renseigne la clé DeepSeek dans « Édition → Paramètres globaux ».</source>
        <translation>Enter the DeepSeek key under “Edit → Global settings”.</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="1175"/>
        <source>Clé OpenAI manquante</source>
        <translation>OpenAI key missing</translation>
    </message>
    <message>
        <location filename="../../ui/generation_controller.py" line="1178"/>
        <source>Le provider STT cloud nécessite une clé OpenAI. Renseigne-la dans « Édition → Paramètres globaux ».</source>
        <translation>The cloud STT provider requires an OpenAI key. Enter it under “Edit → Global settings”.</translation>
    </message>
</context>
<context>
    <name>GenerationSettingsView</name>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="118"/>
        <source>Réglages de la génération</source>
        <translation>Generation settings</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="119"/>
        <source>Configurer la génération</source>
        <translation>Configure generation</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="127"/>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="362"/>
        <source>Style</source>
        <translation>Style</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="128"/>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="421"/>
        <source>Sources</source>
        <translation>Sources</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="129"/>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="481"/>
        <source>Transcription</source>
        <translation>Transcription</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="130"/>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="536"/>
        <source>Génération IA</source>
        <translation>AI generation</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="131"/>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="588"/>
        <source>Phases IA</source>
        <translation>AI phases</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="132"/>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="605"/>
        <source>Export</source>
        <translation>Export</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="171"/>
        <source>Décontracté</source>
        <translation>Casual</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="172"/>
        <source>Standard</source>
        <translation>Standard</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="173"/>
        <source>Professionnel</source>
        <translation>Professional</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="174"/>
        <source>Académique</source>
        <translation>Academic</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="181"/>
        <source>Conserver l&apos;ordre — 1 source = 1 chapitre</source>
        <translation>Preserve order — 1 source = 1 chapter</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="184"/>
        <source>Synthèse thématique — refonte transversale</source>
        <translation>Thematic synthesis — cross-cutting rewrite</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="192"/>
        <source>Hors ligne (GPU local, gratuit)</source>
        <translation>Offline (local GPU, free)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="194"/>
        <source>En ligne (OpenAI, payant)</source>
        <translation>Online (OpenAI, paid)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="211"/>
        <source>Dossier scanné en mode automatique : tous les fichiers vidéo, audio et documents (PDF, Word, Markdown, texte) y sont ramassés.</source>
        <translation>Folder scanned automatically: all video, audio, and document files (PDF, Word, Markdown, text) are picked up from it.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="215"/>
        <source>Choisir…</source>
        <translation>Choose…</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="217"/>
        <source>Choisir le dossier contenant les sources à traiter.</source>
        <translation>Choose the folder containing the sources to process.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="224"/>
        <source>Une vidéo YouTube par ligne (liens unitaires).
Ex. : https://youtu.be/XXXXXXXXXXX</source>
        <translation>One YouTube video per line (single links).
Ex. : https://youtu.be/XXXXXXXXXXX</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="240"/>
        <source>Détermine le ton et le registre du document final (décontracté, standard, professionnel ou académique).</source>
        <translation>Sets the tone and register of the final document (casual, standard, professional, or academic).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="252"/>
        <source>Conserver l&apos;ordre : assemble les sources dans l&apos;ordre choisi (contenu recopié tel quel). Synthèse thématique : l&apos;IA refond tout par thème (l&apos;ordre n&apos;a alors plus d&apos;effet).</source>
        <translation>Preserve order: assembles the sources in the chosen order (content copied as-is). Thematic synthesis: the AI rewrites everything by theme (order then has no effect).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="264"/>
        <source>Consignes libres pour orienter la reformulation. Ex. : « ton chaleureux mais rigoureux, exemples concrets, éviter le jargon inutile ».</source>
        <translation>Free guidance to steer the rephrasing. Ex.: “warm but rigorous tone, concrete examples, avoid unnecessary jargon”.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="272"/>
        <source>Reformuler les documents (PDF, Word, Markdown, texte)</source>
        <translation>Rephrase documents (PDF, Word, Markdown, text)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="276"/>
        <source>Si coché (défaut), les documents texte passent par la reformulation comme une transcription orale. Décoché : le texte est inséré tel quel (cours déjà bien rédigé).</source>
        <translation>If checked (default), text documents go through rephrasing like a transcript. Unchecked: the text is inserted as-is (course already well written).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="288"/>
        <source>Mode hors ligne : GPU NVIDIA requis, sans coût. Mode en ligne : OpenAI, facturé à la minute, recommandé pour les longues durées.</source>
        <translation>Offline mode: NVIDIA GPU required, no cost. Online mode: OpenAI, billed per minute, recommended for long content.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="300"/>
        <source>Conserver les fichiers audio (réécoute / dépannage)</source>
        <translation>Keep audio files (replay / troubleshooting)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="304"/>
        <source>Si coché, les fichiers .wav extraits des médias (vidéo/audio/YouTube) ne sont pas supprimés après la transcription.</source>
        <translation>If checked, the .wav files extracted from media (video/audio/YouTube) are not deleted after transcription.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="315"/>
        <source>Transcriptions cloud simultanées (sans effet en STT local : 1 GPU).</source>
        <translation>Simultaneous cloud transcriptions (no effect on local STT: 1 GPU).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="328"/>
        <source>Pas de plafond</source>
        <translation>No cap</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="331"/>
        <source>Coût maximal en USD. La génération s&apos;arrête si elle s&apos;en approche. Mettez 0 pour désactiver le plafond.</source>
        <translation>Maximum cost in USD. Generation stops as it approaches it. Set 0 to disable the cap.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="344"/>
        <source>Appels IA simultanés (le compte concurrence DeepSeek est élevé).</source>
        <translation>Simultaneous AI calls (DeepSeek concurrency limits are high).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="364"/>
        <source>Ton, mise en forme et mode d&apos;assemblage du document consolidé.</source>
        <translation>Tone, formatting, and assembly mode of the consolidated document.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="371"/>
        <source>Mise en forme</source>
        <translation>Formatting</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="373"/>
        <source>Préréglage de style, mode d&apos;assemblage des sources et consignes libres pour orienter l&apos;écriture.</source>
        <translation>Style preset, source assembly mode, and free guidance to steer the writing.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="378"/>
        <source>Préréglage de style</source>
        <translation>Style preset</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="379"/>
        <source>Mode d&apos;assemblage</source>
        <translation>Assembly mode</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="381"/>
        <source>Consignes de style</source>
        <translation>Style guidance</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="388"/>
        <source>Optionnel — laissez vide pour le comportement par défaut.</source>
        <translation>Optional — leave blank for the default behaviour.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="396"/>
        <source>Documents texte</source>
        <translation>Text documents</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="398"/>
        <source>Comportement appliqué aux fichiers PDF, Word, Markdown et texte.</source>
        <translation>Behaviour applied to PDF, Word, Markdown, and text files.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="406"/>
        <source>Décochez pour les cours déjà rédigés (insertion telle quelle, coût nul).</source>
        <translation>Uncheck for courses already written out (inserted as-is, zero cost).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="423"/>
        <source>Dossier des fichiers à traiter, vidéos YouTube, langues à produire et ordre d&apos;apparition des sources dans le document.</source>
        <translation>Folder of files to process, YouTube videos, languages to produce, and order of sources in the document.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="431"/>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="628"/>
        <source>Dossier des sources</source>
        <translation>Source folder</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="433"/>
        <source>Dossier scanné pour les vidéos, audios et documents à traiter.</source>
        <translation>Folder scanned for the videos, audio, and documents to process.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="444"/>
        <source>Vidéos YouTube</source>
        <translation>YouTube videos</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="446"/>
        <source>Liens YouTube unitaires (une URL par ligne). La vidéo est téléchargée puis transcrite comme une vidéo locale.</source>
        <translation>Single YouTube links (one URL per line). The video is downloaded and then transcribed like a local video.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="455"/>
        <source>Langues du document</source>
        <translation>Document languages</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="457"/>
        <source>Langues à produire pour le document consolidé. La langue « principale » est l&apos;originale ; les autres en sont des traductions automatiques.</source>
        <translation>Languages to produce for the consolidated document. The “primary” language is the original; the others are automatic translations.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="466"/>
        <source>Ordre et exclusions</source>
        <translation>Order and exclusions</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="468"/>
        <source>Ordre d&apos;apparition des sources dans le document, et exclusions éventuelles.</source>
        <translation>Order of sources in the document, and optional exclusions.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="483"/>
        <source>Moteur et modèle utilisés pour transcrire les vidéos et fichiers audio.</source>
        <translation>Engine and model used to transcribe the videos and audio files.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="490"/>
        <source>Moteur de transcription</source>
        <translation>Transcription engine</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="492"/>
        <source>Mode hors ligne (GPU local, sans coût) ou en ligne (OpenAI, plus précis sur les longues durées).</source>
        <translation>Offline mode (local GPU, no cost) or online (OpenAI, more accurate on long content).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="497"/>
        <source>Moteur</source>
        <translation>Engine</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="503"/>
        <source>Modèle de transcription</source>
        <translation>Transcription model</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="505"/>
        <source>Choix du modèle ; un seul est actif à la fois, selon le moteur choisi.</source>
        <translation>Model choice; only one is active at a time, depending on the chosen engine.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="509"/>
        <source>Modèle hors ligne (GPU)</source>
        <translation>Offline model (GPU)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="510"/>
        <source>Modèle en ligne (OpenAI)</source>
        <translation>Online model (OpenAI)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="516"/>
        <source>Performance et conservation</source>
        <translation>Performance and retention</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="518"/>
        <source>Parallélisme des transcriptions en ligne et gestion des fichiers audio extraits.</source>
        <translation>Parallelism of online transcriptions and management of extracted audio files.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="522"/>
        <source>Transcriptions simultanées</source>
        <translation>Simultaneous transcriptions</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="538"/>
        <source>Modèle de génération, plafond de budget et nombre de traitements en parallèle.</source>
        <translation>Generation model, budget cap, and number of parallel jobs.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="544"/>
        <source>Modèle de génération</source>
        <translation>Generation model</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="546"/>
        <source>Modèle DeepSeek utilisé pour les phases de reformulation, structuration, consolidation, traduction et cohérence.</source>
        <translation>DeepSeek model used for the rephrasing, structuring, consolidation, translation, and coherence phases.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="551"/>
        <source>Modèle</source>
        <translation>Model</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="557"/>
        <source>Budget</source>
        <translation>Budget</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="559"/>
        <source>Plafond de dépense — la génération s&apos;arrête si le coût l&apos;atteint.</source>
        <translation>Spending cap — generation stops if the cost reaches it.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="563"/>
        <source>Budget maximal</source>
        <translation>Maximum budget</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="569"/>
        <source>Performance</source>
        <translation>Performance</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="571"/>
        <source>Nombre d&apos;appels IA simultanés. Plus rapide, n&apos;augmente pas le coût.</source>
        <translation>Number of simultaneous AI calls. Faster, does not raise the cost.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="575"/>
        <source>Traitements IA simultanés</source>
        <translation>Simultaneous AI jobs</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="590"/>
        <source>Réglages fins pour chacune des 7 phases IA du pipeline (thinking, intensité, température, retries). Laissez les valeurs par défaut sauf cas particulier.</source>
        <translation>Fine-grained settings for each of the 7 AI pipeline phases (thinking, intensity, temperature, retries). Leave defaults unless required.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="607"/>
        <source>Formats proposés lors de l&apos;export du document consolidé et du glossaire.</source>
        <translation>Formats offered when exporting the consolidated document and the glossary.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="611"/>
        <source>Formats à exporter</source>
        <translation>Formats to export</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="619"/>
        <source>Sans sélection, l&apos;export laissera le choix au moment de l&apos;action.</source>
        <translation>Without a selection, the export will offer a choice at action time.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="685"/>
        <source>GPU NVIDIA introuvable</source>
        <translation>NVIDIA GPU not found</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="687"/>
        <source>Le mode de transcription locale nécessite un GPU NVIDIA compatible CUDA.

Veuillez utiliser le mode OpenAI en ligne.</source>
        <translation>Local transcription requires an NVIDIA CUDA-compatible GPU.

Please use the OpenAI online mode.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="757"/>
        <source>Dossier des sources manquant</source>
        <translation>Source folder missing</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/generation_settings_view.py" line="759"/>
        <source>Veuillez sélectionner le dossier des sources (vidéos, audios, documents).</source>
        <translation>Please select the source folder (videos, audio, documents).</translation>
    </message>
</context>
<context>
    <name>GenerationTab</name>
    <message>
        <location filename="../../ui/features/generation_tab.py" line="30"/>
        <source>Génération</source>
        <extracomment>Stubs PySide6 : ``QT_TRANSLATE_NOOP`` est typé ``object`` ; on caste car la fonction renvoie son argument textuel tel quel.</extracomment>
        <translation>Generation</translation>
    </message>
    <message>
        <location filename="../../ui/features/generation_tab.py" line="33"/>
        <source>Exporte les livrables de la génération (document consolidé et glossaire) dans les formats cochés (Markdown / PDF / HTML).</source>
        <translation>Export the generation deliverables (consolidated document and glossary) in the selected formats (Markdown / PDF / HTML).</translation>
    </message>
</context>
<context>
    <name>GlobalSettingsDialog</name>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="75"/>
        <source>Paramètres globaux</source>
        <extracomment>Largeur minimale du dialogue (px). Marges externes du dialogue. Largeur min/max de la colonne centrale.</extracomment>
        <translation>Global settings</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="108"/>
        <source>Système</source>
        <translation>System</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="109"/>
        <source>Clair</source>
        <translation>Light</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="110"/>
        <source>Sombre</source>
        <translation>Dark</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="121"/>
        <source>Clés API</source>
        <translation>API keys</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="123"/>
        <source>Les clés sont chiffrées localement (Windows DPAPI) et ne quittent jamais votre ordinateur en clair.</source>
        <translation>Keys are encrypted locally (Windows DPAPI) and never leave your computer in clear text.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="132"/>
        <source>Clé personnelle OpenAI utilisée pour la transcription en ligne et la recherche sémantique du Dialogue.</source>
        <translation>Personal OpenAI key used for online transcription and semantic search in the Dialogue.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="139"/>
        <source>Clé API OpenAI</source>
        <translation>OpenAI API key</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="145"/>
        <source>Clé personnelle DeepSeek utilisée pour la reformulation, les supports pédagogiques et les réponses du Dialogue.</source>
        <translation>Personal DeepSeek key used for rephrasing, revision materials, and Dialogue answers.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="152"/>
        <source>Clé API DeepSeek</source>
        <translation>DeepSeek API key</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="164"/>
        <source>Apparence</source>
        <translation>Appearance</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="166"/>
        <source>Choisissez un mode clair, sombre, ou laissez Fahmi2 suivre le thème de votre système (Windows).</source>
        <translation>Pick a light or dark mode, or let Fahmi2 follow your system theme (Windows).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="174"/>
        <source>« Système » suit automatiquement le thème de Windows. « Clair » ou « Sombre » force l&apos;apparence indépendamment du système.</source>
        <translation>“System” follows the Windows theme automatically. “Light” or “Dark” forces the appearance independently of the system.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="185"/>
        <source>Thème de l&apos;interface</source>
        <translation>Interface theme</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="191"/>
        <source>Le changement s&apos;applique immédiatement à toute l&apos;application.</source>
        <translation>The change applies immediately to the whole application.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="205"/>
        <source>Langue</source>
        <translation>Language</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="207"/>
        <source>Choisissez la langue de l&apos;interface. Le changement s&apos;applique au prochain démarrage de Fahmi2.</source>
        <translation>Choose the interface language. The change applies the next time Fahmi2 starts.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="215"/>
        <source>Sélectionne la langue d&apos;affichage des menus, boutons et libellés. N&apos;affecte ni le contenu des projets, ni les langues de sortie du pipeline (qui se règlent par projet).</source>
        <translation>Sets the language for menus, buttons, and labels. Does not affect project content, nor pipeline output languages (those are set per project).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="230"/>
        <source>Langue de l&apos;interface</source>
        <translation>Interface language</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="236"/>
        <source>Le changement de langue s&apos;applique au prochain démarrage de Fahmi2.</source>
        <translation>The language change applies the next time Fahmi2 starts.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="301"/>
        <source>Redémarrage requis</source>
        <translation>Restart required</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/global_settings_dialog.py" line="303"/>
        <source>La langue de l&apos;interface a été enregistrée. Elle sera appliquée au prochain démarrage de Fahmi2.</source>
        <translation>The interface language has been saved. It will take effect the next time Fahmi2 starts.</translation>
    </message>
</context>
<context>
    <name>LanguageSelectionView</name>
    <message>
        <location filename="../../ui/widgets/language_selection_view.py" line="56"/>
        <source>Produites</source>
        <translation>Produced</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/language_selection_view.py" line="66"/>
        <source>Principale (originale)</source>
        <translation>Primary (original)</translation>
    </message>
</context>
<context>
    <name>LogsDock</name>
    <message>
        <location filename="../../ui/widgets/logs_dock.py" line="35"/>
        <source>INFO</source>
        <extracomment>Couleurs et libellés **sources** par sévérité — alignés sur le thème Clair Fluent. Les libellés sont marqués par :func:`QT_TRANSLATE_NOOP` pour extraction ; la résolution effective passe par :func:`_severity_label` à l&apos;usage (le ``QTranslator`` n&apos;est pas installé à l&apos;import du module).</extracomment>
        <translation>INFO</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/logs_dock.py" line="36"/>
        <source>WARN</source>
        <translation>WARN</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/logs_dock.py" line="37"/>
        <source>ERREUR</source>
        <translation>ERROR</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/logs_dock.py" line="38"/>
        <source>FATAL</source>
        <translation>FATAL</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/logs_dock.py" line="60"/>
        <source>Logs</source>
        <translation>Logs</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/logs_dock.py" line="78"/>
        <source>Niveau minimum</source>
        <translation>Minimum level</translation>
    </message>
</context>
<context>
    <name>MainWindow</name>
    <message>
        <location filename="../../ui/main_window.py" line="172"/>
        <source>Fichier</source>
        <extracomment>Nom de produit (non traduit — marque). Largeur initiale de la sidebar projets (px). Suffisamment large pour accueillir des noms de projet de taille moyenne sans tronquer le sous-libellé « Génération ... · Supports ... ». Reste redimensionnable via le QSplitter (l&apos;utilisateur peut élargir ou réduire à sa convenance). Largeur minimale absolue de la sidebar (empêche de la réduire à rien).</extracomment>
        <translation>File</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="174"/>
        <source>Nouveau projet…</source>
        <translation>New project…</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="177"/>
        <source>Quitter</source>
        <translation>Quit</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="181"/>
        <source>Édition</source>
        <translation>Edit</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="183"/>
        <source>Paramètres globaux…</source>
        <translation>Global settings…</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="185"/>
        <source>Modifier les prompts…</source>
        <translation>Edit prompts…</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="188"/>
        <source>Aide</source>
        <translation>Help</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="190"/>
        <source>À propos</source>
        <translation>About</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="200"/>
        <source>À propos de Fahmi2</source>
        <translation>About Fahmi2</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="206"/>
        <source>&lt;b&gt;Fahmi2&lt;/b&gt; — version {version}&lt;br&gt;&lt;br&gt;Transformez vos entrants — vidéos, fichiers audio, liens YouTube ou documents texte (PDF, Word, Markdown, txt) — en un document consolidé et structuré (reformulé, chapitré, avec glossaire, multilingue : français, anglais, allemand, espagnol, italien, chinois, arabe), assemblé dans l&apos;ordre des sources ou par refonte thématique transversale.&lt;br&gt;&lt;br&gt;Le consolidé et le glossaire s&apos;exportent en Markdown / PDF / HTML / Word (.docx) — le chinois et l&apos;arabe (droite-à-gauche) y sont rendus correctement.&lt;br&gt;&lt;br&gt;Puis exploitez ce corpus sans effort :&lt;ul&gt;&lt;li&gt;supports de révision (flashcards, QCM, fiches, examen blanc…, exports Anki / Markdown / PDF / HTML / Word)&lt;/li&gt;&lt;li&gt;dialogue (chat ancré sur le cours, réponses citées et diffusées en streaming).&lt;/li&gt;&lt;/ul&gt;Le tout en quelques minutes et sans intervention manuelle.</source>
        <translation>&lt;b&gt;Fahmi2&lt;/b&gt; — version {version}&lt;br&gt;&lt;br&gt;Turn your inputs — videos, audio files, YouTube links, or text documents (PDF, Word, Markdown, txt) — into a consolidated, structured document (rephrased, chaptered, with a glossary, multilingual: French, English, German, Spanish, Italian, Chinese, Arabic), assembled either in source order or as a cross-cutting thematic rewrite.&lt;br&gt;&lt;br&gt;The consolidated document and the glossary export to Markdown / PDF / HTML / Word (.docx) — Chinese and Arabic (right-to-left) render correctly.&lt;br&gt;&lt;br&gt;Then make use of this corpus effortlessly:&lt;ul&gt;&lt;li&gt;revision aids (flashcards, MCQs, summary sheets, mock exam…, exports to Anki / Markdown / PDF / HTML / Word)&lt;/li&gt;&lt;li&gt;dialogue (chat anchored on the course, cited and streamed answers).&lt;/li&gt;&lt;/ul&gt;All in a few minutes, with no manual intervention.</translation>
    </message>
</context>
<context>
    <name>ModelLabels</name>
    <message>
        <location filename="../../ui/_model_labels.py" line="41"/>
        <source>DeepSeek V4 Flash (économique)</source>
        <extracomment>Chaînes sources des libellés de modèles LLM. ``cast(str, …)`` corrige l&apos;annotation ``object`` des stubs PySide6 ; le contexte ``&quot;ModelLabels&quot;`` est passé en littéral car ``pyside6-lupdate`` n&apos;extrait pas les chaînes quand l&apos;argument context est une variable.</extracomment>
        <translation>DeepSeek V4 Flash (economical)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="45"/>
        <source>DeepSeek V4 Pro (capacité supérieure)</source>
        <translation>DeepSeek V4 Pro (higher capacity)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="52"/>
        <source>text-embedding-3-small (économique)</source>
        <translation>text-embedding-3-small (economical)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="56"/>
        <source>text-embedding-3-large (précision supérieure)</source>
        <translation>text-embedding-3-large (higher precision)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="62"/>
        <source>text-embedding-ada-002 (génération précédente)</source>
        <translation>text-embedding-ada-002 (previous generation)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="70"/>
        <source>large-v3-turbo (équilibré)</source>
        <translation>large-v3-turbo (balanced)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="73"/>
        <source>large-v3 (précision maximale)</source>
        <translation>large-v3 (maximum precision)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="76"/>
        <source>medium (plus léger / rapide)</source>
        <translation>medium (lighter / faster)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="79"/>
        <source>small (rapide, faible VRAM)</source>
        <translation>small (fast, low VRAM)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="85"/>
        <source>whisper-1 (timestamps fins)</source>
        <translation>whisper-1 (fine-grained timestamps)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="89"/>
        <source>gpt-4o-transcribe (précision supérieure)</source>
        <translation>gpt-4o-transcribe (higher precision)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="93"/>
        <source>gpt-4o-mini-transcribe (2× moins cher)</source>
        <translation>gpt-4o-mini-transcribe (2× cheaper)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="98"/>
        <source>Automatique (serveur)</source>
        <translation>Automatic (server)</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="102"/>
        <source>Élevée</source>
        <translation>High</translation>
    </message>
    <message>
        <location filename="../../ui/_model_labels.py" line="103"/>
        <source>Maximale</source>
        <translation>Maximum</translation>
    </message>
</context>
<context>
    <name>NewProjectDialog</name>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="69"/>
        <source>Renommer le projet</source>
        <extracomment>Largeur minimale (px) du dialogue (donne assez de place à la carte centrée). Marges externes du dialogue. Largeur min/max de la colonne contenant la carte (centrée).</extracomment>
        <translation>Rename project</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="70"/>
        <source>Nouveau projet</source>
        <translation>New project</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="79"/>
        <source>Nom court et reconnaissable affiché dans la liste des projets.</source>
        <translation>Short, recognisable name shown in the project list.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="84"/>
        <source>Choisir…</source>
        <translation>Choose…</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="87"/>
        <source>Choisissez le dossier qui contiendra les livrables du projet.</source>
        <translation>Choose the folder that will contain the project deliverables.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="124"/>
        <source>Identité du projet</source>
        <translation>Project identity</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="126"/>
        <source>Nom du projet et dossier de travail. Le dossier est défini une seule fois à la création et ne peut plus être déplacé ensuite.</source>
        <translation>Project name and working folder. The folder is set once at creation and cannot be moved afterwards.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="131"/>
        <source>Nom du projet</source>
        <translation>Project name</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="137"/>
        <source>Dossier du projet</source>
        <translation>Project folder</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="141"/>
        <source>Le dossier du projet est fixé à la création et ne peut plus être modifié.</source>
        <translation>The project folder is set at creation and cannot be changed.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="145"/>
        <source>Ce dossier contiendra le document consolidé, le glossaire et les supports générés. Choisissez un emplacement où vous gardez vos travaux.</source>
        <translation>This folder will contain the consolidated document, the glossary, and the generated materials. Pick a location where you keep your work.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="178"/>
        <source>Créer le projet</source>
        <translation>Create project</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="194"/>
        <source>Emplacement du projet</source>
        <translation>Project location</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="206"/>
        <source>Champs manquants</source>
        <translation>Missing fields</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/new_project_dialog.py" line="208"/>
        <source>Veuillez renseigner le nom et l&apos;emplacement du projet.</source>
        <translation>Please fill in the project name and location.</translation>
    </message>
</context>
<context>
    <name>PedagogyController</name>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="299"/>
        <location filename="../../ui/pedagogy_controller.py" line="363"/>
        <location filename="../../ui/pedagogy_controller.py" line="484"/>
        <location filename="../../ui/pedagogy_controller.py" line="545"/>
        <location filename="../../ui/pedagogy_controller.py" line="621"/>
        <source>Aucun projet sélectionné</source>
        <extracomment>Plafond de coût atteint : statut renvoyé par l&apos;orchestrateur. Émis quand le statut de la génération change (démarrage / fin / échec / réinitialisation), pour rafraîchir les icônes de la sidebar.</extracomment>
        <translation>No project selected</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="302"/>
        <source>Sélectionne un projet dans la sidebar avant de configurer.</source>
        <translation>Select a project in the sidebar before configuring.</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="330"/>
        <location filename="../../ui/pedagogy_controller.py" line="633"/>
        <source>Supports non configurés</source>
        <translation>Materials not configured</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="333"/>
        <location filename="../../ui/pedagogy_controller.py" line="636"/>
        <source>Configurez d&apos;abord les supports pédagogiques (⚙ Réglages).</source>
        <translation>Configure the revision materials first (⚙ Settings).</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="366"/>
        <source>Sélectionne un projet dans la sidebar avant de générer.</source>
        <translation>Select a project in the sidebar before generating.</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="375"/>
        <source>Génération déjà en cours</source>
        <translation>Generation already in progress</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="378"/>
        <source>Une génération de supports est déjà en cours.</source>
        <translation>A materials generation is already in progress.</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="462"/>
        <source>Aucun dossier de supports</source>
        <translation>No materials folder</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="465"/>
        <source>Aucun support n&apos;a encore été généré pour ce projet.</source>
        <translation>No material has been generated yet for this project.</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="487"/>
        <source>Sélectionne un projet dans la sidebar avant de réinitialiser.</source>
        <translation>Select a project in the sidebar before resetting.</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="496"/>
        <source>Génération en cours</source>
        <translation>Generation in progress</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="499"/>
        <source>Impossible de réinitialiser pendant une génération. Annule-la d&apos;abord.</source>
        <translation>Cannot reset while generation is in progress. Cancel it first.</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="508"/>
        <source>Réinitialiser les supports ?</source>
        <translation>Reset the materials?</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="511"/>
        <source>Réinitialiser les supports pédagogiques de « {name} » ?

Tous les supports générés, leurs exports intermédiaires et l&apos;état d&apos;exécution seront supprimés. Cette action est irréversible.</source>
        <translation>Reset the revision materials for “{name}”?

All generated materials, their intermediate exports, and the execution state will be deleted. This action is irreversible.</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="548"/>
        <location filename="../../ui/pedagogy_controller.py" line="624"/>
        <source>Sélectionne un projet dans la sidebar avant d&apos;exporter.</source>
        <translation>Select a project in the sidebar before exporting.</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="556"/>
        <source>Exporter vers Anki</source>
        <translation>Export to Anki</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="567"/>
        <source>Export impossible</source>
        <translation>Export failed</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="574"/>
        <source>Erreur inattendue</source>
        <translation>Unexpected error</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="581"/>
        <source>Aucun support exportable</source>
        <translation>No exportable material</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="584"/>
        <source>Aucune carte Anki à exporter (flashcards, cloze ou QCM requis). Générez d&apos;abord des supports exportables.</source>
        <translation>No Anki card to export (flashcards, cloze, or MCQs required). Generate exportable materials first.</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="604"/>
        <source>Export terminé</source>
        <translation>Export finished</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="605"/>
        <source>{count} carte(s) Anki exportée(s) vers :
{path}</source>
        <translation>{count} Anki card(s) exported to:
{path}</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_controller.py" line="716"/>
        <source>La génération s&apos;est terminée sur une erreur inattendue</source>
        <translation>Generation ended with an unexpected error</translation>
    </message>
</context>
<context>
    <name>PedagogyLabels</name>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="29"/>
        <source>Flashcards — Concepts</source>
        <translation>Flashcards — Concepts</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="31"/>
        <source>QCM</source>
        <translation>MCQ</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="33"/>
        <source>Vrai / Faux</source>
        <translation>True / False</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="36"/>
        <source>Textes à trous</source>
        <translation>Cloze</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="39"/>
        <source>Questions ouvertes</source>
        <translation>Open questions</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="42"/>
        <source>Fiche de révision</source>
        <translation>Revision sheet</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="45"/>
        <source>Points clés</source>
        <translation>Key points</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="48"/>
        <source>Examen blanc</source>
        <translation>Mock exam</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="53"/>
        <source>Anki (.apkg)</source>
        <translation>Anki (.apkg)</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="54"/>
        <source>Markdown</source>
        <translation>Markdown</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="55"/>
        <source>PDF</source>
        <translation>PDF</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="56"/>
        <source>HTML</source>
        <translation>HTML</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="57"/>
        <source>Word (.docx)</source>
        <translation>Word (.docx)</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="62"/>
        <source>grand public (découverte)</source>
        <translation>general audience (discovery)</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="65"/>
        <source>lycée</source>
        <translation>high school</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="69"/>
        <source>licence (premier cycle universitaire)</source>
        <translation>undergraduate (first cycle)</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="74"/>
        <source>master / expert</source>
        <translation>master / expert</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="81"/>
        <source>automatique (adapté au public cible)</source>
        <translation>automatic (adapted to target audience)</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="85"/>
        <source>restituer (mémorisation, définitions)</source>
        <translation>recall (memorisation, definitions)</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="88"/>
        <source>comprendre et appliquer</source>
        <translation>understand and apply</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="92"/>
        <source>analyser et au-delà (synthèse, évaluation)</source>
        <translation>analyse and beyond (synthesis, evaluation)</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="99"/>
        <source>légère</source>
        <translation>light</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="101"/>
        <source>standard</source>
        <translation>standard</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="103"/>
        <source>dense</source>
        <translation>dense</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="108"/>
        <source>En attente</source>
        <translation>Pending</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="111"/>
        <source>En cours</source>
        <translation>Running</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="114"/>
        <source>Généré</source>
        <translation>Generated</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="117"/>
        <source>À jour</source>
        <translation>Up to date</translation>
    </message>
    <message>
        <location filename="../../ui/pedagogy_labels.py" line="119"/>
        <source>Échec</source>
        <translation>Failed</translation>
    </message>
</context>
<context>
    <name>PedagogyProgress</name>
    <message>
        <location filename="../../ui/widgets/pedagogy_progress_view.py" line="39"/>
        <source>Support</source>
        <extracomment>Snapshot vide. ``row_header`` est résolu à l&apos;usage par :func:`empty_matrix` ci-dessous pour suivre la langue active.</extracomment>
        <translation>Material</translation>
    </message>
</context>
<context>
    <name>PedagogyProgressView</name>
    <message>
        <location filename="../../ui/widgets/pedagogy_progress_view.py" line="88"/>
        <source>Statut</source>
        <translation>Status</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/pedagogy_progress_view.py" line="90"/>
        <source>Supports</source>
        <translation>Materials</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/pedagogy_progress_view.py" line="93"/>
        <source>Langues</source>
        <translation>Languages</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/pedagogy_progress_view.py" line="96"/>
        <source>Durée</source>
        <translation>Duration</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/pedagogy_progress_view.py" line="98"/>
        <source>Coût</source>
        <translation>Cost</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/pedagogy_progress_view.py" line="151"/>
        <source>tâches</source>
        <translation>tasks</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/pedagogy_progress_view.py" line="158"/>
        <source>plafond ${ceiling:.2f}</source>
        <translation>cap ${ceiling:.2f}</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/pedagogy_progress_view.py" line="162"/>
        <source>sans plafond</source>
        <translation>no cap</translation>
    </message>
</context>
<context>
    <name>PedagogySettingsView</name>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="95"/>
        <source>Réglages des supports pédagogiques</source>
        <translation>Revision materials settings</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="96"/>
        <source>Configurer les supports pédagogiques</source>
        <translation>Configure revision materials</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="105"/>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="298"/>
        <source>Supports</source>
        <translation>Materials</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="106"/>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="334"/>
        <source>Difficulté</source>
        <translation>Difficulty</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="107"/>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="385"/>
        <source>Langues</source>
        <translation>Languages</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="108"/>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="405"/>
        <source>Génération IA</source>
        <translation>AI generation</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="109"/>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="463"/>
        <source>Export</source>
        <translation>Export</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="206"/>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="312"/>
        <source>Si coché, le corrigé est généré dans un document distinct du sujet (utile pour les examens blancs).</source>
        <translation>If checked, the answer key is generated in a document separate from the questions (useful for mock exams).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="219"/>
        <source>Niveau d&apos;études supposé du lecteur. Le ton et le vocabulaire s&apos;adaptent.</source>
        <translation>Assumed academic level of the reader. Tone and vocabulary adapt.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="227"/>
        <source>Niveau de la taxonomie de Bloom : comprendre, appliquer, analyser, etc.</source>
        <translation>Bloom’s taxonomy level: understand, apply, analyse, etc.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="234"/>
        <source>Volume final des supports (compact, équilibré, dense).</source>
        <translation>Final volume of the materials (compact, balanced, dense).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="241"/>
        <source>Consignes libres pour l&apos;IA. Ex. : « privilégier des exemples concrets, éviter les pièges trop subtils, varier les formulations ».</source>
        <translation>Free guidance for the AI. Ex.: “prefer concrete examples, avoid overly subtle traps, vary the phrasings”.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="254"/>
        <source>Activer la réflexion approfondie</source>
        <translation>Enable deep reasoning</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="271"/>
        <source>Pas de plafond</source>
        <translation>No cap</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="274"/>
        <source>Coût maximal en USD. La génération s&apos;arrête si elle s&apos;en approche. Mettez 0 pour désactiver le plafond.</source>
        <translation>Maximum cost in USD. Generation stops as it approaches it. Set 0 to disable the cap.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="283"/>
        <source>Nombre de générations IA exécutées en parallèle. Augmenter accélère sans changer le coût (DeepSeek facture au token, pas au temps).</source>
        <translation>Number of AI generations run in parallel. Increasing speeds things up without changing the cost (DeepSeek bills per token, not time).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="300"/>
        <source>Sélectionnez les supports de révision à générer. Pour les supports évaluatifs, cochez « Corrigé séparé » pour générer un sujet sans réponses et un corrigé dans un document distinct.</source>
        <translation>Select the revision materials to generate. For assessment-style materials, check “Separate answer key” to generate a question-only document plus a separate answer key.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="306"/>
        <source>Types de supports</source>
        <translation>Material types</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="308"/>
        <source>Type de support</source>
        <translation>Material type</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="309"/>
        <source>Corrigé séparé</source>
        <translation>Separate answer key</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="336"/>
        <source>Public visé, objectif pédagogique et quantité de contenu — orientent le ton, la difficulté et le volume.</source>
        <translation>Target audience, learning objective, and content amount — drive tone, difficulty, and volume.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="343"/>
        <source>Public et objectif</source>
        <translation>Audience and objective</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="345"/>
        <source>À qui les supports sont-ils destinés, et quel niveau d&apos;apprentissage visent-ils ?</source>
        <translation>Who the materials are intended for, and what learning level they target.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="349"/>
        <source>Public visé</source>
        <translation>Target audience</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="350"/>
        <source>Objectif pédagogique (Bloom)</source>
        <translation>Learning objective (Bloom)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="356"/>
        <source>Densité</source>
        <translation>Density</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="358"/>
        <source>Volume des supports générés : compact pour réviser vite, dense pour creuser.</source>
        <translation>Volume of the generated materials: compact for quick revision, dense to dig deeper.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="362"/>
        <source>Quantité de contenu</source>
        <translation>Content amount</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="368"/>
        <source>Consignes pédagogiques</source>
        <translation>Teaching guidance</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="370"/>
        <source>Optionnel. Indiquez à l&apos;IA toute orientation spécifique.</source>
        <translation>Optional. Tell the AI any specific orientation.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="387"/>
        <source>Les supports sont rédigés dans les langues choisies, même si le document source est dans une autre langue.</source>
        <translation>The materials are written in the chosen languages, even if the source document is in another language.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="392"/>
        <source>Langues à produire</source>
        <translation>Languages to produce</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="407"/>
        <source>Modèle de génération, intensité de réflexion, budget et performance.</source>
        <translation>Generation model, reasoning intensity, budget, and performance.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="414"/>
        <source>Modèle de génération</source>
        <translation>Generation model</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="416"/>
        <source>Modèle DeepSeek utilisé pour rédiger les supports. « Pro » coûte plus mais donne des supports de meilleure qualité.</source>
        <translation>DeepSeek model used to draft the materials. “Pro” costs more but produces higher-quality materials.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="421"/>
        <source>Modèle</source>
        <translation>Model</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="422"/>
        <source>Température</source>
        <translation>Temperature</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="428"/>
        <source>Réflexion approfondie</source>
        <translation>Deep reasoning</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="430"/>
        <source>Active un raisonnement étendu avant la génération — meilleure qualité, coût plus élevé. Recommandé pour les examens blancs.</source>
        <translation>Triggers extended reasoning before generation — better quality, higher cost. Recommended for mock exams.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="436"/>
        <source>Intensité de réflexion</source>
        <translation>Reasoning intensity</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="442"/>
        <source>Budget et performance</source>
        <translation>Budget and performance</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="444"/>
        <source>Plafond de dépense (la génération s&apos;arrête si le coût l&apos;atteint) et nombre de tâches IA traitées en parallèle (plus rapide, n&apos;augmente pas le coût).</source>
        <translation>Spending cap (generation stops if the cost reaches it) and number of AI tasks processed in parallel (faster, does not raise the cost).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="449"/>
        <source>Budget maximal</source>
        <translation>Maximum budget</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="450"/>
        <source>Traitements simultanés</source>
        <translation>Simultaneous jobs</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="465"/>
        <source>Formats proposés lors de l&apos;export depuis l&apos;onglet « Supports pédagogiques ».</source>
        <translation>Formats offered when exporting from the “Revision materials” tab.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="469"/>
        <source>Formats à exporter</source>
        <translation>Formats to export</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="477"/>
        <source>Sans sélection, l&apos;export laissera le choix au moment de l&apos;action.</source>
        <translation>Without a selection, the export will offer a choice at action time.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="515"/>
        <source>Réglages incomplets</source>
        <translation>Incomplete settings</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/pedagogy_settings_view.py" line="516"/>
        <source>Sélectionnez au moins un support et au moins une langue.</source>
        <translation>Select at least one material and at least one language.</translation>
    </message>
</context>
<context>
    <name>PedagogyState</name>
    <message>
        <location filename="../../ui/viewmodels/pedagogy_state.py" line="61"/>
        <source>⚙ À configurer</source>
        <translation>⚙ To configure</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/pedagogy_state.py" line="63"/>
        <source>⚠ Génération requise</source>
        <translation>⚠ Generation required</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/pedagogy_state.py" line="65"/>
        <source>● Prêt à générer</source>
        <translation>● Ready to generate</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/pedagogy_state.py" line="67"/>
        <source>✓ Supports à jour</source>
        <translation>✓ Materials up to date</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/pedagogy_state.py" line="68"/>
        <source>⟳ Supports à régénérer</source>
        <translation>⟳ Materials to regenerate</translation>
    </message>
</context>
<context>
    <name>PedagogyTab</name>
    <message>
        <location filename="../../ui/features/pedagogy_tab.py" line="29"/>
        <source>Supports pédagogiques</source>
        <extracomment>Stubs PySide6 : ``QT_TRANSLATE_NOOP`` est typé ``object`` ; on caste car la fonction renvoie son argument textuel tel quel.</extracomment>
        <translation>Revision materials</translation>
    </message>
    <message>
        <location filename="../../ui/features/pedagogy_tab.py" line="32"/>
        <source>Configurer les supports pédagogiques (supports, difficulté, langues, modèle &amp; coût).</source>
        <translation>Configure the revision materials (materials, difficulty, languages, model &amp; cost).</translation>
    </message>
    <message>
        <location filename="../../ui/features/pedagogy_tab.py" line="40"/>
        <source>Estime le coût LLM de génération des supports sélectionnés (par support × langue × chapitre).</source>
        <translation>Estimate the LLM cost of generating the selected materials (per material × language × chapter).</translation>
    </message>
    <message>
        <location filename="../../ui/features/pedagogy_tab.py" line="48"/>
        <source>Ouvre le dossier « pedagogy » contenant les supports générés (JSON + Markdown).</source>
        <translation>Open the “pedagogy” folder containing the generated materials (JSON + Markdown).</translation>
    </message>
    <message>
        <location filename="../../ui/features/pedagogy_tab.py" line="56"/>
        <source>Exporte les supports vers un paquet Anki (.apkg) : flashcards, cloze et QCM (ré-import sans doublon).</source>
        <translation>Export the materials to an Anki deck (.apkg): flashcards, cloze, and MCQs (re-import without duplicates).</translation>
    </message>
</context>
<context>
    <name>PhaseConfigsWidget</name>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="63"/>
        <source>Configuration des phases LLM</source>
        <translation>LLM phase configuration</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="71"/>
        <source>&lt;b&gt;Phase&lt;/b&gt;</source>
        <translation>&lt;b&gt;Phase&lt;/b&gt;</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="72"/>
        <source>&lt;b&gt;Thinking&lt;/b&gt;</source>
        <translation>&lt;b&gt;Thinking&lt;/b&gt;</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="73"/>
        <source>&lt;b&gt;Effort&lt;/b&gt;</source>
        <translation>&lt;b&gt;Effort&lt;/b&gt;</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="74"/>
        <source>&lt;b&gt;Température&lt;/b&gt;</source>
        <translation>&lt;b&gt;Temperature&lt;/b&gt;</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="75"/>
        <source>&lt;b&gt;Max retries&lt;/b&gt;</source>
        <translation>&lt;b&gt;Max retries&lt;/b&gt;</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="88"/>
        <source>Active le mode raisonnement DeepSeek pour cette phase (envoie {&quot;thinking&quot;: {&quot;type&quot;: &quot;enabled&quot;}}). Qualité supérieure, coût plus élevé.</source>
        <translation>Enables DeepSeek reasoning for this phase (sends {&quot;thinking&quot;: {&quot;type&quot;: &quot;enabled&quot;}}). Higher quality, higher cost.</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="102"/>
        <source>Niveau d&apos;effort de raisonnement (envoie {&quot;reasoning_effort&quot;: &quot;&lt;valeur&gt;&quot;}). Pris en compte uniquement si Thinking est activé.</source>
        <translation>Reasoning effort level (sends {&quot;reasoning_effort&quot;: &quot;&lt;value&gt;&quot;}). Only used if Thinking is on.</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="119"/>
        <source>Température LLM : 0.0 = déterministe, 2.0 = très créatif. 0.2-0.4 pour structuration/reformulation, 0.0-0.2 pour traduction, 0.4-0.6 pour idées créatives.</source>
        <translation>LLM temperature: 0.0 = deterministic, 2.0 = very creative. 0.2-0.4 for structuring/rephrasing, 0.0-0.2 for translation, 0.4-0.6 for creative ideas.</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="131"/>
        <source>Nombre de tentatives en cas d&apos;erreur transitoire (rate limit, serveur indisponible).</source>
        <translation>Number of retries on transient errors (rate limit, server unavailable).</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="145"/>
        <source>1. Extraction des termes</source>
        <translation>1. Term extraction</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="146"/>
        <source>2. Réconciliation glossaire</source>
        <translation>2. Glossary reconciliation</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="147"/>
        <source>3. Reformulation</source>
        <translation>3. Rephrasing</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="148"/>
        <source>4. Structuration</source>
        <translation>4. Structuring</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="149"/>
        <source>5. Consolidation</source>
        <translation>5. Consolidation</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="150"/>
        <source>6. Traduction</source>
        <translation>6. Translation</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/phase_configs_widget.py" line="151"/>
        <source>7. Cohérence finale</source>
        <translation>7. Final coherence</translation>
    </message>
</context>
<context>
    <name>ProjectHeaderBar</name>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="68"/>
        <source>Configurer les réglages de génération (entrée, langues, style, transcription, modèle, phases).</source>
        <translation>Configure the generation settings (input, languages, style, transcription, model, phases).</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="73"/>
        <source>Estime à l&apos;avance le coût total du Run en analysant la durée des sources du dossier d&apos;entrée (STT + LLM).</source>
        <translation>Estimate the total Run cost in advance by analysing the duration of the sources in the input folder (STT + LLM).</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="78"/>
        <source>Ouvre dans l&apos;explorateur le dossier contenant les fichiers Markdown produits (consolidated, glossary, per-video par langue).</source>
        <translation>Open in Explorer the folder containing the produced Markdown files (consolidated, glossary, per-video by language).</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="83"/>
        <source>Supprime tout ce qui a été généré pour cette fonctionnalité (livrables sur disque et état en base). Action irréversible.</source>
        <translation>Delete everything generated for this feature (on-disk deliverables and database state). Irreversible action.</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="87"/>
        <source>⚙️  Réglages</source>
        <translation>⚙️  Settings</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="90"/>
        <source>💵  Estimer le coût</source>
        <translation>💵  Estimate cost</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="98"/>
        <source>🚀  Lancer</source>
        <translation>🚀  Run</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="99"/>
        <source>⏸️  Pause</source>
        <translation>⏸️  Pause</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="100"/>
        <source>▶️  Reprendre</source>
        <translation>▶️  Resume</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="101"/>
        <source>❌  Annuler</source>
        <translation>❌  Cancel</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="103"/>
        <source>📂  Dossier de sortie</source>
        <translation>📂  Output folder</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="106"/>
        <source>📦  Exporter</source>
        <translation>📦  Export</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/project_header_bar.py" line="109"/>
        <source>🗑️  Réinitialiser</source>
        <translation>🗑️  Reset</translation>
    </message>
</context>
<context>
    <name>ProjectsSidebar</name>
    <message>
        <location filename="../../ui/widgets/projects_sidebar.py" line="134"/>
        <source>Génération {gen} · Supports {ped} · Visuels {vis}</source>
        <extracomment>Rôle Qt portant la valeur de ``ProjectId`` dans chaque ``QListWidgetItem``. Glyphe Unicode utilisé comme pastille de statut (cercle plein). Hauteur fixe (px) d&apos;une ligne — assez d&apos;air pour nom + sous-libellé. Marges et espacements internes de la ligne. ``objectName`` de la pastille (stylé via QSS avec la même mécanique ``accent=&quot;success&quot;/&quot;running&quot;/...`` que les valeurs des tuiles de stats). ``objectName`` du nom du projet (titre bold). ``objectName`` du sous-libellé (statuts en clair, gris). Priorité des accents pour la pastille agrégée. Le plus haut « gagne » : si au moins une fonctionnalité est en cours / en pause / en erreur, la pastille reflète cet état plutôt qu&apos;un statut neutre/succès.</extracomment>
        <translation>Generation {gen} · Materials {ped} · Visuals {vis}</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/projects_sidebar.py" line="151"/>
        <source>Génération : {gen}
Supports : {ped}
Visuels : {vis}</source>
        <translation>Generation: {gen}
Materials: {ped}
Visuals: {vis}</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/projects_sidebar.py" line="334"/>
        <source>Modifier…</source>
        <translation>Edit…</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/projects_sidebar.py" line="335"/>
        <source>Supprimer…</source>
        <translation>Delete…</translation>
    </message>
</context>
<context>
    <name>PromptsEditorDialog</name>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="87"/>
        <source>Modifier les prompts</source>
        <extracomment>Police monospace utilisée par l&apos;éditeur (cohérent avec ``#logsDockArea``). ``objectName`` du label de statut (stylé via QSS : ``#promptsEditorStatus``). ``objectName`` de la zone d&apos;édition (stylé via QSS : ``#promptsEditorTextArea``).</extracomment>
        <translation>Edit prompts</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="106"/>
        <source>Éditeur de prompts</source>
        <translation>Prompts editor</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="108"/>
        <source>Personnalisez les prompts Jinja2 utilisés par les phases IA. Vos overrides sont stockés dans %APPDATA%/Fahmi2/prompts et chargés prioritairement au prochain lancement.</source>
        <translation>Customise the Jinja2 prompts used by the AI phases. Your overrides are stored in %APPDATA%/Fahmi2/prompts and are loaded with priority at the next launch.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="192"/>
        <source>💾  Enregistrer</source>
        <translation>💾  Save</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="196"/>
        <source>↩  Réinitialiser au défaut</source>
        <translation>↩  Reset to default</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="242"/>
        <source>Template invalide</source>
        <translation>Invalid template</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="251"/>
        <source>Prompt enregistré</source>
        <translation>Prompt saved</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="252"/>
        <source>L&apos;override est actif au prochain lancement de phase.</source>
        <translation>The override is active at the next phase launch.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="262"/>
        <source>Aucun override actif</source>
        <translation>No active override</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="263"/>
        <source>Ce template n&apos;a pas d&apos;override personnalisé.</source>
        <translation>This template has no custom override.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="268"/>
        <source>Réinitialiser au défaut ?</source>
        <translation>Reset to default?</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="270"/>
        <source>Supprimer l&apos;override personnalisé et restaurer le prompt par défaut bundlé avec l&apos;application ?</source>
        <translation>Delete the custom override and restore the default prompt bundled with the application?</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="328"/>
        <source>✏️ &lt;i&gt;Override personnalisé actif&lt;/i&gt;</source>
        <translation>✏️ &lt;i&gt;Custom override active&lt;/i&gt;</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="332"/>
        <source>📦 &lt;i&gt;Prompt par défaut (aucun override)&lt;/i&gt;</source>
        <translation>📦 &lt;i&gt;Default prompt (no override)&lt;/i&gt;</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="347"/>
        <source>Abandonner les modifications ?</source>
        <translation>Discard changes?</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/prompts_editor_dialog.py" line="349"/>
        <source>Vous avez des modifications non enregistrées sur ce prompt. Les abandonner pour changer de phase ?</source>
        <translation>You have unsaved changes on this prompt. Discard them to switch phase?</translation>
    </message>
</context>
<context>
    <name>RunMatrix</name>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="31"/>
        <source>Ingestion</source>
        <translation>Ingestion</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="32"/>
        <source>Termes</source>
        <translation>Terms</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="33"/>
        <source>Glossaire</source>
        <translation>Glossary</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="36"/>
        <source>Reformul.</source>
        <translation>Rephras.</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="37"/>
        <source>Structur.</source>
        <translation>Structur.</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="38"/>
        <source>Consolid.</source>
        <translation>Consolid.</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="39"/>
        <source>Traduction</source>
        <translation>Translation</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="40"/>
        <source>Cohérence</source>
        <translation>Coherence</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="48"/>
        <source>en attente</source>
        <translation>pending</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="50"/>
        <source>en cours</source>
        <translation>running</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="52"/>
        <source>terminé</source>
        <translation>completed</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="54"/>
        <source>échec</source>
        <translation>failed</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="59"/>
        <source>déjà fait</source>
        <translation>already done</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="178"/>
        <source>Source</source>
        <translation>Source</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="194"/>
        <source> (coût au niveau du run)</source>
        <translation> (run-level cost)</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/run_matrix.py" line="198"/>
        <source>coût</source>
        <translation>cost</translation>
    </message>
</context>
<context>
    <name>SourceOrderView</name>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="94"/>
        <source>ⓘ Mode refonte thématique : l&apos;ordre des sources est sans effet (seule l&apos;inclusion / exclusion compte).</source>
        <extracomment>Codes courts de type de source affichés en préfixe — universels (pas traduits ; restent stables d&apos;une langue à l&apos;autre).</extracomment>
        <translation>ⓘ Thematic synthesis mode: the source order has no effect (only inclusion / exclusion matters).</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="193"/>
        <source>  • nouveau</source>
        <translation>  • new</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="249"/>
        <source>Sources à traiter — ordre des chapitres</source>
        <translation>Sources to process — chapter order</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="255"/>
        <source>Sources exclues</source>
        <translation>Excluded sources</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="287"/>
        <source>▲ Monter</source>
        <translation>▲ Move up</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="288"/>
        <source>Monter la source sélectionnée d&apos;une position</source>
        <translation>Move the selected source up by one position</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="290"/>
        <source>▼ Descendre</source>
        <translation>▼ Move down</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="292"/>
        <source>Descendre la source sélectionnée d&apos;une position</source>
        <translation>Move the selected source down by one position</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="295"/>
        <source>Exclure</source>
        <translation>Exclude</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="296"/>
        <source>Exclure la source sélectionnée du traitement</source>
        <translation>Exclude the selected source from processing</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="317"/>
        <source>Réinclure</source>
        <translation>Re-include</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="318"/>
        <source>Réintégrer la source sélectionnée</source>
        <translation>Re-include the selected source</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="337"/>
        <source>↻ Rafraîchir</source>
        <translation>↻ Refresh</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="340"/>
        <source>Re-scanner le dossier d&apos;entrée pour détecter les nouvelles sources</source>
        <translation>Re-scan the input folder for newly added sources</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="344"/>
        <source>Tout réinclure</source>
        <translation>Re-include all</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/source_order_view.py" line="345"/>
        <source>Réintégrer toutes les sources exclues</source>
        <translation>Re-include all excluded sources</translation>
    </message>
</context>
<context>
    <name>StandardButtons</name>
    <message>
        <location filename="../../ui/_components.py" line="104"/>
        <source>OK</source>
        <extracomment>``objectName`` réservé aux cartes (stylé par les QSS clair/sombre). ``objectName`` réservé au titre d&apos;une carte. ``objectName`` réservé à la description optionnelle sous un titre de carte. ``objectName`` réservé au titre d&apos;un écran de réglages. ``objectName`` réservé à la description d&apos;un écran de réglages. ``objectName`` réservé aux textes d&apos;aide sous un champ. ``objectName`` réservé aux micro-labels de section (majuscules). ``objectName`` réservé aux séparateurs horizontaux fins. ``objectName`` réservé au footer de dialogue (séparateur top + padding). Espacement vertical entre les enfants d&apos;une carte. Hauteur fixe d&apos;un séparateur horizontal (``#hsep``). Marges externes d&apos;une page de réglages (autour de la pile de cartes). Espacement vertical entre les enfants d&apos;une page de réglages. Espacement horizontal d&apos;un formulaire (entre étiquette et champ). Espacement vertical d&apos;un formulaire (entre lignes). Padding horizontal du footer de dialogue (autour de la barre de boutons). Padding vertical du footer de dialogue. Espacement entre les boutons du footer. Libellés **sources FR** des boutons standard Qt (Save/Cancel/Close…) appliqués par :func:`localize_button_box`. Marqués par :func:`QT_TRANSLATE_NOOP` pour extraction ; la résolution effective passe par ``QCoreApplication.translate(&quot;StandardButtons&quot;, source)`` au moment où le bouton est rencontré, donc dans la langue active.</extracomment>
        <translation>OK</translation>
    </message>
    <message>
        <location filename="../../ui/_components.py" line="106"/>
        <source>Annuler</source>
        <translation>Cancel</translation>
    </message>
    <message>
        <location filename="../../ui/_components.py" line="109"/>
        <source>Enregistrer</source>
        <translation>Save</translation>
    </message>
    <message>
        <location filename="../../ui/_components.py" line="112"/>
        <source>Fermer</source>
        <translation>Close</translation>
    </message>
    <message>
        <location filename="../../ui/_components.py" line="114"/>
        <source>Oui</source>
        <translation>Yes</translation>
    </message>
    <message>
        <location filename="../../ui/_components.py" line="115"/>
        <source>Non</source>
        <translation>No</translation>
    </message>
    <message>
        <location filename="../../ui/_components.py" line="117"/>
        <source>Appliquer</source>
        <translation>Apply</translation>
    </message>
    <message>
        <location filename="../../ui/_components.py" line="120"/>
        <source>Abandonner</source>
        <translation>Discard</translation>
    </message>
    <message>
        <location filename="../../ui/_components.py" line="123"/>
        <source>Réinitialiser</source>
        <translation>Reset</translation>
    </message>
    <message>
        <location filename="../../ui/_components.py" line="126"/>
        <source>Aide</source>
        <translation>Help</translation>
    </message>
</context>
<context>
    <name>StatsStripWidget</name>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="54"/>
        <source>Statut</source>
        <translation>Status</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="55"/>
        <source>Sources</source>
        <translation>Sources</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="56"/>
        <source>Phases</source>
        <translation>Phases</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="57"/>
        <source>Langues</source>
        <translation>Languages</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="58"/>
        <source>Durée</source>
        <translation>Duration</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="59"/>
        <source>Coût</source>
        <translation>Cost</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="187"/>
        <source>sources terminées</source>
        <translation>sources completed</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="193"/>
        <source>phases terminées</source>
        <translation>phases completed</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="204"/>
        <source>terminé</source>
        <translation>completed</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="206"/>
        <source>en pause (figée)</source>
        <translation>paused (frozen)</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="216"/>
        <source>plafond ${ceiling:.2f}</source>
        <translation>cap ${ceiling:.2f}</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/stats_strip.py" line="220"/>
        <source>sans plafond</source>
        <translation>no cap</translation>
    </message>
</context>
<context>
    <name>StatusLabels</name>
    <message>
        <location filename="../../ui/status_labels.py" line="33"/>
        <source>Créé</source>
        <extracomment>Libellés FR sources par statut de Run. Marqués par :func:`QT_TRANSLATE_NOOP` pour que ``pyside6-lupdate`` les extraie dans les ``.ts``, sans appeler ``QCoreApplication.translate`` à l&apos;import (le ``QTranslator`` n&apos;est pas encore installé à ce moment). Le **contexte est passé en littéral** : ``pyside6-lupdate`` n&apos;extrait pas les chaînes quand l&apos;argument context est une variable. ``cast(str, …)`` corrige l&apos;annotation ``object`` des stubs PySide6.</extracomment>
        <translation>Created</translation>
    </message>
    <message>
        <location filename="../../ui/status_labels.py" line="34"/>
        <source>En cours</source>
        <translation>Running</translation>
    </message>
    <message>
        <location filename="../../ui/status_labels.py" line="35"/>
        <source>En pause</source>
        <translation>Paused</translation>
    </message>
    <message>
        <location filename="../../ui/status_labels.py" line="36"/>
        <source>Terminé</source>
        <translation>Completed</translation>
    </message>
    <message>
        <location filename="../../ui/status_labels.py" line="37"/>
        <source>Échec</source>
        <translation>Failed</translation>
    </message>
    <message>
        <location filename="../../ui/status_labels.py" line="38"/>
        <source>Annulé</source>
        <translation>Cancelled</translation>
    </message>
</context>
<context>
    <name>VisualsController</name>
    <message>
        <location filename="../../ui/visuals_controller.py" line="325"/>
        <source>Sélectionne un projet dans la sidebar avant de configurer.</source>
        <extracomment>Plafond de coût atteint : note ajoutée au log de fin (statut ``PAUSED``). Émis quand le statut de la génération change (démarrage / fin / échec / réinitialisation), pour rafraîchir les icônes de la sidebar.</extracomment>
        <translation>Select a project in the sidebar before configuring.</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="349"/>
        <location filename="../../ui/visuals_controller.py" line="686"/>
        <source>Visualisations non configurées</source>
        <translation>Visualizations not configured</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="352"/>
        <location filename="../../ui/visuals_controller.py" line="689"/>
        <source>Configurez d&apos;abord les visualisations (⚙ Réglages).</source>
        <translation>Configure the visualizations first (⚙ Settings).</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="393"/>
        <source>Sélectionne un projet dans la sidebar avant de générer.</source>
        <translation>Select a project in the sidebar before generating.</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="402"/>
        <source>Génération déjà en cours</source>
        <translation>Generation already in progress</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="405"/>
        <source>Une génération de visualisations est déjà en cours.</source>
        <translation>A visualization generation is already in progress.</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="503"/>
        <source>Aucun dossier de visualisations</source>
        <translation>No visualizations folder</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="506"/>
        <source>Aucune visualisation n&apos;a encore été produite pour ce projet.</source>
        <translation>No visualization has been produced for this project yet.</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="524"/>
        <source>Sélectionne un projet dans la sidebar avant de réinitialiser.</source>
        <translation>Select a project in the sidebar before resetting.</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="533"/>
        <source>Génération en cours</source>
        <translation>Generation in progress</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="534"/>
        <source>Impossible de réinitialiser pendant une génération. Annule-la d&apos;abord.</source>
        <translation>Cannot reset while generation is in progress. Cancel it first.</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="543"/>
        <source>Réinitialiser les visualisations ?</source>
        <translation>Reset the visualizations?</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="546"/>
        <source>Réinitialiser les visualisations de « {name} » ?

Toutes les pages produites et l&apos;état d&apos;exécution seront supprimés. Cette action est irréversible.</source>
        <translation>Reset the visualizations for “{name}”?

All produced pages and the execution state will be deleted. This action is irreversible.</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="628"/>
        <source>La génération s&apos;est terminée sur une erreur inattendue</source>
        <translation>Generation ended with an unexpected error</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="656"/>
        <source>Aucun projet sélectionné</source>
        <translation>No project selected</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="674"/>
        <source>Clé DeepSeek manquante</source>
        <translation>DeepSeek key missing</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="677"/>
        <source>Renseigne la clé DeepSeek dans « Édition → Paramètres globaux ».</source>
        <translation>Enter the DeepSeek key under “Edit → Global settings”.</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="699"/>
        <source>Génération impossible</source>
        <translation>Generation not possible</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="852"/>
        <source>&lt;b&gt;Projet :&lt;/b&gt; {name}</source>
        <translation>&lt;b&gt;Project:&lt;/b&gt; {name}</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="855"/>
        <source>&lt;b&gt;Langue de structure :&lt;/b&gt; {lang}</source>
        <translation>&lt;b&gt;Structure language:&lt;/b&gt; {lang}</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="858"/>
        <source>&lt;b&gt;Langues latines :&lt;/b&gt; {count}</source>
        <translation>&lt;b&gt;Latin languages:&lt;/b&gt; {count}</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="861"/>
        <source>&lt;b&gt;Unités de texte :&lt;/b&gt; {count}</source>
        <translation>&lt;b&gt;Text units:&lt;/b&gt; {count}</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="867"/>
        <source>Carte des connaissances</source>
        <translation>Knowledge map</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="871"/>
        <source>Diagrammes</source>
        <translation>Diagrams</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="875"/>
        <source>Traduction des libellés</source>
        <translation>Label translation</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_controller.py" line="884"/>
        <source>Estimation du coût des visualisations</source>
        <translation>Visualizations cost estimate</translation>
    </message>
</context>
<context>
    <name>VisualsLabels</name>
    <message>
        <location filename="../../ui/visuals_labels.py" line="34"/>
        <source>Carte des connaissances</source>
        <translation>Knowledge map</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="37"/>
        <source>Diagrammes</source>
        <translation>Diagrams</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="43"/>
        <source>Organigramme</source>
        <translation>Flowchart</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="46"/>
        <source>Chronologie</source>
        <translation>Timeline</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="49"/>
        <source>Comparaison</source>
        <translation>Comparison</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="52"/>
        <source>Hiérarchie</source>
        <translation>Hierarchy</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="54"/>
        <source>Cycle</source>
        <translation>Cycle</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="56"/>
        <source>Arbre de décision</source>
        <translation>Decision tree</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="62"/>
        <source>En attente</source>
        <translation>Pending</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="64"/>
        <source>En cours</source>
        <translation>Running</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="65"/>
        <source>Généré</source>
        <translation>Generated</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="66"/>
        <source>À jour</source>
        <translation>Up to date</translation>
    </message>
    <message>
        <location filename="../../ui/visuals_labels.py" line="67"/>
        <source>Échec</source>
        <translation>Failed</translation>
    </message>
</context>
<context>
    <name>VisualsProgress</name>
    <message>
        <location filename="../../ui/widgets/visuals_progress_view.py" line="39"/>
        <source>Livrable</source>
        <translation>Deliverable</translation>
    </message>
</context>
<context>
    <name>VisualsProgressView</name>
    <message>
        <location filename="../../ui/widgets/visuals_progress_view.py" line="88"/>
        <source>Statut</source>
        <translation>Status</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/visuals_progress_view.py" line="90"/>
        <source>Avancement</source>
        <translation>Progress</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/visuals_progress_view.py" line="93"/>
        <source>Langues</source>
        <translation>Languages</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/visuals_progress_view.py" line="96"/>
        <source>Durée</source>
        <translation>Duration</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/visuals_progress_view.py" line="98"/>
        <source>Coût</source>
        <translation>Cost</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/visuals_progress_view.py" line="151"/>
        <source>langues</source>
        <translation>languages</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/visuals_progress_view.py" line="158"/>
        <source>plafond ${ceiling:.2f}</source>
        <translation>cap ${ceiling:.2f}</translation>
    </message>
    <message>
        <location filename="../../ui/widgets/visuals_progress_view.py" line="162"/>
        <source>sans plafond</source>
        <translation>no cap</translation>
    </message>
</context>
<context>
    <name>VisualsSettingsView</name>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="85"/>
        <source>Réglages des visualisations</source>
        <translation>Visualization settings</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="86"/>
        <source>Configurer les visualisations</source>
        <translation>Configure visualizations</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="94"/>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="265"/>
        <source>Livrables</source>
        <translation>Deliverables</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="95"/>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="295"/>
        <source>Contenu</source>
        <translation>Content</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="96"/>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="334"/>
        <source>Génération IA</source>
        <translation>AI generation</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="176"/>
        <source>Carte des connaissances (graphe interactif)</source>
        <translation>Knowledge map (interactive graph)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="181"/>
        <source>Page HTML autonome présentant un graphe interactif des concepts, termes du glossaire, idées et exemples, avec leurs relations.</source>
        <translation>Standalone HTML page showing an interactive graph of concepts, glossary terms, ideas and examples, with their relationships.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="186"/>
        <source>Diagrammes (galerie de schémas)</source>
        <translation>Diagrams (diagram gallery)</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="191"/>
        <source>Page HTML autonome présentant des organigrammes, chronologies, comparaisons, hiérarchies, cycles et arbres de décision générés.</source>
        <translation>Standalone HTML page showing generated flowcharts, timelines, comparisons, hierarchies, cycles and decision trees.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="199"/>
        <source>Volume des nœuds et diagrammes générés par section (compact, équilibré, dense).</source>
        <translation>Volume of nodes and diagrams generated per section (compact, balanced, dense).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="215"/>
        <source>Activer la réflexion approfondie</source>
        <translation>Enable deep reasoning</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="233"/>
        <source>Pas de plafond</source>
        <translation>No cap</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="236"/>
        <source>Coût maximal en USD. La génération s&apos;arrête si elle s&apos;en approche. Mettez 0 pour désactiver le plafond.</source>
        <translation>Maximum cost in USD. Generation stops as it approaches it. Set 0 to disable the cap.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="245"/>
        <source>Nombre de langues traitées en parallèle. Augmenter accélère sans changer le coût (DeepSeek facture au token, pas au temps).</source>
        <translation>Number of languages processed in parallel. Increasing it speeds things up without changing the cost (DeepSeek bills per token, not per time).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="267"/>
        <source>Choisissez les pages HTML autonomes à produire. Chaque page est complète et hors-ligne (aucune dépendance externe).</source>
        <translation>Choose the standalone HTML pages to produce. Each page is complete and offline (no external dependency).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="272"/>
        <source>Pages à produire</source>
        <translation>Pages to produce</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="280"/>
        <source>Les visualisations sont produites pour chaque langue latine générée (français, anglais, allemand, espagnol, italien). Le chinois et l&apos;arabe ne sont pas pris en charge.</source>
        <translation>Visualizations are produced for each generated Latin-script language (French, English, German, Spanish, Italian). Chinese and Arabic are not supported.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="297"/>
        <source>Densité du contenu extrait et types de diagrammes autorisés.</source>
        <translation>Density of the extracted content and allowed diagram types.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="303"/>
        <source>Densité</source>
        <translation>Density</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="305"/>
        <source>Volume des nœuds et diagrammes : compact pour l&apos;essentiel, dense pour creuser.</source>
        <translation>Volume of nodes and diagrams: compact for the essentials, dense to dig deeper.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="310"/>
        <source>Quantité de contenu</source>
        <translation>Content amount</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="316"/>
        <source>Types de diagrammes</source>
        <translation>Diagram types</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="318"/>
        <source>Types autorisés dans la galerie. L&apos;IA choisit le type adapté à chaque contenu parmi ceux cochés.</source>
        <translation>Types allowed in the gallery. The AI picks the type suited to each content among those checked.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="336"/>
        <source>Modèle de génération, intensité de réflexion, budget et performance.</source>
        <translation>Generation model, reasoning intensity, budget, and performance.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="342"/>
        <source>Modèle de génération</source>
        <translation>Generation model</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="344"/>
        <source>Modèle DeepSeek utilisé pour extraire la structure et traduire les libellés.</source>
        <translation>DeepSeek model used to extract the structure and translate the labels.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="349"/>
        <source>Modèle</source>
        <translation>Model</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="350"/>
        <source>Température</source>
        <translation>Temperature</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="356"/>
        <source>Réflexion approfondie</source>
        <translation>Deep reasoning</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="358"/>
        <source>Active un raisonnement étendu avant l&apos;extraction — meilleure qualité, coût plus élevé.</source>
        <translation>Enables extended reasoning before extraction — better quality, higher cost.</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="364"/>
        <source>Intensité de réflexion</source>
        <translation>Reasoning intensity</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="370"/>
        <source>Budget et performance</source>
        <translation>Budget and performance</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="372"/>
        <source>Plafond de dépense (la génération s&apos;arrête si le coût l&apos;atteint) et nombre de langues traitées en parallèle (plus rapide, n&apos;augmente pas le coût).</source>
        <translation>Spending cap (generation stops if the cost reaches it) and number of languages processed in parallel (faster, does not increase the cost).</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="378"/>
        <source>Budget maximal</source>
        <translation>Maximum budget</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="379"/>
        <source>Traitements simultanés</source>
        <translation>Simultaneous jobs</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="413"/>
        <source>Réglages incomplets</source>
        <translation>Incomplete settings</translation>
    </message>
    <message>
        <location filename="../../ui/dialogs/visuals_settings_view.py" line="415"/>
        <source>Sélectionnez au moins un livrable. Si les diagrammes sont activés, cochez au moins un type de diagramme.</source>
        <translation>Select at least one deliverable. If diagrams are enabled, check at least one diagram type.</translation>
    </message>
</context>
<context>
    <name>VisualsState</name>
    <message>
        <location filename="../../ui/viewmodels/visuals_state.py" line="73"/>
        <source>⚙ À configurer</source>
        <translation>⚙ To configure</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/visuals_state.py" line="75"/>
        <source>⚠ Génération requise</source>
        <translation>⚠ Generation required</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/visuals_state.py" line="77"/>
        <source>● Prêt à générer</source>
        <translation>● Ready to generate</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/visuals_state.py" line="79"/>
        <source>✓ Visualisations à jour</source>
        <translation>✓ Visualizations up to date</translation>
    </message>
    <message>
        <location filename="../../ui/viewmodels/visuals_state.py" line="80"/>
        <source>⟳ Visualisations à régénérer</source>
        <translation>⟳ Visualizations to regenerate</translation>
    </message>
</context>
<context>
    <name>VisualsTab</name>
    <message>
        <location filename="../../ui/features/visuals_tab.py" line="28"/>
        <source>Visualisations</source>
        <extracomment>Stubs PySide6 : ``QT_TRANSLATE_NOOP`` est typé ``object`` ; on caste car la fonction renvoie son argument textuel tel quel.</extracomment>
        <translation>Visualizations</translation>
    </message>
    <message>
        <location filename="../../ui/features/visuals_tab.py" line="31"/>
        <source>Configurer les visualisations (livrables, densité, types de diagrammes, modèle &amp; coût).</source>
        <translation>Configure the visualizations (deliverables, density, diagram types, model &amp; cost).</translation>
    </message>
    <message>
        <location filename="../../ui/features/visuals_tab.py" line="39"/>
        <source>Estime le coût LLM de production des visualisations (extraction de la structure + traduction des libellés par langue).</source>
        <translation>Estimate the LLM cost of producing the visualizations (structure extraction + per-language label translation).</translation>
    </message>
    <message>
        <location filename="../../ui/features/visuals_tab.py" line="47"/>
        <source>Ouvre le dossier « visuals » contenant les pages HTML autonomes produites (carte des connaissances et diagrammes, par langue).</source>
        <translation>Open the “visuals” folder containing the produced standalone HTML pages (knowledge map and diagrams, per language).</translation>
    </message>
</context>
</TS>
