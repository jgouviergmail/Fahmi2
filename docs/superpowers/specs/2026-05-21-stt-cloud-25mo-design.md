# STT cloud — franchir la limite des 25 Mo d'OpenAI Whisper (design détaillé)

- **Date** : 2026-05-21
- **Statut** : design (à valider)
- **Contexte** : un utilisateur **sans GPU** est contraint d'utiliser le STT
  **cloud** (OpenAI Whisper). Or l'API plafonne chaque fichier à **25 Mo**, alors
  qu'un WAV 16 kHz mono fait **~115 Mo/heure** : toute vidéo de cours réelle
  dépasse la limite. Sans traitement, le STT cloud est inutilisable en production.
- **Prérequis** : le bug de parsing de langue (`"french"` → `ValueError`) est déjà
  corrigé (`fix(stt): mappe la langue Whisper cloud`).

## 1. Objectif & portée

Rendre le STT cloud fonctionnel pour **toute durée** de cours, en s'appuyant sur
les bonnes pratiques documentées (compression + découpage). La solution :

- **compresse** l'audio en **Opus ~24 kbps mono** (≈ 2 h 18 dans 25 Mo) ;
- **découpe aux silences** uniquement si le résultat dépasse encore la limite
  (cours > ~2 h) ;
- **recolle** les transcriptions des segments (offsets temporels) en une seule
  `Transcription`.

**Hors périmètre** : le STT **local** (faster-whisper) reste **inchangé** (pas de
limite locale, WAV optimal pour ctranslate2) ; pas de denoise / normalisation /
suppression des silences du contenu (bonnes pratiques mentionnées mais non
demandées — YAGNI).

## 2. Décisions verrouillées

1. **Compression Opus + découpage aux silences si besoin** (robuste toute durée).
2. **Format Opus** (conteneur `.ogg`), ~24 kbps mono, `-application voip`.
3. **Découpage aux silences** (`ffmpeg silencedetect`), avec coupe « dure » de
   repli si aucun silence exploitable près de la cible (garantit ≤ limite).
4. **Préparateur audio dédié injecté** dans l'adapter cloud (le contrat
   `STTProvider.transcribe(fichier)` et la phase 0 ne changent pas).
5. **libopus garanti au packaging** (vérification au build, pas de fallback
   runtime).
6. **Timeout client OpenAI explicite** (cohérence avec le `DeepSeekAdapter`).

## 3. Composant `CloudAudioPreparer` (`infra/audio/cloud_audio_preparer.py`)

Responsabilité unique : transformer un WAV en **1+ fichiers Opus ≤ limite** avec
leurs offsets temporels. Réutilise les patterns de `FFmpegExtractor` (subprocess
`ffmpeg`/`ffprobe`, `FFmpegError`).

```python
@dataclass(frozen=True)
class AudioChunk:
    """Un segment audio prêt pour le STT cloud.

    Attributes:
        path: Fichier Opus (≤ ``max_chunk_bytes``).
        offset_seconds: Décalage temporel du segment dans l'audio d'origine.
    """
    path: Path
    offset_seconds: float


class CloudAudioPreparer:
    def __init__(
        self, *,
        ffmpeg_binary: str | None = None,
        ffprobe_binary: str | None = None,
        bitrate_kbps: int = _OPUS_BITRATE_KBPS,
        max_chunk_bytes: int = _MAX_CHUNK_BYTES,
        silence_noise_db: int = _SILENCE_NOISE_DB,
        silence_min_seconds: float = _SILENCE_MIN_SECONDS,
    ) -> None: ...

    def prepare(self, wav_path: Path, work_dir: Path) -> list[AudioChunk]:
        """Transcode en Opus ; découpe aux silences si > limite.

        Returns:
            Liste ordonnée d'``AudioChunk`` (offsets croissants). Au moins un.

        Raises:
            FFmpegError: transcodage/découpage échoué, ou encodeur ``libopus``
                indisponible (``FFMPEG.OPUS_UNAVAILABLE``).
        """
```

Algorithme de `prepare` :

1. **Transcoder** `wav → work_dir/full.ogg` (`-c:a libopus -b:a 24k -ac 1
   -application voip`). Si l'échec ffmpeg indique un encodeur inconnu → lever
   `FFMPEG.OPUS_UNAVAILABLE` (message clair).
2. Si `taille(full.ogg) ≤ max_chunk_bytes` → `[AudioChunk(full.ogg, 0.0)]`.
3. Sinon **découper** :
   a. Durée totale `T` (ffprobe) ; `n = ceil(taille / max_chunk_bytes)` ;
      durée cible `target = T / n`.
   b. `silencedetect` sur le WAV → liste des **milieux de silence** (timestamps).
   c. Construire les bornes : pour chaque frontière visée `k·target`
      (k = 1..n-1), choisir le milieu de silence le plus proche **dans une
      fenêtre** `±(target/2)` ; si aucun → couper à `k·target` (coupe dure).
      Garantir que chaque tranche reste sous la limite (re-découper si une
      tranche dépasse, par sécurité).
   d. Pour chaque tranche `[start, end]` : ré-encoder **depuis le WAV**
      (`-ss start -to end -c:a libopus …`) → `AudioChunk(opus_i, start)`.

> Découpe depuis le WAV (ré-encodage), pas depuis l'Opus : timestamps précis,
> pas de dépendance aux keyframes.

## 4. Adapter OpenAI : multi-segments + recollage

`OpenAIWhisperAdapter` :

- `__init__(..., preparer: CloudAudioPreparer | None = None, timeout: float =
  _REQUEST_TIMEOUT_SECONDS)`. `preparer=None` → comportement direct (un fichier),
  utile pour les tests et l'injection.
- `transcribe(wav, language_hint, on_progress)` :
  1. Crée un **répertoire temporaire** (`tempfile.mkdtemp`), nettoyé en `finally`.
  2. `chunks = preparer.prepare(wav, tmp)` (ou `[wav@0.0]` si pas de préparateur).
  3. Pour chaque `chunk` (index i / n) : appel `audio.transcriptions.create`,
     `_parse_verbose_response(..., fallback=language_hint)`, puis **décalage** des
     segments : `start/end += chunk.offset_seconds`. `on_progress((i+1)/n)`.
  4. Agrège : segments concaténés (ordre des chunks), `detected_language` = celle
     du **1er** chunk, `duration_seconds` = `max(end_seconds)` (ou durée sonde).
- Mapping d'erreurs `STTError` inchangé ; client `OpenAI(timeout=…)` explicite.

`estimate_cost(duration_seconds)` inchangé (fonction de la durée, pas de la taille).

## 5. Garantie libopus au packaging (`packaging/fetch-ffmpeg.ps1`)

Après copie des binaires, vérifier que l'encodeur est présent :

```powershell
$encoders = & $ffmpegExe -hide_banner -encoders 2>$null
if ($encoders -notmatch 'libopus') {
    Write-Error "ffmpeg bundle sans libopus : encodeur requis pour le STT cloud."
}
```

Fail-fast au build (au même titre que la vérification SHA256). Aucune branche de
fallback dans le code applicatif.

## 6. Constantes (`infra/audio/cloud_audio_preparer.py`)

- `_OPUS_BITRATE_KBPS = 24`
- `_MAX_CHUNK_BYTES = 24_000_000` (marge sous 25 Mo : overhead conteneur)
- `_SILENCE_NOISE_DB = -30`
- `_SILENCE_MIN_SECONDS = 0.5`
- `_OPUS_CONTAINER_SUFFIX = ".ogg"`, `_OPUS_APPLICATION = "voip"`

Aucune valeur en dur dans la logique.

## 7. Tests

- **`CloudAudioPreparer`** (tests d'intégration ffmpeg réel, comme
  `test_faster_whisper`/phase 0 utilisent ffmpeg) :
  - petit WAV généré → **1 chunk** Opus, taille < limite, offset 0 ;
  - `max_chunk_bytes` **abaissé** artificiellement → **N chunks**, offsets
    strictement croissants, chacun ≤ limite, somme des durées ≈ durée totale ;
  - `FFMPEG.OPUS_UNAVAILABLE` simulé via binaire ffmpeg inexistant /
    `_resolve`-style (ou un `silencedetect` parsé depuis une sortie capturée en
    test unitaire pur).
- **Adapter** (sans réseau) : **préparateur fake** renvoyant 2 chunks (offsets
  0.0 et 60.0) + 2 réponses OpenAI mockées → vérifier le **recollage**
  (timestamps décalés, concaténation ordonnée, langue du 1er chunk). Les tests
  existants passent (préparateur `None` = chemin direct).
- `pytest`, `ruff check .`, `mypy src tests` verts.

## 8. Découpage des responsabilités (fichiers)

| Fichier | Rôle | Action |
|---|---|---|
| `infra/audio/cloud_audio_preparer.py` | `AudioChunk` + `CloudAudioPreparer` | Créer |
| `infra/stt/openai_whisper_adapter.py` | préparateur injecté + recollage + timeout | Modifier |
| `ui/generation_controller.py` (DI) | injecter `CloudAudioPreparer` dans l'adapter cloud | Modifier |
| `packaging/fetch-ffmpeg.ps1` | vérification libopus | Modifier |
| `tests/unit/infra/audio/test_cloud_audio_preparer.py` | tests préparateur | Créer |
| `tests/unit/infra/stt/test_openai_whisper_adapter.py` | recollage multi-chunk | Modifier |
| docs (`02`, `04`, `CHANGELOG`) | STT cloud gros fichiers | Modifier |

## 9. Limites connues (assumées)

- Le découpage **ré-encode** les tranches → léger surcoût CPU local (rare :
  seulement > ~2 h). Acceptable.
- Coupe « dure » si aucun silence près de la cible (parole continue > 2 h) :
  artefact mineur à une frontière, atténué par la reformulation LLM en aval.
- Les segments d'**une** vidéo sont transcrits **séquentiellement** dans l'adapter
  (pas de pool imbriqué — les vidéos sont déjà parallélisées entre elles par la
  phase 0). Le cas (cours > 2 h) est rare ; YAGNI sur un 2e niveau de pool.
