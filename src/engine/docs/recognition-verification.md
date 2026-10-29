# Engine verification — through 2026-10-29

The first Python audio-to-phone baseline executed successfully using the real
Pasketti checkpoint. This record concerns execution and software behavior, not
clinical accuracy or acceptance of the 87% recognition requirement.

## Current acoustic baseline — 2026-10-29

The complete conda suite passed **85 tests in 40.53 seconds**. This includes
existing recognition/analysis regressions and 22 new acoustic/workflow cases.
CTC probabilities and substitution scores are checked against exhaustive path
enumeration, including repeated phones and word-separator-to-blank marginalization.
Tests cover native model IDs, complete-affricate spelling aliases, normalization,
unknown/multi-class targets, resource limits, impossible/zero-probability paths,
partial availability, model-version mismatch, an independently supplied model
adapter, and combined CLI output. The prior 63-test count is historical.

The real-model integration check now obtains CTC evidence while forbidding network
connections and scores the generated sample's full target. A separate combined
`assess` smoke run used the real local model, counted **one forward pass**, and
returned 18 available acoustic phone scores with matching symbolic analysis.
The generated result was saved in a temporary file and embedded as the frontend's
seventh example; the original six illustrative symbolic examples remain.

That single CPU smoke run observed model load 12,781.7 ms and combined audio
preparation/recognition/analysis/scoring 1,667.3 ms. These are uncontrolled single
observations, not a latency guarantee or target-device benchmark.

The method is restricted single-substitution CTC sequence support, not full
published GOP-SF, calibrated correctness, severity, or direct phonological-feature
prediction. There are no acoustic decision thresholds or trained custom models.
See [method, output contract, and adapter details](acoustic-assessment.md).

Chrome checks passed for all seven cases and the 18-row acoustic panel at 1440,
768, and 390 px widths without page overflow. UTF-16 combined-result import
preserved IPA and acoustic fields; invalid positive log support and model-version
mismatch were rejected without replacing the current view. A browser download
was read back to confirm all three result objects were preserved. No runtime
exceptions or frontend network requests were observed. The expanded walkthrough
was checked for footer overlap and regenerated as a 16-page PDF.

## Synthetic S/O/A fixtures and graphical groups — 2026-10-29

Six new WAVs were synthesized locally with Microsoft David Desktop at rate -1,
then assessed with one resident real Pasketti model. Per-fixture JSON retains
predictions without correction, and includes optional fixture metadata, embedded
audio, and supplied phone groups. The standalone demo now embeds 13 cases. A
local ZIP contains WAVs, individual result JSONs, manifest, aggregate example
data, and a README. Generated files are ignored under `examples/synthetic-soa/`.

Observed candidate counts (S/O/A) were: seat control 1/0/0, sheet 2/0/0,
see 0/1/0, seats 1/0/1, sunset control 0/0/0, and sun sat 0/0/0. Thus synthesis
prompts are not verified recognizer labels. The seat control was recognized
with a final `d`; minimum-edit alignment in the addition example can also place
the unmatched phone differently from the intended suffix.

Sunset and sun sat had identical recognized phone tokens and symbolic distances.
The weakest raw acoustic margin in the supplied second group changed from about
+3.69 to +1.34. This illustrates audio dependence, not clinical quality or proof
that only the vowel caused the difference; timing/prosody also changed.

Chrome checks passed for all 13 results, embedded WAV decoding, phone/group
switching, custom group validation, gaps remaining unavailable, visible unmatched
additions, control overlays, result import/export preserving audio and metadata,
unsafe metadata rejection, and 1440/768/390 px layouts with no page overflow.
No frontend runtime exceptions or network requests were observed. The backend
math is unchanged; the prior 85-test suite remains its recorded verification.

The earlier JSON report was also checked: `src/assessment.json` was empty while
`src/engine/assessment.json` was 78,442 bytes, valid, and had acoustic status ok.
Both user files were preserved; the confusion was between two paths.

## Documentation refresh — 2026-10-28

The complete current conda suite passed **63 tests in 25.71 seconds**, including
real-weight recognition with network connections forbidden. This supersedes the
earlier test counts below. It includes 28 analysis cases after the PowerShell
encoding fix. No runtime changes were made for this documentation refresh.

| Area | Evidence and limits |
| --- | --- |
| Recognition | Actual pinned weights run on the local synthetic sample; no intended-population accuracy claim. |
| Analysis | Token alignment, variants, S/O/A candidates, exact feature lookup, and JSON behavior tested; no acoustic distortion detection or clinical severity. |
| Frontend | Six engine-generated illustrative examples, file import/export, interactive map, and local playback; Chrome desktop/tablet/mobile checks recorded below. No live inference connection. |
| Deployment | Python CPU development baseline; iPad/browser inference and production integration remain unverified/unimplemented. |

The sections below preserve the order of earlier measurements and fixes. Older
paths, environments, dependency extras, and timings describe those historical
runs. Use the [current README](../README.md) for installation and commands, and
the [updated walkthrough](PronouncedFish-Engine-Walkthrough.html) for the current
end-to-end explanation and complete result contracts.

## Environment and sample

- Windows build 26200; Intel64 Family 6 Model 154 Stepping 3; CPU inference.
- Python 3.9.12, PyTorch 2.6.0, Transformers 4.57.6, librosa 0.11.0,
  NumPy 1.26.4, soundfile 0.13.1.
- Model revision and SHA-256: see [baseline identity](model-baseline.md).
- Audio: locally synthesized Windows `System.Speech` reading
  “The rabbit sits in the sun.” No microphone or patient recording was used.
- Source WAV: 22,050 Hz, mono, 49,923 frames (2.2641 seconds), resampled to 16 kHz.
- At this stage, generated assets were under ignored `.verification/` and `models/`.
  The synthetic recording now lives at `engine/sample.wav`; `.verification/` was removed.

## Observed result

Raw model transcription:

```text
ðə ɹæbɪt sɪts ɪn ðə sʌn
```

Produced-phone tokens:

```text
ð ə ɹ æ b ɪ t s ɪ t s ɪ n ð ə s ʌ n
```

The recognizer received the waveform alone. The phrase was only the synthesis
input, not a model prompt or expected transcription. Output status was `ok`,
confidence status `uncalibrated`, and `requires_review` was true.

One CLI execution reported:

| Measurement | Observed time |
| --- | ---: |
| Model initialization, including import/load and asset checks | 8,137.6 ms |
| File preprocessing | 2,896.5 ms |
| Model forward pass | 874.8 ms |
| Processing, including preprocessing, inference, and decoding | 3,778.9 ms |

Initialization plus processing was approximately 11.92 seconds in that run.
This is one desktop smoke measurement with startup overhead, not a repeated
latency benchmark or evidence of iPad performance. Separate cold/warm studies,
longer utterances, peak-memory measurement, and target-device testing remain open.

## Checks performed

- **30 unit cases passed**: CTC blank-separated repetitions, affricates and
  combining marks, unusable input, non-finite model output, stereo conversion,
  resampling, and rejection of invalid or oversized source recordings.
- **1 real-model integration test passed** with `socket.connect` and
  `socket.create_connection` forbidden during model initialization and inference.
- Pinned weights passed SHA-256 verification; parser symbols exactly matched
  the downloaded vocabulary.
- Editable package installation and dependency consistency (`pip check`) passed.
- An upstream PyTorch attention-mask deprecation warning was present in this
  initial run. The later correction below removes its cause for unpadded input.

Unit fixtures supply deterministic logits for decoding behavior only. They are
not used by production code and are not counted as recognition-accuracy results.
The single synthetic voice is not representative of children aged 4–6, atypical
speech, or consonant substitutions. No PER, calibrated confidence, substitution
precision/recall, or SRS accuracy result has been measured.

## Conda verification — 2026-10-28

The existing `phoneme-engine` conda environment was configured with Python
3.12.16 and the engine's `recognition` and `dev` extras. The same downloaded
model and synthetic sample were reused. All **31 tests passed** in 24.93 seconds,
including real-model inference with network connections forbidden. `pip check`
also passed. The upstream attention-mask deprecation warning remained visible.

The restricted runner denied access to pytest-created temporary folders, so the
successful run used normal filesystem access with a fresh workspace-local
`--basetemp` and `NUMBA_CACHE_DIR`. No recognition implementation changes were
needed. The timing table above remains the original Python 3.9 measurement;
the conda test duration is not an inference benchmark.

## CLI output and preprocessing correction — 2026-10-28

A user run showed JSON-escaped IPA, the mixed attention-mask warning, and
14,001.2 ms of preprocessing (773.8 ms of model inference). Investigation of the
installed libraries showed that librosa's first resampling call loaded a large
dependency chain. On the synthetic sample, direct SoXR initialization/resampling
took 7.7 ms in a comparison process; librosa's first call took 2,824.5 ms.
After matching librosa's ceil-length padding, the waveforms were identical.

Changes verified:

- File preprocessing uses SoXR HQ directly with the same output-length convention.
- The single, unpadded recognition call omits its redundant padding mask; no
  warning is suppressed in production and no installed library is patched.
- CLI output uses UTF-8 JSON with readable IPA rather than ASCII escape sequences.

**35 tests passed** in the conda environment. New checks compare resampling
against librosa at four source rates, including fractional output lengths.
The real-model test treats the unwanted warning as an error and verifies that
mask-free decoding matches the original all-valid-mask decoding, while forbidding
network connections. A separate CLI check confirmed valid UTF-8 JSON, readable
IPA, and no mixed-mask warning. `pip check` passed.

The latest CLI run on the same 2.2641-second synthetic recording reported:

| Measurement | Observed time |
| --- | ---: |
| Model initialization | 16,062.0 ms |
| File preprocessing | 5.3 ms |
| Model forward pass | 2,561.2 ms |
| Processing after initialization | 2,579.4 ms |

The transcription remained `ðə ɹæbɪt sɪts ɪn ðə sʌn`. These are single-run
measurements, not controlled performance benchmarks; initialization and inference
times varied across runs. Complete startup plus processing was about 18.64 seconds
in this run, so startup remains a separate latency concern. Reusing an initialized
recognizer avoids paying model-load cost for every attempt. The iPad and clinical
accuracy requirements remain unverified.

## Repository simplification

The source now lives directly in `engine/pronouncedfish_engine/`. Unused browser
types, analysis interfaces, the generic recognizer protocol, and the speculative
architecture document were removed. Runtime dependencies install with the package;
`.[dev]` adds pytest and the librosa waveform reference used by tests. The sample
generator now writes `engine/sample.wav`.

The original `.venv`, build outputs, and `.verification` caches were local
development artifacts, not required source directories. They were cleaned up
after preserving the synthetic sample. Earlier paths and timings above are a
historical verification record. Model assets and the conda environment are retained.

## Reproduce on Windows

After the installation and model download in the [README](../README.md), run from
`src/engine/` with the Microsoft David Desktop voice installed:

```powershell
conda activate phoneme-engine
.\scripts\New-SmokeAudio.ps1
python -m pronouncedfish_engine recognize sample.wav
$env:PRONOUNCEDFISH_MODEL_DIR = (Resolve-Path models\pasketti-phonetic).Path
$env:PRONOUNCEDFISH_SMOKE_AUDIO = (Resolve-Path sample.wav).Path
python -m pytest -q
```

Timing can vary with CPU load, operating-system caches, and first-use library
initialization. The helper performs local speech synthesis only. On other
platforms use a permitted synthetic/development WAV or FLAC instead.

## Optional analysis verification — 28 October 2026

The recognition package now exposes `analyze(result, expected_phones, ...)` and
a saved-JSON `analyze` CLI command. The optional `analysis` extra installs
Jiwer 4.0.0 and PanPhon 0.22.2. The conda environment has these dependencies
installed; `pip check` reports no broken requirements.

The full suite passed **59 tests in 23.88 seconds** in the Python 3.12 conda
environment, including the existing real-weight recognition test with network
connections blocked. There are 24 new analysis cases covering complete-token
alignment, accepted variants, spelling aliases, retained IPA distinctions,
directional substitution inventories, unknown feature mappings, unassessable
recognition, offline feature loading, input/cache preservation, and CLI output
and error handling. These are software checks, not child-speech accuracy results.

The real packaged PanPhon data has 24 feature columns. `/t/` versus `/d/` yields
Manhattan distance 2, entirely in `voi`. Gaps and unknown phones receive no
distance. PanPhon's default loader failed under Windows cp1252; the implementation
reads its installed CSV explicitly as UTF-8 without modifying the library.

At this analysis-only stage, no acoustic distortion detector, clinical severity score, heatmap UI, approved
practice-item dictionary, or validated substitution inventory was added. Those
remain distinct from descriptive target comparison. The subsequent standalone
frontend adds a heatmap prototype. The HTML/PDF walkthrough has now been refreshed
to cover recognition, analysis, and that prototype; the [README](../README.md)
describes the current API and its limits.

### Windows PowerShell JSON redirection fix

The analysis CLI now lets the standard JSON decoder detect UTF-8/16/32 from
bytes. Windows PowerShell's UTF-16 redirection previously failed UTF-8 decoding.
The existing redirected file also contained IPA corrupted by OEM-code-page
decoding before it was written, so decoding the file alone was insufficient.
Redirected CLI JSON now uses ASCII Unicode escapes; interactive output keeps IPA.
Previously corrupted files must be regenerated from their source recording.

All 28 analysis tests passed, including five Unicode file encodings and a simulated
UTF-8-to-cp437-to-UTF-16 redirection. A real PowerShell `recognize sample.wav >`
temporary-file run followed by `analyze` returned `status="ok"`,
`matches_target=true`, and zero substitutions, omissions, or additions against
the synthetic sample's expected phones. The user's existing file was preserved.

### Standalone frontend example

`frontend-demo.html` embeds six actual `analyze()` outputs for illustrative phone
inputs and needs no external assets, network, or server. Headless Chrome checks
passed at desktop (1440 px), tablet (768 px), and mobile (390 px) widths without
page overflow. Screenshots were inspected outside the source tree.

Browser checks exercised all scenarios, phone selection, changed/all-feature
views, correct IPA and distances (`ɹ` → `w`: 9; `d` → `t`: 2), keyboard focus,
UTF-16 file input, malformed/recognition-only file errors, safe rendering of
imported strings, and local synthetic-audio playback without changing analysis.
No JavaScript runtime exceptions were observed. This verifies the prototype
renderer, not live browser inference or clinical validity.
