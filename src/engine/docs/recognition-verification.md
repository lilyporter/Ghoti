# Recognition verification — 2026-10-28

The first Python audio-to-phone baseline executed successfully using the real
Pasketti checkpoint. This record concerns execution and software behavior, not
clinical accuracy or acceptance of the 87% recognition requirement.

## Environment and sample

- Windows build 26200; Intel64 Family 6 Model 154 Stepping 3; CPU inference.
- Python 3.9.12, PyTorch 2.6.0, Transformers 4.57.6, librosa 0.11.0,
  NumPy 1.26.4, soundfile 0.13.1.
- Model revision and SHA-256: see [baseline identity](model-baseline.md).
- Audio: locally synthesized Windows `System.Speech` reading
  “The rabbit sits in the sun.” No microphone or patient recording was used.
- Source WAV: 22,050 Hz, mono, 49,923 frames (2.2641 seconds), resampled to 16 kHz.
- Local generated assets remain under ignored `.verification/` and `models/`.

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
