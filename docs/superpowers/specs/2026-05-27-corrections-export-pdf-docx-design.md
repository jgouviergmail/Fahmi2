# Corrections de rendu des exports (PDF arabe/chinois, DOCX paysage) — Conception

**Date :** 2026-05-27
**Branche :** `feat/langues-export-docx`
**Statut :** validé sur données réelles (sondes jetables + inspection visuelle Chrome)

## Problèmes signalés (utilisateur)

1. **PDF arabe — carrés blancs** : certains caractères ne sont pas rendus (carrés ``□``),
   par ex. au chapitre 1.2.1 de `consolidated.ar.pdf`.
2. **PDF chinois — pas de retours à la ligne** : le texte déborde après la marge
   droite (`consolidated.zh.pdf` et `glossary.zh.pdf`).
3. **DOCX — glossaire** : le présenter en **paysage** comme le PDF.
4. **Appliquer ces corrections aux supports pédagogiques.**

## Diagnostic (établi empiriquement)

### 1. Carrés blancs = émojis, pas de l'arabe

Sonde de couverture (cmap d'`arial.ttf` via fontTools) : **tous** les glyphes arabes du
chapitre 1.2.1 sont couverts par Arial. Les seuls caractères non couverts du document
sont des **émojis décoratifs** issus des gabarits de prompt : 📖 (U+1F4D6, ×13),
📝 (U+1F4DD, ×7), 💡 (U+1F4A1, ×5), 🎯 (U+1F3AF, ×2). ReportLab ne sait pas rendre les
émojis couleur (COLR/CPAL) et xhtml2pdf ne fait pas de repli de police par glyphe → ``□``.
Le problème touche **toutes les langues** (HTML/DOCX masquent l'effet via le repli du
navigateur/Word), mais l'utilisateur l'a remarqué sur l'arabe.

### 2. Chinois non coupé = ReportLab ne coupe qu'aux espaces

ReportLab (via xhtml2pdf) coupe les lignes **uniquement aux espaces** (`split(text, " ")`,
mots ré-encodés en `bytes`). Le chinois s'écrit **sans espaces** → un paragraphe = un seul
« mot » insécable → débordement (mesuré : `max_extent` jusqu'à 1520 pt pour une page de
595 pt). La piste CSS `-pdf-word-wrap: CJK` est **inexploitable** : dans xhtml2pdf
**0.2.17** (dernière version), le chemin de dessin CJK mono-fragment construit des lignes
`str` que `_leftDrawParaLine` joint en `bytes` (`b" ".join`) → `TypeError` sur tout
`<p>`/`<li>`. La règle ne fonctionne **que** sur les cellules de tableau (`td`/`th`).
U+200B (espace insécable de largeur nulle) n'est pas un point de coupe pour ReportLab.

### 3. DOCX paysage

`python-docx` : `section.orientation = WD_ORIENT.LANDSCAPE` + permutation
`page_width`/`page_height` sur chaque section. Trivial.

## Décisions de conception

Les corrections de rendu vivent **dans le seul renderer PDF** (`render_markdown_to_pdf`) :
HTML et DOCX s'appuient sur le repli natif du navigateur/Word (émojis OK, CJK coupé
nativement, bidi arabe). Les supports pédagogiques **héritent automatiquement** des
corrections : ils passent par le même `render_markdown_to_pdf` (et `language=` est déjà
propagé par `document_export`/`pedagogy_export`).

### Correction 1 — Retrait des caractères sans glyphe (PDF, toutes langues)

Filtre de couverture **générique** au rendu PDF (même esprit que `_normalize_for_pdf`
pour les tirets) : on retire tout caractère absent de la **cmap de la police active**,
**sauf** les catégories Unicode invisibles/structurelles `{Cc, Cf, Zs, Zl, Zp}` (préserve
``\n``, espaces, et surtout ZWJ/RLM/LRM nécessaires à la jonction/bidi arabe). La
couverture vient de ReportLab lui-même (`pdfmetrics.getFont(name).face.charToGlyph`) — **pas
de dépendance fontTools runtime**. Police active : YaHei (`_CJK_FONT_NAME`) pour le
chinois, Arial (`_PDF_FONT_REGULAR`) sinon (couvre latin + arabe). Validé : seuls les 4
émojis sont retirés du `consolidated.ar.md`, l'arabe reste mis en forme (formes
contextuelles + bidi).

### Correction 2 — Retours à la ligne CJK (PDF)

Approche **hybride** (validée : 0 débordement sur 2845 fragments du consolidé, 0/330 du
glossaire ; rendu visuel propre, sans espaces inter-caractères) :

- **Prose** (`p`, `li`, `blockquote`, `h1..h6`) : **pré-formatage** des nœuds texte CJK via
  `reportlab.lib.textsplit.wordSplit` (qui coupe proprement le CJK caractère par caractère
  **sans** insérer d'espace et préserve les mots latins/chiffres), insertion de `<br/>`. La
  largeur disponible se dérive des constantes de page A4 (`reportlab.lib.pagesizes.A4`) et de
  la marge ; la taille de police par balise (corps/titres) est la **source unique** injectée
  dans le gabarit CSS. Parcours de l'arbre HTML avec **BeautifulSoup** (dépendance déclarée).
- **Tableaux** (`td`/`th`) : règle CSS `td, th { -pdf-word-wrap: CJK; }` injectée dans le
  gabarit, **uniquement pour les langues CJK** (sur du latin elle couperait les mots).

Le pré-formatage et la règle ne s'appliquent qu'aux **langues CJK** (`_CJK_LANGUAGES`,
extensible).

### Correction 3 — DOCX paysage

`render_markdown_to_docx(..., *, landscape=False)` ; quand `True`, permutation des
dimensions + `WD_ORIENT.LANDSCAPE` sur chaque section. Le champ `ExportDocument.pdf_landscape`
devient **`landscape`** (l'orientation concerne désormais PDF **et** DOCX ; `pdf_column_widths`
reste spécifique au PDF). `document_export.write_documents` passe `landscape` aux deux
renderers. Le glossaire de la génération reste le seul document en paysage.

## Fichiers touchés

- `infra/export/markdown_pdf.py` : strip de couverture, pré-formatage CJK, règle table,
  centralisation des tailles de police + marge dans le gabarit.
- `infra/export/markdown_docx.py` : paramètre `landscape`.
- `app/document_export.py` : `pdf_landscape` → `landscape` ; passe `landscape` au DOCX.
- `app/generation_export.py` : `landscape=True` pour le glossaire.
- Tests : `test_markdown_pdf.py`, `test_markdown_docx.py`, `test_generation_export.py`.
- Docs : `CLAUDE.md`, `docs/` pertinents, `README.md`.

## Hors périmètre

- Définitions d'acronymes non traduites : déjà corrigé (prompt `phase_6_glossary_localization`,
  commit `adce5f0`), revalidation par régénération à la charge de l'utilisateur.
- Rendu des émojis en couleur dans le PDF (ReportLab ne le supporte pas) : on retire, on ne
  remplace pas.
