# Langues supplémentaires (de/es/it/zh/ar) + export DOCX — design

- **Date** : 2026-05-26
- **Statut** : **spec validée** (brainstorming terminé)
- **Origine** : demande utilisateur — étendre les langues gérées (aujourd'hui
  FR/EN) à l'allemand, l'espagnol, l'italien, le chinois et l'arabe pour les
  **trois** fonctionnalités (Génération, Supports pédagogiques, Dialogue), **si**
  aucune limitation technique bloquante (STT, embeddings notamment) ; et ajouter
  le format d'export **DOCX**, non géré aujourd'hui.
- **Prérequis** : exports documentaires partagés (`app/document_export`, livré),
  corpus/retrieval du Dialogue (livré v1.2.0).

## 1. Intention

Aujourd'hui `domain/enums.Language` n'a que `FR`/`EN`. Toute l'UI dérive les
langues proposées de `tuple(Language)` (sélecteur Génération, cases Pédagogie,
langue de réponse du Dialogue, boucles d'export), donc **ajouter des valeurs à
l'enum les propage presque partout automatiquement**. Le travail restant est de
compléter les **tables de libellés**, les **en-têtes de glossaire**, les **alias
de détection STT**, de **fiabiliser le rendu PDF** pour le chinois (CJK) et
l'arabe (RTL), et d'ajouter le **format DOCX**.

Principe directeur : **réutiliser les mécanismes existants** (enum → propagation),
**centraliser** ce qui est dupliqué (libellés de langue), n'introduire **aucune
fragilité** (pas de monkeypatch d'une lib tierce, pas de police bundlée) — la
solution PDF retenue n'utilise que des **APIs supportées** et des **polices
système Windows**.

## 2. Périmètre des langues

Ajout de 5 valeurs à `Language` (`StrEnum`, `domain/enums.py`), après `EN` pour
conserver `FR` comme défaut d'affichage et d'ordre :

```python
class Language(StrEnum):
    FR = "fr"
    EN = "en"
    DE = "de"
    ES = "es"
    IT = "it"
    ZH = "zh"
    AR = "ar"
```

- **Aucune migration** : `Language` est un `StrEnum` stocké par **code** dans les
  blobs (`projects.settings_json`, conversations, manifeste pédagogie). Les
  `"fr"`/`"en"` existants restent valides ; les 5 nouvelles deviennent simplement
  sélectionnables.
- **Trois fonctionnalités** : les 5 langues s'appliquent identiquement à la
  Génération (langues produites + principale/source), à la Pédagogie (langues
  cibles), au Dialogue (langue de réponse). Aucune restriction par fonctionnalité.

### 2.1 Validation des limitations techniques (vérifiée)

| Brique | de | es | it | zh | ar | Conclusion |
|--------|----|----|----|----|----|------------|
| STT local `faster-whisper` | ✓ | ✓ | ✓ | ✓ | ✓ | Multilingue (indice = `source_language`) |
| STT cloud OpenAI Whisper / `gpt-4o-*-transcribe` | ✓ | ✓ | ✓ | ✓ | ✓ | Multilingue |
| Embeddings OpenAI `text-embedding-3` | ✓ | ✓ | ✓ | ✓ | ✓ | Multilingue (Dialogue sémantique) |
| LLM DeepSeek (prompts agnostiques via libellé) | ✓ | ✓ | ✓ | ✓ | ✓ | Qualité variable mais fonctionnelle |
| Export Markdown / HTML | ✓ | ✓ | ✓ | ✓ | ✓ | UTF-8 ; HTML = repli de police navigateur |
| Export PDF | ✓ | ✓ | ✓ | **§5** | **§5** | Latin gratuit ; zh/ar = travail dédié (validé) |
| Export DOCX | ✓ | ✓ | ✓ | ✓ | ✓ | Word gère CJK/bidi nativement (§6) |
| Retrieval **lexical** (TF-IDF) | ✓ | ✓ | ✓ | **dégradé** | ✓ | §7 (mitigation `AUTO`→sémantique) |

Aucun blocage de traitement. Les deux seuls points durs sont **circonscrits au
rendu PDF zh/ar** (§5) et à la **recherche lexicale chinoise** (§7, mitigée).

## 3. Centralisation des libellés de langue (DRY)

Aujourd'hui le **nom de langue** est dupliqué dans 4 endroits, ce qui invite à la
dérive en passant de 2 à 7 langues :

- `pipeline/handlers/_base.py` (`_LANGUAGE_LABELS_FR`, minuscule : « français »)
- `pedagogy/labels.py` (`_LANGUAGE_LABELS_FR`, minuscule, identique)
- `ui/widgets/language_selection_view.py` (`_LANGUAGE_LABELS`, capitalisé : « Français »)
- `ui/dialogs/pedagogy_settings_view.py` : affiche **le code brut** `lang.value`
  (« fr ») — incohérence à corriger.

**Décision** : source unique dans le domaine. **Nouveau module**
`domain/languages.py` (importe `Language` ; n'introduit aucune dépendance Qt/HTTP,
conforme aux contraintes de couche) :

```python
#: Nom humain (minuscule) par langue — source unique de vérité.
_LANGUAGE_NAMES: dict[Language, str] = {
    Language.FR: "français", Language.EN: "anglais", Language.DE: "allemand",
    Language.ES: "espagnol", Language.IT: "italien", Language.ZH: "chinois",
    Language.AR: "arabe",
}

def language_label(language: Language) -> str:       # prompts (minuscule)
    return _LANGUAGE_NAMES[language]

def language_display_label(language: Language) -> str:  # UI (capitalisé)
    return _LANGUAGE_NAMES[language].capitalize()
```

- `pipeline/handlers/_base.language_label` et `pedagogy/labels.language_label`
  **délèguent** à cette source (compat d'API conservée : les handlers/générateurs
  continuent d'importer `language_label` depuis leur module habituel, qui ré-exporte).
- `ui/widgets/language_selection_view` et `ui/dialogs/pedagogy_settings_view`
  consomment `language_display_label` (fini le code brut côté pédagogie).
- Le domaine n'imposant pas de connaître les libellés UI ailleurs, on garde la
  séparation : `language_label` (fond, prompts) vs `language_display_label`
  (présentation). Les **en-têtes de glossaire** (§4) restent une table dédiée
  (donnée distincte : 4 traductions de colonnes), pas un simple libellé.

## 4. Glossaire — en-têtes traduits

`domain/glossary.py` : compléter `_HEADERS_BY_LANGUAGE` (tuple
`(Terme, Acronyme, Signification, Définition)`) pour DE/ES/IT/ZH/AR. Le repli
actuel sur l'anglais ne concernera plus ces langues. Traductions à valider
(qualité native, cf. règle d'orthographe parfaite étendue aux autres langues) :

| Langue | Terme | Acronyme | Signification | Définition |
|--------|-------|----------|---------------|------------|
| de | Begriff | Akronym | Bedeutung | Definition |
| es | Término | Acrónimo | Significado | Definición |
| it | Termine | Acronimo | Significato | Definizione |
| zh | 术语 | 缩写 | 含义 | 定义 |
| ar | المصطلح | الاختصار | المعنى | التعريف |

## 5. Export PDF — chinois (CJK) + arabe (RTL)

### 5.1 Constat (vérifié par spikes sur le venv réel)

Le renderer actuel (`infra/export/markdown_pdf.py`) enregistre Arial via
`pdfmetrics.registerFont` + `addMapping` et pose `font-family: "AppSans"`. **Ce
mécanisme est ignoré par xhtml2pdf** : le PDF est en réalité rendu en **Helvetica
intégrée**. Cela « marche » pour FR/EN **uniquement parce que Helvetica couvre le
Latin-1** — donc **de/es/it passent aussi gratuitement**. En revanche, le chinois
et l'arabe sortent en carrés `■`.

Pistes écartées (mesurées) :
- `@font-face` avec une police CJK système (`.ttc`) → `TTFError` (xhtml2pdf ne
  passe pas `subfontIndex`).
- `@font-face` avec un `.ttf` (y compris en `data:` URI) → `PermissionError`
  Windows (xhtml2pdf copie la police dans un `NamedTemporaryFile(delete=True)`
  gardé ouvert, que ReportLab ne peut rouvrir par nom). Bug confirmé, sandbox ou
  non. **Ne pas emprunter cette voie** (imposerait un monkeypatch fragile).

### 5.2 Solution retenue (validée empiriquement, sans patch ni bundle)

xhtml2pdf résout `font-family` via `xhtml2pdf.context.getFontName`, qui consulte
`context.fontList` — une **copie de `xhtml2pdf.default.DEFAULT_FONT`** (dict
`nom-de-famille-minuscule → nom de police ReportLab enregistrée`). D'où :

1. **Enregistrer les polices avec ReportLab** (API supportée, **pas** de fichier
   temporaire, **pas** de monkeypatch) :
   - Chinois : `pdfmetrics.registerFont(TTFont("CJKReg", <Fonts>/msyh.ttc,
     subfontIndex=0))` — `subfontIndex` gère la **TrueType Collection** système
     **Microsoft YaHei**. Variante grasse via `msyhbd.ttc` (titres) +
     `addMapping`.
   - Arabe : `pdfmetrics.registerFont(TTFont("ArReg", <Fonts>/arial.ttf))` —
     `arial.ttf` (TTF simple, **contient les glyphes arabes**) ; + variantes
     `arialbd/ariali/arialbi` (déjà connues du module).
2. **Injecter dans la table de résolution** une seule fois, idempotent, mémoïsé
   (à la manière de `_ensure_pdf_fonts_registered`) :
   `xhtml2pdf.default.DEFAULT_FONT["cjk"] = "CJKReg"` ;
   `DEFAULT_FONT["arab"] = "ArReg"`. (C'est le **point d'injection standard** :
   `pisa.CreatePDF` n'expose pas de hook de registre ; mutation **additive**,
   bien moins invasive qu'un patch de méthode.)
3. **Sélection police + direction par langue** dans le gabarit PDF
   (`_PDF_HTML_TEMPLATE`) :
   - Latin (fr/en/de/es/it) : inchangé (Helvetica).
   - Chinois : `body { font-family: cjk; }` (YaHei couvre aussi le latin → texte
     mixte OK, vérifié).
   - Arabe : `body { font-family: arab; }` + `direction: rtl` + le tag **officiel**
     xhtml2pdf `<pdf:language name="arabic"/>` en tête de corps → déclenche
     `arabic_reshaper` + `python-bidi` (déjà présents, transitifs xhtml2pdf) →
     **mise en forme contextuelle (lettres liées) + bidi**.

### 5.3 Câblage

- `app/document_export.ExportDocument` reçoit un champ `language: Language` (les
  collecteurs `generation_export`/`pedagogy_export` itèrent déjà par langue, ils
  le renseignent).
- `infra/export/markdown_pdf.render_markdown_to_pdf(..., language: Language)` :
  enregistre les polices nécessaires (mémoïsé), choisit `font-family`/`direction`/
  `pdf:language` selon la langue. `render_markdown_to_html` reçoit aussi la langue
  pour poser `lang`/`dir` (aujourd'hui `lang="fr"` est en dur).
- Garde : étendre `pdf_fonts_available()` (et/ou ajouter `cjk_font_available()`)
  pour lever une `ConfigError` claire (`EXPORT.NO_CJK_FONT`) si Microsoft YaHei est
  introuvable, plutôt que des carrés silencieux.

### 5.4 Preuves (spikes)

- Chinois : `MicrosoftYaHei-0` **embarqué** (sous-ensemble), `机器学习` rendu,
  `pisa.err == 0`. Latin coexiste dans le même PDF.
- Arabe : `ArialMT` **embarqué**, texte extrait en **formes de présentation**
  `U+FE70–U+FEFF` (= lettres **liées**, shaping appliqué) + ordre bidi.
- **Limite de la preuve** : embarquement + shaping prouvés par extraction de texte
  et codepoints, **pas** par capture d'écran. Une vérification visuelle (rendu
  rasterisé) reste une étape d'acceptation à l'implémentation.

### 5.5 Réserves assumées

- **Dépendance polices système Windows** (`msyh.ttc`, `arial.ttf`) : présentes par
  défaut sous Win10/11 ; l'app est Windows-only. Couverte par la garde §5.3.
- **Gras CJK** : enregistrer `msyhbd.ttc` pour un vrai gras (sinon gras synthétique).
- Mutation de `DEFAULT_FONT` : une fois, idempotente, **documentée** (pourquoi :
  absence de hook de registre dans `pisa.CreatePDF`).

## 6. Export DOCX (nouveau format)

### 6.1 Modèle

- `domain/enums.ExportFormat` : ajout `DOCX = "docx"`.
- `infra/export/markdown_pdf.EXTENSION_BY_FORMAT[DOCX] = ".docx"`.
- `domain/generation.GENERATION_EXPORT_FORMATS` : ajout `DOCX` (format
  documentaire, comme MD/PDF/HTML — pas d'APKG en génération). Côté pédagogie,
  `pedagogy_settings_view` itère **tous** les `ExportFormat` → DOCX apparaît
  automatiquement.
- `ui/pedagogy_labels.EXPORT_LABELS[DOCX] = "Word (.docx)"` (consommé par les deux
  features via `_export_ui.choose_export_format`).

### 6.2 Renderer

Nouveau module **`infra/export/markdown_docx.py`** (garde `markdown_pdf` focalisé) :
`render_markdown_to_docx(markdown_text, output_path)` =
**Markdown → HTML** (réutilise le rendu existant, mêmes extensions `tables`/`toc`)
**→ `htmldocx.HtmlToDocx().add_html_to_document(body, Document())` → `.docx`**.
Dispatch ajouté dans `app/document_export.write_documents` (branche `DOCX`).

Validé (spike) : htmldocx 0.0.6 produit titres Word, gras/italique, **vrais
tableaux** (`<w:tbl>`), listes, liens, et le texte **chinois** comme **arabe**
(Word applique la bidi nativement à l'affichage).

### 6.3 Dépendances & packaging

- `pyproject.toml` : ajouter `htmldocx` + `beautifulsoup4` (roues **pure-python**).
  `python-docx` est déjà présent (ingestion .docx) et tire déjà **lxml** → pas de
  nouvelle dépendance native.
- `packaging/fahmi2.spec` (gitignored) : `collect_submodules`/`collect_data_files`
  pour `bs4`/`htmldocx` si l'analyse d'imports ne suffit pas ; vérifier que
  `arabic_reshaper`/`python-bidi` (déjà collectés via xhtml2pdf) restent présents.

### 6.4 Réserves assumées

- **htmldocx 0.0.6** : lib jeune mais minuscule (un module) et validée sur notre
  contenu. **Repli documenté** : un renderer Markdown→DOCX maison sur python-docx
  si un écart de fidélité bloquant apparaît.
- Les **largeurs de colonnes** du glossaire (`pdf_column_widths`) sont
  **spécifiques au PDF** ; en DOCX le tableau prend la mise en page Word par
  défaut (acceptable).
- **Arabe en DOCX** : texte correct (bidi Word) ; l'alignement/direction RTL du
  paragraphe est **best-effort** (option `w:bidi` via python-docx en polissage
  ultérieur si besoin).

## 7. Dialogue — recherche lexicale en chinois (limitation documentée)

Le retrieval **lexical** (`core/retrieval`, TF-IDF) tokenise avec `\b\w+\b`.
Pour l'**arabe** cela fonctionne (mots séparés par des espaces) ; pour le
**chinois** (sans espaces), un segment entier devient un seul token → recherche
lexicale **dégradée**.

**Décision (YAGNI)** : on **ne** ajoute **pas** de tokenizer CJK (n-grammes
caractères). Mitigation existante suffisante : le mode `AUTO` (défaut du Dialogue)
route vers le **sémantique** (embeddings, excellents en chinois cross-lingue) dès
qu'une clé OpenAI est présente — le cas usuel. On **documente** la limitation
(README + aide UI du Dialogue) : pour le chinois, privilégier le mode sémantique.
Réouvrable ultérieurement sans refonte (le tokenizer est un point unique).

## 8. Coût

Aucun changement. `CostEstimator`/`PedagogyCostEstimator` raisonnent en **nombres**
de langues (`target_languages_count`, `translation_languages_count`) et les tarifs
STT/embedding/LLM sont **par minute/token**, indépendants de la langue.

## 9. Découpage des changements (par couche)

| Couche | Fichier(s) | Changement |
|--------|-----------|------------|
| domain | `enums.py` | +5 valeurs `Language` ; +`ExportFormat.DOCX` |
| domain | `languages.py` (nouveau) | source unique des libellés + `language_label`/`language_display_label` |
| domain | `glossary.py` | en-têtes DE/ES/IT/ZH/AR |
| domain | `generation.py` | `GENERATION_EXPORT_FORMATS` += DOCX |
| pipeline | `handlers/_base.py` | `language_label` délègue à `domain/languages` |
| pedagogy | `labels.py` | idem délégation |
| infra | `stt/openai_whisper_adapter.py` | alias Whisper (noms + codes) ×5 |
| infra | `export/markdown_pdf.py` | enregistrement polices (TTC subfontIndex) + injection `DEFAULT_FONT` + `font-family`/`direction`/`pdf:language` par langue + garde CJK ; `render_*` reçoivent `language` |
| infra | `export/markdown_docx.py` (nouveau) | renderer Markdown→HTML→htmldocx |
| app | `document_export.py` | `ExportDocument.language` ; dispatch `DOCX` |
| app | `generation_export.py`, `pedagogy_export.py` | renseignent `language` |
| ui | `pedagogy_labels.py` | `EXPORT_LABELS[DOCX]` |
| ui | `language_selection_view.py`, `pedagogy_settings_view.py` | `language_display_label` |
| packaging | `pyproject.toml`, `fahmi2.spec` | htmldocx + beautifulsoup4 ; vérif collecte |

## 10. Tests

- `domain` : enum (7 langues, codes), `language_label`/`language_display_label`,
  en-têtes glossaire par langue, `ExportFormat.DOCX` documentaire.
- `infra/stt` : mapping des alias Whisper (noms anglais + codes ISO) ×5.
- `infra/export` :
  - **PDF zh** : assert police CJK **embarquée** + caractères chinois présents
    (extraction) ; garde `EXPORT.NO_CJK_FONT` si police absente (monkeypatch du
    chemin de fonts dans le test).
  - **PDF ar** : assert présence de formes de présentation `U+FE70–U+FEFF`
    (shaping) après rendu.
  - **DOCX** : assert `<w:tbl>`, titre, gras, texte zh/ar présents dans
    `word/document.xml`.
- `app` : `write_documents` route `DOCX` ; `ExportDocument.language` propagé.
- `ui` : smoke des vues réglages avec 7 langues ; libellés capitalisés (pas de
  code brut en pédagogie).
- Repasses obligatoires : `pytest`, `ruff check .`, `mypy src tests` verts.

## 11. Documentation à mettre à jour

- `CLAUDE.md` : langues gérées (FR/EN → +de/es/it/zh/ar), `ExportFormat` (+DOCX),
  note rendu PDF CJK/RTL (polices système + `DEFAULT_FONT` + `pdf:language`),
  limitation lexicale chinoise du Dialogue.
- `README.md` : tableau des langues/exports ; recommandation sémantique pour le
  chinois.
- `packaging/README.md` : dépendances DOCX (htmldocx/bs4) ; rappel polices système
  CJK/Arial (rien à bundler).

## 12. Hors périmètre (explicite)

- Tokenizer CJK pour le retrieval lexical (§7) — réouvrable sans refonte.
- Interface utilisateur **elle-même** en RTL (l'app reste LTR ; seul le **contenu**
  arabe des livrables est RTL).
- Alignement RTL fin du paragraphe DOCX (`w:bidi`) — polissage ultérieur.
- Langues hors des 5 demandées.
