# PronouncedFish engine

A small Python package that runs the pretrained Pasketti phonetic model locally.
It accepts WAV/FLAC audio and returns IPA plus complete phone tokens. Recognition
accuracy is inherited from Pasketti; we have not trained or fine-tuned it.
An optional analysis module compares those tokens against supplied target
pronunciations and returns candidate differences and phonological feature distances.
An experimental acoustic scorer additionally compares CTC sequence probabilities
from the recording. It is separate from symbolic PanPhon distances and remains
uncalibrated; it does not detect distortions or predict acoustic feature vectors.

## Run it

From `src/engine/`:

```powershell
conda activate phoneme-engine
python -m pip install -e ".[dev,analysis]"
python -m pronouncedfish_engine download-model
.\scripts\New-SmokeAudio.ps1
python -m pronouncedfish_engine recognize sample.wav
```

The sample generator uses the installed Windows Microsoft David Desktop voice.
For your own permitted development recording, replace `sample.wav` with its path.
Existing model files in `models/pasketti-phonetic/` are reused without downloading.
For a fresh environment: `conda env create -f environment.yml`, then activate it.
Python 3.9-3.12 is supported by the current dependency pins; conda uses 3.12.
Use `pip install -e .` if you only need recognition, without the test dependencies.

## What is here, and why

```text
engine/
  pronouncedfish_engine/    The working Python package
    pasketti.py             Load Pasketti once, run local inference, decode CTC
    audio.py                Read, validate, mix channels, and resample audio
    phonetics.py            Group IPA marks into complete phone tokens
    analysis.py             Align target/recognized phones and compare features
    assessment.py           CTC evidence, experimental scoring, and model boundary
    assets.py               Download and verify a reproducible model snapshot
    recognition.py          AudioInput and RecognitionResult used by the code
    cli.py                  download-model, recognize, analyze, and assess commands
  tests/                    Regression checks and an optional real-model test
  scripts/                  One Windows synthetic-sample generator
  docs/                     Model notes, recorded checks, and team walkthrough
  models/                   Downloaded assets, ignored by Git
  pyproject.toml            Package metadata and dependency pins
  environment.yml           Conda setup; installs this package with test tools
```

There is no browser package or plugin framework. The small EvidenceRecognizer
boundary is used by acoustic assessment and can accept a future model adapter.
The model assets are required by Pasketti; their configuration and tokenizer JSON
files are downloaded upstream files, not extra application architecture.

## Use it from Python

```python
from pronouncedfish_engine import PaskettiRecognizer, load_audio

recognizer = PaskettiRecognizer("models/pasketti-phonetic")
result = recognizer.recognize(load_audio("sample.wav"))
```

Keep `recognizer` alive between attempts to avoid reloading the large model.
Audio must be nonempty WAV/FLAC, at most 30 seconds. `load_audio` prepares mono
16 kHz PCM. Recognition takes no expected word and makes no audio network request.
The CLI prints JSON and timing; the library does not log recordings. Interactive
output displays IPA. Redirected JSON escapes non-ASCII characters to preserve
them through Windows PowerShell's encoding conversions; JSON readers restore IPA.
`status="ok"` means parseable output, not proven correctness. All results require
review; confidence has not been calibrated. Noise and clipping detection remain
limited. Exit codes: 0 = phones returned, 2 = unassessable, 1 = execution error.

## Compare against a practice target

Install `python -m pip install -e ".[analysis]"` in an existing recognition-only
environment. Jiwer 4.0.0 aligns complete phone tokens; PanPhon 0.22.2 supplies
phonological feature data. Analysis needs no model weights or network connection.

```python
from pronouncedfish_engine import analyze

# `result` is the unchanged output of recognizer.recognize(...).
# Supply a pronunciation selected for the practice item by your team/SLP.
comparison = analyze(
    result,
    expected_phones=["ð", "ə", "ɹ", "æ", "b", "ɪ", "t", "s", "ɪ", "t", "s",
                     "ɪ", "n", "ð", "ə", "s", "ʌ", "n"],
    acceptable_variants=[],
    supported_substitutions=[],
)
```

For a small example, recognized `["d"]` against expected `["t"]` returns one
candidate substitution. Its feature comparison has Manhattan distance 2, entirely
in the `voi` (voicing) column. This is descriptive feature distance, not severity.

The CLI also accepts saved recognition JSON in UTF-8, UTF-16, or UTF-32,
including the UTF-16 output written by Windows PowerShell redirection. Supply
`--expected-phones` so analysis knows which target to compare against. From PowerShell:

```powershell
python -m pronouncedfish_engine recognize sample.wav > recognition.json
python -m pronouncedfish_engine analyze recognition.json --expected-phones ð ə ɹ æ b ɪ t s ɪ t s ɪ n ð ə s ʌ n
# Optional flags, each repeatable:
# --acceptable-variant k ɑ t
# --supported-substitution t d
```

`--acceptable-variant` supplies another complete pronunciation. The first example
uses the synthetic sample's known sentence, not an automatically generated target.
The caller must supply the target and approved variants; there is no word-to-IPA
dictionary or clinical substitution inventory built into this module.

Output is JSON-compatible and includes:

- `selected_variant_index`: target is 0, followed by acceptable variants in order.
  Selection minimizes unit-cost phone edits; ties prefer the first variant.
- `matches_target`: whether the selected variant matches after spelling
  normalization. This does not establish acoustic correctness.
- `edit_counts`: candidate substitutions, omissions, and additions.
- `alignment`: individual phone pairs or gaps, with zero-based indices into the
  selected variant and original recognized tokens. Minimum-edit alignments can be
  ambiguous; the returned explanation is not a clinical finding.
- `supported_substitution`: whether a substitution belongs to the supplied
  directional `(expected, recognized)` inventory. Defaults to false for all
  substitutions until an approved inventory is provided; it is not validation.
- `feature_names` and each row's `feature_comparison`: target/recognized vectors,
  per-feature absolute differences, and their sum (Manhattan distance). The
  standalone frontend plots alignment rows against feature columns as a heatmap.

Features use PanPhon's `-1`, `0`, `+1` values; `0` is a feature specification, not
missing data. Gaps have `feature_status="not_applicable"` and no distance. Phones
absent from the feature table have `feature_status="unavailable"` and no distance;
they are never silently dropped, split, or assigned zero distance. We read the
packaged CSV as UTF-8 to avoid PanPhon's Windows default-encoding issue.

NFD Unicode normalization and spelling aliases `g` → `ɡ`, `ʧ` → `t͡ʃ`, and
`ʤ` → `d͡ʒ` apply only during comparison. Original input spellings remain in the
output. Nasalization, length, and the distinction between `r` and `ɹ` are preserved.
Inputs must already be complete phone tokens, not raw IPA strings or words.

An unassessable recognition or empty recognized sequence returns unassessable
analysis with no inferred omissions. All results require review.
`distortion_status="not_assessed"`: two acoustically different productions can
receive the same IPA symbol and therefore the same feature vector. This layer
does not detect acoustic distortions or supply calibrated confidence, diagnostic
labels, clinical severity, or validated child-production accuracy.

The [official Pasketti demo](https://colab.research.google.com/drive/1Gj64XMfPThMuqCw1YD2CaYWLW6kg8hAH)
also uses Jiwer, but compares model transcription against human transcription of
the recording. Its yellow/red/green colors describe model substitutions, missed
sounds, and extra sounds. Our comparison uses the supplied practice pronunciation.
See [Jiwer's alignment documentation](https://jitsi.github.io/jiwer/usage/) and
[PanPhon](https://github.com/dmort27/panphon) for the reused tools/data. In research,
cite [Mortensen et al. (2016)](https://aclanthology.org/C16-1328/).

## Result contracts

Recognition and analysis return separate JSON-compatible dictionaries. The CLI
prints one result per invocation; a file is created when you redirect that output.
Analysis does not overwrite or attach itself to the recognition dictionary.

### Recognition fields

| Field | Type / current meaning |
| --- | --- |
| `status` | `"ok"` or `"unassessable"`; successful parsing does not establish accuracy. |
| `recognized_phones` | Array of complete phone tokens in recognized order. |
| `phonetic_transcription` | Raw decoded IPA string, retaining predicted word spacing. |
| `model_version` | Model ID plus pinned revision. |
| `inference_time_ms` | Neural-network forward-pass duration, or `null` if inference did not run. |
| `confidence_status` | Currently `"uncalibrated"` after inference or `"unavailable"` without inference. The declared type also allows `"calibrated"`, but the baseline never emits it. |
| `requires_review` | Currently always `true`. |
| `review_reason` | Review explanation; the declared type allows `null`, but the baseline supplies a reason. |

### Analysis fields

| Field | Type / current meaning |
| --- | --- |
| `status` | `"ok"` or `"unassessable"`. |
| `expected_phones` | Original primary target token array supplied by the caller. |
| `selected_variant_index` | Integer: primary target is 0; supplied variants follow in order. `null` if unassessable. |
| `selected_expected_phones` | Target/variant actually used for alignment; `null` if unassessable. |
| `matches_target` | Boolean token-match result after spelling normalization; `null` if unassessable. |
| `edit_counts` | Object with integer `substitutions`, `omissions`, and `additions`; `null` if unassessable. |
| `alignment` | Array of phone-pair/gap objects; empty if unassessable. |
| `feature_names` | Ordered names for the positions in feature vectors; 24 when assessable, empty if unassessable. |
| `feature_source` | `"panphon==0.22.2/spe+"`. |
| `distortion_status` | Always `"not_assessed"`. |
| `requires_review` | Always `true`. |
| `review_reason` | Explanation of candidate interpretation or unassessability. |

Every `alignment` entry contains these fields:

| Field | Meaning |
| --- | --- |
| `kind` | `"match"`, `"substitution"`, `"omission"`, or `"addition"`. |
| `expected_index` | Zero-based index into `selected_expected_phones`; `null` for an addition. |
| `recognized_index` | Zero-based index into the original recognized sequence; `null` for an omission. |
| `expected_phone` | Target token, or `null` for an addition. |
| `recognized_phone` | Recognized token, or `null` for an omission. |
| `supported_substitution` | For substitutions, membership in the supplied directional inventory; otherwise `null`. |
| `feature_status` | `"available"`, `"unavailable"` for an unknown exact mapping, or `"not_applicable"` for a gap. |
| `feature_comparison` | Object described below, or `null` when no distance can be calculated. |

`feature_comparison` contains `expected_vector`, `recognized_vector`,
`absolute_differences`, and `manhattan_distance`. The three arrays correspond
position-for-position with `feature_names`; the distance sums absolute differences.
Vector values are `-1`, `0`, or `+1`; differences are `0`, `1`, or `2`.

The output contains no recording, patient/session ID, validated phone timestamp,
numerical confidence probability, or clinical severity score. `model_load_ms`,
`preprocessing_ms`, and `processing_ms` are recognition CLI stderr diagnostics,
not JSON fields. `processing_ms` includes preprocessing and inference; do not add
those timings again when calculating initialization plus processing.

An application may explicitly keep both results together:

```python
response = {"recognition": result, "analysis": comparison}
```

That two-result wrapper is an integration choice, not an HTTP endpoint. The new
`assess` command supplies a three-result bundle, described below. The standalone
frontend accepts analysis alone or a bundle with an `analysis` member.

## Experimental acoustic evidence

```powershell
python -m pronouncedfish_engine assess sample.wav --expected-phones ð ə ɹ æ b ɪ t s ɪ t s ɪ n ð ə s ʌ n > assessment.json
```

This performs one model forward pass and returns `recognition`, `analysis`, and
`acoustic_assessment`. Existing `recognize` and `analyze` outputs are unchanged.
Open `assessment.json` in the frontend to see its separate acoustic evidence panel.

The versioned method, `ctc-single-substitution-log-support-v1`, compares full-target
CTC probabilities with sequences replacing one target phone at a time. It sums
CTC paths rather than assuming a phone segment boundary. Other target positions
stay fixed, and the selected variant is the one chosen by symbolic analysis.

Unlike fixed PanPhon distance, this evidence can change even when the winning
recognized phone stays the same. It is a **restricted experimental baseline**,
not full published GOP-SF, a correctness percentage, clinical severity, numerical
confidence calibration, or direct audio-to-feature prediction. There are no
insertion/deletion alternatives or learned decision thresholds.

The acoustic result includes method/model identity, calibration status, selected
target and candidate phones, full-target sequence log probability, and per-phone
`conditional_log_support`, `best_alternative_phone`, and
`log_margin_vs_best_alternative`. Log support closer to 0 means greater relative
support within this candidate set. A positive margin favors the target over its
best alternative; it does not establish correctness. `status` describes score
availability: `ok`, `partial`, or `unavailable`.

Pasketti target phones requiring multiple output classes (nasalization, length,
tied sequences) return unavailable rather than dropping their marks. Ordinary
complete single-class affricates are supported. Model adapters supply their own
phone IDs and blank; non-CTC adapters may explicitly return no CTC evidence.

See [acoustic assessment and model expansion](docs/acoustic-assessment.md) for
the exact formula, all JSON fields, resource limits, reference papers, and how to
add a future model. No custom training or calibration has been performed.

## Phone pairs, SODA, and the heatmap

A phone pair is one aligned target sound and recognized sound. For target
`["d", "ʌ", "k"]` and recognition `["t", "ʌ", "k"]`, the pairs are:

| Expected | Recognized | Interpretation |
| --- | --- | --- |
| `d` | `t` | Candidate substitution. |
| `ʌ` | `ʌ` | Matching tokens. |
| `k` | `k` | Matching tokens. |

An omission has a target phone and `null` recognized phone; an addition has the
reverse. The frontend displays gaps as `∅`. Alignment allows subsequent sounds to
remain matched after an insertion/deletion. Multiple minimum-edit explanations
can exist, so the returned alignment is one candidate explanation. Indices are
token positions, not word-initial/medial/final labels or audio timestamps.

SODA means **substitution, omission, distortion, addition**. The engine reports
candidate S/O/A differences; distortion is explicitly unassessed. The SRS proof of
concept scopes clinical substitution evaluation to a predetermined inventory.
Descriptive omissions/additions do not expand the validated clinical scope. Even
a listed substitution can originate in recognition error rather than production.

Features describe sounds, not correctness. The following are plain-language
introductions to the [PanPhon definitions](https://aclanthology.org/C16-1328/):

| Code | Feature | Interpretation / example |
| --- | --- | --- |
| `syl` | Syllabic | Forms a syllable's core; usually a vowel. Not a syllable count. |
| `son` | Sonorant | Relatively unobstructed, resonant production; vowels, nasals, liquids, and glides. |
| `cons` | Consonantal | Consonantal constriction; excludes vowels and glides in this system. |
| `cont` | Continuant | Continuous oral airflow, such as `s`; a stop such as `t` has closure. |
| `nas` | Nasal | Nasal airflow, as in `m` or `n`. |
| `voi` | Voiced | Vocal-fold vibration; `d` is positive, `t` negative. |
| `lab` | Labial | Lip involvement, such as `p`, `b`, or `m`. |
| `round` | Rounded | Lip rounding, such as `u`. |

The full 24-feature glossary is in the [team walkthrough](docs/PronouncedFish-Engine-Walkthrough.html#features).
Sonorant is not synonymous with voiced: `d` is voiced but not sonorant. Feature
values encode positive/negative/unspecified categories, not more/less correct.

For `d` → `t`, only voicing changes: `+1` → `-1`, giving absolute difference 2.
The other 23 feature differences are zero. In the heatmap, rows are phone pairs,
columns are features, and cells are absolute differences. Gaps and unavailable
mappings display `—`. A fixed distance map and a session confusion matrix are
different: a confusion matrix would count observed target/recognized combinations;
it is not implemented here.

These are symbolic lookup vectors derived from IPA, not WavLM's learned acoustic
embeddings. The model does not separately measure every feature from the audio.
If an acoustic distortion is still transcribed as the target IPA symbol, the
lookup vectors can be identical. Distance is neither confidence nor severity.

## Why use a package around Pasketti?

Pasketti supplies the trained recognition ability; our package does not improve
its accuracy by wrapping it. The package provides reusable audio preparation,
pinned/verified local assets, complete-token decoding, explicit result/review
states, and the target comparison consumed by the demo. Jiwer provides alignment;
PanPhon provides feature data. We reuse both rather than training another model
or implementing an edit-distance algorithm.

The official notebook's comparison answers **model versus human transcription of
the same production**. Our target analysis answers **recognized production versus
supplied practice pronunciation**. A correct transcription of “wabbit” can still
differ from the target “rabbit.” In the notebook's legend, green means an extra
model sound; it does not mean correct child production.

There is one Python package and one standalone frontend file. The previous unused
browser types, speculative interfaces, and empty future-feature folders were
removed. A small model-evidence interface now has an actual consumer in `assess`,
with replacement-model tests. Downloaded model JSON files are upstream assets, not additional services.
No frontend framework, HTTP service, database, training pipeline, or browser model
runtime was added for this milestone.

## Standalone frontend example

Open [frontend-demo.html](docs/frontend-demo.html) directly in a browser. This
single file contains all styles, scripts, and 13 cases: six illustrative symbolic
comparisons, one real-model synthetic sentence, and six playable S/O/A recordings.
Select sound pairs, inspect the feature heatmap and acoustic evidence, or open and
save engine result JSON. No server or install is required.

To load your own result, append `> analysis.json` to the `analyze` command above,
then choose **Open analysis JSON**. UTF-8 and BOM-marked UTF-16 files are supported.
The optional audio picker only plays a local file; it does not run recognition or
change the displayed analysis. The page makes no network requests or persistent
session writes. **How this frontend connects to the engine** explains integration.

If `analyze` reports that `--expected-phones` is missing, supply the target tokens;
the engine does not infer a practice target from the recording. If an older
PowerShell-generated JSON file has damaged IPA, regenerate it with the current
recognition CLI. Merely converting that file's encoding cannot recover sounds
already replaced or corrupted during redirection.

## Synthetic S/O/A comparisons and graphical groups

The frontend now includes six additional recordings/results, synthesized with
Microsoft David Desktop. They are adult synthetic prompts, not a child-speech
validation dataset. Audio is embedded in the standalone HTML, so each comparison
can be played without choosing a file. Generated WAVs and individual result JSONs
are also available locally in `examples/synthetic-soa/`, with `comparison-pack.zip`.

| Target | Spoken prompt | Intended change |
| --- | --- | --- |
| seat | Seat. | Control. |
| seat | Sheet. | Initial /s/ → /ʃ/ substitution. |
| seat | See. | Omit final /t/. |
| seat | Seats. | Add final /s/. |
| sunset | Sunset. | Two-group control. |
| sunset | Sun sat. | Change the second vowel; timing and prosody also differ. |

These are intended synthesis changes, not guaranteed recognition results. In the
recorded run the seat control itself ends in recognized `d`; sheet/seats include
additional recognition differences. Minimum-edit alignment can place an addition
differently when substitutions also occur. No predictions are edited to fit labels.
Both sunset recordings are recognized as the target, but the weakest second-group
acoustic margin drops from about +3.69 to +1.34. This is model evidence, not an
assessment of clinical severity or proof of the cause of the change.

The **Distance and acoustic support** panel offers phone or supplied-group views:

- Symbolic distance is a raw PanPhon distance per phone; group distance is the
  mean only when every target phone has a comparison. Gaps/unknown mappings stay
  unavailable, and unmatched additions are displayed separately.
- Acoustic margin is the raw log margin; a group's value is its weakest phone
  (minimum), not a learned syllable score. Positive favors target over the best
  restricted alternative; negative favors the alternative. No percent-correct
  conversion or clinical threshold is used.
- Outlined dots overlay the synthetic control for the same target/model. This
  recording is not a clinical norm and may itself have recognition errors.
- The axes are fixed for comparison (distance 0–12, margin −10 to +10); values
  outside that display range are clipped graphically; numeric labels are rounded
  to two decimals without clipping. Raw JSON keeps the full precision.
- “sun” and “set” use supplied groups of three target phones each. You can enter
  other group sizes, such as `3 3`, that sum to the selected target length. This is
  a display grouping, not automatic syllabification or measured audio boundaries.
  Custom grouping controls do not change the engine result.

Regenerate audio and assess it with one resident model:

```powershell
.\scripts\New-ComparisonAudio.ps1
python scripts/Assess-ComparisonAudio.py
```

The Python script writes per-fixture JSON with optional `demo_metadata`: the
synthesis prompt, target word, voice, supplied `syllables` intervals (`start`
inclusive, `end` exclusive), and embedded `audio_data_url`. These annotations are
fixture data, not extra fields in the core engine's assessment contract. The
frontend validates them when importing an individual fixture JSON. The aggregate
`comparison-examples.json` is for embedding examples, not a single result import.

If you see two `assessment.json` files, remember redirection is relative to the
shell's current directory. Running the command from `src/engine/` writes
`src/engine/assessment.json`, not `src/assessment.json`. Inspect with
`Get-Item .\assessment.json` and load the file from that directory. Console timing
lines are stderr diagnostics; JSON is redirected into the file.

## Check it

```powershell
python -m pytest -q
```

To include real-model inference using the generated synthetic sample:

```powershell
$env:PRONOUNCEDFISH_MODEL_DIR = (Resolve-Path models\pasketti-phonetic).Path
$env:PRONOUNCEDFISH_SMOKE_AUDIO = (Resolve-Path sample.wav).Path
python -m pytest -q
```

The integration test blocks network connections. Unit tests cover preprocessing,
CTC decoding and phone tokenization. Analysis tests run when its optional
dependencies are installed and cover alignment, variants, feature distances,
unknown phones, unassessable results, and the saved-JSON CLI. Librosa checks
that direct SoXR resampling preserves the earlier reference waveform.
Acoustic tests compare the CTC calculation with exhaustive path enumeration,
exercise model replacement, unknown mappings and impossible paths, and verify
audio-dependent scores with unchanged winning labels. The real-model integration
test now checks acoustic evidence as well as recognition. The latest full run
passed 85 tests; see the verification record for its scope.

`build/`, `*.egg-info/`, `__pycache__/`, and `.pytest_cache/` are generated by
packaging or Python/pytest. They are not source modules and are ignored by Git.
The obsolete `.venv` and earlier `.verification` artifacts have been removed;
the active development environment is the external conda environment.

See [model and license notes](docs/model-baseline.md),
[verification results](docs/recognition-verification.md), and the
[current team walkthrough](docs/PronouncedFish-Engine-Walkthrough.html), with a
locally generated PDF beside it (ignored by Git).
Next: measure recognition and candidate analysis against annotated child speech.
Browser/iPad inference and production application integration are not implemented.
The standalone frontend example demonstrates the interactive heatmap locally.
