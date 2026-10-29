# PronouncedFish engine

A small Python package that runs the pretrained Pasketti phonetic model locally.
It accepts WAV/FLAC audio and returns IPA plus complete phone tokens. Recognition
accuracy is inherited from Pasketti; we have not trained or fine-tuned it.
An optional analysis module compares those tokens against supplied target
pronunciations and returns candidate differences and phonological feature distances.

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
    assets.py               Download and verify a reproducible model snapshot
    recognition.py          AudioInput and RecognitionResult used by the code
    cli.py                  The download-model, recognize, and analyze commands
  tests/                    Regression checks and an optional real-model test
  scripts/                  One Windows synthetic-sample generator
  docs/                     Model notes, recorded checks, and team walkthrough
  models/                   Downloaded assets, ignored by Git
  pyproject.toml            Package metadata and dependency pins
  environment.yml           Conda setup; installs this package with test tools
```

There is no browser package or generic recognizer framework.
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
  per-feature absolute differences, and their sum (Manhattan distance). A future
  UI can plot alignment rows against feature columns to make a heatmap.

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

`build/`, `*.egg-info/`, `__pycache__/`, and `.pytest_cache/` are generated by
packaging or Python/pytest. They are not source modules and are ignored by Git.
The obsolete `.venv` and earlier `.verification` artifacts have been removed;
the active development environment is the external conda environment.

See [model and license notes](docs/model-baseline.md),
[verification results](docs/recognition-verification.md), and the
[team walkthrough of the earlier recognition-only baseline](docs/PronouncedFish-Engine-Walkthrough.html).
Next: measure recognition and candidate analysis against annotated child speech.
Browser/iPad inference and an interactive heatmap UI are not implemented.
