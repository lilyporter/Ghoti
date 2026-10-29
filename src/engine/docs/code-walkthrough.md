# Understanding the PronouncedFish code

This guide explains the current implementation from the recording to the screen.
Start with sections 1–6 to understand the calculations. Sections 7–12 connect them
to every source module, the frontend functions, setup files, scripts, and tests.
The examples below are teaching examples unless explicitly identified as saved
synthetic model runs. No model was trained as part of this package.

## Contents

1. [What the engine actually does](#1-what-the-engine-actually-does)
2. [Follow one recording through the code](#2-follow-one-recording-through-the-code)
3. [Phone sequences and S/O/A alignment](#3-phone-sequences-and-soa-alignment)
4. [Feature vectors and Manhattan distance](#4-feature-vectors-and-manhattan-distance)
5. [Scores that use the actual recording](#5-scores-that-use-the-actual-recording)
6. [How the frontend draws closeness](#6-how-the-frontend-draws-closeness)
7. [Python source, function by function](#7-python-source-function-by-function)
8. [Frontend source, function by function](#8-frontend-source-function-by-function)
9. [Model files, dependencies, and generated files](#9-model-files-dependencies-and-generated-files)
10. [Synthetic examples and tests](#10-synthetic-examples-and-tests)
11. [Replacing the recognition model](#11-replacing-the-recognition-model)
12. [Run, inspect, and troubleshoot](#12-run-inspect-and-troubleshoot)

Related documents: the [engine README](../README.md) contains the JSON field
reference; [acoustic assessment](acoustic-assessment.md) gives the detailed scoring
contract; the [team walkthrough](PronouncedFish-Engine-Walkthrough.html) is the
shorter presentation; [verification notes](recognition-verification.md) record
past checks. Open [frontend-demo.html](frontend-demo.html) alongside this guide.

## 1. What the engine actually does

Think of three questions being answered in sequence:

| Question | Result object | Where its evidence comes from |
| --- | --- | --- |
| What sounds did the model estimate? | `recognition` | The recording passed through Pasketti. |
| How do those sound labels differ from the target labels? | `analysis` | The target supplied by the caller, the recognized labels, an alignment algorithm, and the PanPhon lookup table. |
| How much does the recording's model output support a target sound versus replacements? | `acoustic_assessment` | The model's frame probabilities and the selected target sequence. |

`recognize` returns the first object alone. `analyze` returns the second object
alone from saved recognition JSON. `assess` returns a bundle containing all three.
They are different outputs, rather than three names for one score.

The frontend reads these outputs. It does not run the Python model. Opening a WAV
in the HTML page only lets you listen; it does not analyze that WAV.

### Vocabulary used in this code

| Term | Meaning here |
| --- | --- |
| Phone | A speech sound represented by one complete IPA token, such as `s`, `ə`, or `t͡ʃ`. The code compares these tokens as discrete labels. |
| Token | One item in a sequence. A complete phone can contain several Unicode characters. A model token is a native output class, which is not always a complete phone. |
| PCM sample | One waveform amplitude at one instant. At 16 kHz there are 16,000 samples per second. |
| Frame | One step in the model's output sequence after its audio encoder has reduced the sample sequence. A frame is not a syllable. |
| Class / token ID | A numbered slot in the model output vocabulary: for example a phone, a blank, a separator, or a mark. IDs are specific to that model. |
| Logit | An unnormalized model score for a class at a frame. It is not a probability yet. |
| Feature vector | In symbolic analysis, a list of 24 fixed category values looked up for a phone. In neural-network discussions, “vector” can instead mean a learned representation of the recording. Those are different things. |
| Alignment | A pairing of target and recognized sequence positions, allowing gaps. This alignment has no audio times. |
| `None` / `null` | Python's / JSON's representation of an absent value. It must not be read as numeric zero. |

## 2. Follow one recording through the code

The normal combined path is:

```text
CLI: python -m pronouncedfish_engine assess recording.wav --expected-phones s i t
  __main__.py → cli.main()
    PaskettiRecognizer(model_dir)           verify and load the model
    load_audio(recording.wav)              prepare waveform
    assess(recognizer, audio, [s, i, t])
      recognize_with_evidence(audio)
        _run(..., keep_evidence=True)      ONE neural-network forward pass
          model → frame logits
          argmax + CTC decode → phones     recognition
          log_softmax → frame evidence     internal CTCEvidence
      analyze(recognition, target)         alignment + PanPhon distances
      score_ctc(evidence, selected_target)  acoustic sequence comparisons
      return {recognition, analysis, acoustic_assessment}
    JSON to stdout; timing to stderr

HTML: import that JSON → validate → store state → render tables and plots
```

The target does not go into Pasketti's recognition call. The model first estimates
what it heard without the practice answer. The target is used afterward for
comparison. This helps preserve a wrong-sounding prediction instead of silently
rewriting it to the expected word.

### What the data looks like at each boundary

| Step | Data shape | Example / interpretation |
| --- | --- | --- |
| File reader | Source frames × channels | Stereo WAV has two amplitudes at each source instant. |
| Prepared `AudioInput` | One-dimensional float32 samples, 16 kHz | One second becomes roughly 16,000 amplitudes in `[-1, 1]`. |
| Processor input to model | Tensor with one utterance | The processor normalizes the waveform; this is distinct from resampling. |
| Model output | `1 × T × C` logits | One utterance, `T` output frames, `C` classes. Neither dimension is the number of target phones. |
| Greedy decoding | One class ID per frame, then a string | CTC collapse removes blanks and consecutive repeats. |
| Recognition | Complete phone list plus raw transcription | For example `["s", "i", "d"]`. |
| Internal evidence | `T × C` normalized log probabilities | Kept in memory for scoring; absent from public JSON. |
| Analysis | One row per aligned pair or gap | Expected `t` paired with recognized `d` is a candidate substitution. |
| Acoustic assessment | One row per selected target position, when scoreable | Target `t` contrasted with alternative phone sequences. |

Construct the recognizer once in an application and reuse it. The command-line
program starts a new process each time, so a separate invocation reloads and
verifies the model. The large load cost is not paid for every recording if an
application keeps the Python object alive.

## 3. Phone sequences and S/O/A alignment

Suppose the target is `[s, i, t]` and the estimated production is `[s, i, d]`.
`analyze()` uses Jiwer to find a sequence alignment with minimum unit-cost edits.
It treats each complete phone as one item, even though the Jiwer function is
named `process_words`. We supply space-separated phones as its “words.”

| Target | Recognized | Row kind | Edit cost |
| --- | --- | --- | --- |
| `s` | `s` | match | 0 |
| `i` | `i` | match | 0 |
| `t` | `d` | substitution | 1 |

Other simple cases:

| Target sequence | Recognized sequence | Interpretation |
| --- | --- | --- |
| `s i t` | `s i` | Omission: expected `t`, recognized gap. |
| `s i t` | `s i t s` | Addition: expected gap, recognized `s`. |
| `s i t` | `s i t` | Labels match. This does not establish acoustic correctness. |

S/O/A means substitution, omission, addition. D in SODA means distortion and is
currently **not assessed**. A label comparison cannot establish that a child
distorted a sound, nor establish that a mismatch was the child's error rather
than the recognizer's error.

The algorithm aligns whole sequences instead of blindly pairing list positions.
An omission near the start should not cause every later phone to be reported as
a substitution. Repeated phones can permit multiple equally cheap alignments;
the returned alignment is one possible explanation, not a unique acoustic fact.

### Three different meanings of “distance”

| Calculation | Example | What uses it |
| --- | --- | --- |
| Unit-cost sequence edits | `s i t` → `s i d` costs 1 substitution. | Alignment and selection of an acceptable variant. |
| PanPhon Manhattan distance | `t` → `d` differs by 2 in the voicing feature. | Per-pair feature comparison and heatmap. |
| Acoustic log comparison | Target sequence versus sequences with one replacement. | Experimental audio-dependent scoring. |

The first calculation does **not** use PanPhon to weight edits. A substitution
costs one edit regardless of its feature distance. An omission costs one edit but
gets no feature distance, because there is no recognized phone vector to compare.

### Variants, indices, and supported pairs

The main target is variant 0. `--acceptable-variant` adds supplied pronunciations
in order. The variant with the fewest total S+O+A edits wins; ties select the first
in supplied order. No dictionary or automatic dialect decision supplies variants.
Acoustic assessment then uses this selected variant too; it does not choose a
different variant based on its acoustic scores.

`expected_index` and `recognized_index` are separate, zero-based phone positions.
For target `s i t` and recognized `s i`, the omission row has expected index 2,
recognized index `null`. Additions have the reverse arrangement. Neither index
is a character offset, word position, syllable number, or recording timestamp.

`supported_substitutions=[("t", "d")]` marks that directional pair as present in
the caller's inventory. It does not turn the pair into a match, alter distances,
change decoding, or mean the pronunciation is acceptable. The reverse `(d, t)`
is a separate pair. Without a supplied inventory, substitution flags are false.

## 4. Feature vectors and Manhattan distance

### Where the vector comes from

For each aligned pair with two phones, `_features()` performs two dictionary
lookups in PanPhon's packaged table:

```text
expected phone "t"   → fixed vector for /t/
recognized phone "d" → fixed vector for /d/
```

The recognized phone was estimated from audio, but the vector for that label is
fixed. Every occurrence of `d` uses the same PanPhon `d` vector. A clearer `d`, a
noisy `d`, and an uncertain prediction of `d` therefore get the same symbolic
vector. The engine does not extract these 24 feature values from that recording.

This directly answers the “actual said vector or detected phoneme vector?”
question: **this distance compares the detected phone's lookup vector with the
target phone's lookup vector.** The acoustic layer in section 5 uses more of the
recording's model evidence, but still does not predict a measured 24-feature
vector. Hidden WavLM embeddings are also not these 24 linguistic coordinates.

### Read one vector

The order is defined by `feature_names`, currently 24 names from the pinned table:

```text
syl son cons cont delrel lat nas strid voi sg cg ant cor distr
lab hi lo back round velaric tense long hitone hireg
```

Each vector position is `-1`, `0`, or `+1`. These are categorical specifications:
negative, unspecified/neutral in that table, or positive. They are not waveform
amplitudes, probabilities, or measured percentages. Zero is a real table entry;
an unavailable comparison is represented separately by `null`.

| Feature | Plain-language meaning |
| --- | --- |
| `syl` | Syllabic: whether the segment is specified as functioning as a syllable nucleus; this does not count or locate syllables. |
| `son` | Sonorant: a category including vowels and sounds such as nasals/liquids; different from voicing. A voiced stop such as `d` is not thereby a sonorant. |
| `cons` | Consonantal: a consonant-like constriction category. |
| `cont` | Continuant: airflow is not fully stopped at the relevant constriction. |
| `delrel` | Delayed release, relevant to affricates. |
| `lat` | Lateral airflow. |
| `nas` | Nasal airflow. |
| `strid` | Strident friction category. |
| `voi` | Voiced: vocal-fold vibration category. |
| `sg`, `cg` | Spread / constricted glottis. |
| `ant`, `cor`, `distr` | Anterior, coronal, distributed: categories of tongue constriction location/extent. |
| `lab` | Labial involvement. |
| `hi`, `lo`, `back` | High, low, back tongue-position categories. |
| `round` | Lip rounding. |
| `velaric` | Velaric airflow mechanism. |
| `tense` | Tense category. |
| `long` | Length category; not a measured duration in milliseconds. |
| `hitone`, `hireg` | High tone / high register categories. These are not measured pitch tracks. |

These short explanations help read the table; the exact specification is the
versioned PanPhon data, not an independent clinical assessment by this engine.

### Work through /t/ versus /d/

In the current table these vectors differ only in `voi`:

| Coordinate | Expected `t` | Recognized `d` | Absolute difference |
| --- | --- | --- | --- |
| `voi` | -1 | +1 | `abs(-1 - (+1)) = 2` |
| Each of the other 23 coordinates | Same value on both sides | Same value on both sides | 0 |
| Sum | | | **2** |

The full calculation in the code is:

```python
differences = [abs(x - y) for x, y in zip(expected_vector, recognized_vector)]
distance = sum(differences)
```

This is Manhattan distance: add the absolute coordinate differences. There is no
square root, learned weight, cosine similarity, or normalization. A `-1` to `+1`
change contributes 2; `0` to `+1` contributes 1; equal values contribute 0. Thus
distance 2 does not always mean two differing features. `ɹ` versus `w` has distance
9 in the current table, but that does not make it “4.5 times as severe” as `t/d`.

With 24 coordinates bounded by `[-1, +1]`, 48 is a mathematical upper bound on
this formula. It is not a verified maximum among actual table entries, a severity
scale, or the frontend plot's chosen limit.

### How that becomes JSON and a heatmap

`feature_comparison` stores both vectors, the 24 absolute differences, and their
sum in `manhattan_distance`. Entry `i` in each list corresponds to entry `i` in
`feature_names`. `renderHeatmap()` draws the differences, not the original feature
signs: a `2` cell means opposite `-1/+1` specifications; it does not mean feature
value `+2`. The detail panel shows the original values for changed coordinates.

The “changed features only” control hides columns that are zero for every
available pair. If no features change it shows all columns. This control affects
visibility only; the sum and JSON are unchanged.

| Situation | `feature_status` | Distance |
| --- | --- | --- |
| Both complete phones have exact entries | `available` | Computed, possibly 0. |
| At least one exact entry is missing | `unavailable` | `null` comparison; no guessed distance. |
| Addition or omission has a gap | `not_applicable` | `null` comparison; no zero-vector stand-in. |

Unicode spellings are canonicalized for comparison: `g`/`ɡ`, `ʧ`/`t͡ʃ`, and
`ʤ`/`d͡ʒ` are aliases, and NFD decomposes Unicode consistently. Original output
labels are preserved. Nasality and length are retained; `r` and `ɹ` remain
different sounds. Unknown or multi-part phones are not silently shortened to
force a successful feature lookup.

## 5. Scores that use the actual recording

### The evidence before decoding

Pasketti produces a vector of class scores at each output frame. A simplified
three-class frame could assign probabilities blank 0.1, `t` 0.8, and `d` 0.1.
The actual model has more classes and many frames.

The code converts logits using `log_softmax`:

```text
probability(class j) = exp(logit[j]) / sum(exp(logit[k]))
log_probability(j)   = logit[j] - logsumexp(all logits)
```

`logsumexp` computes the log of a sum of exponentials stably. The scorer uses
natural logs (`ln`, base e). Probabilities from many frames can be tiny;
multiplication becomes addition in log space, avoiding numerical underflow.
`ln(1)=0`, `ln(0.5)≈-0.693`, `ln(0.1)≈-2.303`. A larger log probability means
more model support, even when both numbers are negative.

Recognition keeps only the highest-scoring class per frame (`argmax`) and decodes
that path. Acoustic assessment retains the full class distribution at every
frame. Two recordings can therefore produce the same recognized phone sequence
and still produce different acoustic scores.

### What CTC does

The model produces many frames while the target has relatively few phones.
Connectionist Temporal Classification (CTC) connects these lengths using a blank
class and repeated labels. Collapse consecutive repeated IDs, then remove blank:

```text
t t blank d d       → t d
t blank t          → t t       (the blank preserves separate repeated phones)
```

The blank is not a phone and is not itself a detection of silence. It is a CTC
alignment class. The greedy transcript comes from one winning frame path. A
sequence's CTC probability sums **all** frame paths that collapse to that sequence.
Consequently, full-sequence scoring is not simply the confidence of the winning
frame or the average probability of the decoded labels.

Here is a complete, tiny example with two frames:

| Frame | Blank | `a` | `b` |
| --- | --- | --- | --- |
| 1 | 0.2 | 0.6 | 0.2 |
| 2 | 0.5 | 0.1 | 0.4 |

Paths yielding the one-phone target `a` are `[a,a]`, `[a,blank]`, `[blank,a]`:

```text
P_CTC(a | audio) = 0.6×0.1 + 0.6×0.5 + 0.2×0.1 = 0.38
P_CTC(b | audio) = 0.2×0.4 + 0.2×0.5 + 0.2×0.4 = 0.26
```

Other paths produce other outputs, so these two numbers need not sum to 1.
The implementation uses PyTorch's CTC dynamic programming rather than enumerating
all paths, which would become enormous on real recordings.

### The two per-position scores

For target `[s, i, t]`, at position 2 the scorer evaluates sequences `[s, i, p]`
for every candidate phone `p`. Other positions stay at their target labels. At
position 0 it instead evaluates `[p, i, t]`. This is context-dependent: a score
belongs to a position in a full target, not to an isolated audio slice.

Let `L_target` be the CTC log probability of the complete target. For position `i`:

```text
conditional_log_support = L_target - logsumexp(L_of_each_replacement_sequence)
log_margin_vs_best_alternative = L_target - max(L_of_non_target_sequences)
```

The denominator includes the target itself. The best alternative excludes it.
`best_alternative_phone` names the replacement with the highest sequence score;
it need not be the greedy recognized phone.

Using the two-frame example and the candidate set `{a,b}`:

```text
L_target = ln(0.38) ≈ -0.967584
conditional_log_support = ln(0.38 / (0.38+0.26)) ≈ -0.521297
margin = ln(0.38 / 0.26) ≈ +0.379490
```

Log support is at most 0; closer to 0 means stronger relative target support
within this restricted candidate set. A positive margin favors the target over
the best replacement; a negative margin favors a replacement. A zero margin is
a tie. These are not calibrated probabilities of correct pronunciation. Even
exponentiating log support gives a share of this restricted model comparison,
not the probability a clinician would judge the sound correct.

The same principle with a single frame, target `t` 0.8 and alternative `d` 0.1,
gives log support `ln(0.8/0.9)≈-0.117783` and margin `ln(8)≈+2.079442`.
The blank probability 0.1 does not become a replacement phone in that denominator.

### What `score_ctc()` actually loops over

1. Copy the evidence to CPU float64; validate shape, probability normalization,
   class IDs, and limits. Remove small float32 normalization residuals.
2. Canonicalize complete-phone keys and map the target to native output IDs.
   A target phone must map to one native class. Never discard a mark to make it fit.
3. Merge ignored word-separator probability into blank for phone-only scoring.
   Do not redistribute other excluded classes, such as modifier classes.
4. Call nested `sequence_log_probs()` once for the target. It uses
   `-F.ctc_loss(..., reduction="none", zero_infinity=False)` to obtain log
   probabilities. An impossible full target produces unavailable scores.
5. For each target position, build a batch with one sequence per candidate;
   replace that position's ID, score the batch, then compute the two comparisons.
6. Return `ok`, `partial`, or `unavailable` depending on usable rows. Convert
   unavailable values to `null`, rather than writing NaN or infinity into JSON.

If there are `L` target positions and `K` candidates, the loop scores `K`
counterfactual sequences per position. These reuse the **same neural output**.
There are not `L×K` calls to the speech model, though the CTC calculation still
has a cost that grows with the sequence and candidate sizes.

Limits are at most 2,000 frames, 2–128 candidate phones, and at most 128 target
phones. Invalid evidence raises an error; unsupported mappings or impossible
targets produce an explicit unavailable result. Individual rows can also be
unavailable if no finite non-target path exists.

This method is named `ctc-single-substitution-log-support-v1`. It is an
experimental, restricted baseline, inspired by pronunciation-assessment research.
It is not a full implementation of published GOP-SF, has no insertion/deletion
alternatives in its denominator, supplies no segment times, and has no calibrated
good/bad threshold. Whole-sequence log probability is not length-normalized and
should not be used as a universal score across unrelated recordings or models.

## 6. How the frontend draws closeness

The screen deliberately shows symbolic feature distance and acoustic margin as
separate measurements. It does not combine them into an accuracy percentage.

### Phones versus supplied syllable groups

`targetGroups()` either creates one group per target phone or uses supplied
intervals such as `sun=[0,3)` and `set=[3,6)` for `s ʌ n s ɛ t`. Brackets mean
start included, end excluded. These intervals refer to phone indices, not seconds.
Typing `3 3` in the custom grouping control supplies two three-phone groups.
The program does not detect syllable boundaries from audio. Grouping does not
change the underlying alignment or the engine's JSON fields.

For each group, `groupMetrics()` computes:

| Display metric | Rule | Worked example |
| --- | --- | --- |
| Feature distance | Mean of the available per-target-phone Manhattan distances, only if every target phone in the group has a complete feature comparison. | Distances `[0,2,0]` give `(0+2+0)/3 = 0.6667`. |
| Acoustic margin | Minimum per-target-phone margin, only if all target positions have usable acoustic rows. | Margins `[5,1.34,1.42]` give `1.34`. |

These are frontend aggregation choices: the mean reduces dependence on group
length; the minimum highlights the least-supported position. They are not learned
syllable scores or a validated way to diagnose syllable quality. A negative margin
is smaller than a positive one, so it determines the minimum when present.

An omission prevents a complete feature comparison; its group distance is
unavailable instead of a misleading zero. Additions have no target index and are
listed separately; they are not averaged into a target vector. Acoustic scoring
does not include insertion/deletion alternatives, so an acoustic group value
must not be read as “no S/O/A problems.”

### From numbers to positions on a bar

`metricPlot()` chooses these fixed display axes:

```text
Feature position (%) = clamp(distance, 0, 12) / 12 × 100
Margin position (%)  = 50 + clamp(margin, -10, +10) × 5
```

Distance 2 sits at 16.67% of its bar. Margin +2 sits at 60%; margin -2 at 40%.
Feature distance 0 is the target end; acoustic margin 0 is the center/tie point.
The axes are visualization choices, not clinical cutoffs. Values outside the
display range are drawn at the edge. Numeric labels still show the actual value
rounded for display, and JSON retains the underlying precision.

The outlined reference marker comes from a bundled synthetic control for the
same target sequence and model version. It is not a universal ideal speaker.
Even a control recording can be misrecognized.

### A real example already in the page

The bundled synthetic “Sunset.” and “Sun sat.” runs both decoded to `s ʌ n s ɛ t`.
Both therefore have zero symbolic distance at every matched phone. Their second
supplied group's minimum acoustic margin differs: approximately **3.69** for the
control and **1.34** for the changed prompt. The acoustic layer can distinguish
model evidence even when hard labels are identical. This observation is not a
validation of correctness or proof that only vowel quality caused the difference;
the synthetic recordings can differ in timing and prosody too.

Conversely, the synthetic “Seat.” control was recognized as `s i d`, so it already
contains a model mismatch. The page preserves that prediction instead of changing
the result to fit the fixture's intended label.

## 7. Python source, function by function

Leading underscores mark internal implementation helpers. They are not separate
services or extra layers of machine learning. Type hints document expected data;
they do not automatically validate input. The checks inside functions do that.

### Entry points and public data: `__init__.py`, `__main__.py`, `recognition.py`

| Symbol | Responsibility |
| --- | --- |
| [`__init__.py`](../pronouncedfish_engine/__init__.py) / `__all__` | Exposes the public imports: audio/result types, recognizer, analysis, assessment, and evidence types. Importing the package does not construct or download the neural model. |
| [`__main__.py`](../pronouncedfish_engine/__main__.py) | Makes `python -m pronouncedfish_engine` call `cli.main()` and pass its return value to `SystemExit`. |
| [`AudioInput`](../pronouncedfish_engine/recognition.py) | Frozen dataclass carrying `samples` and `sample_rate_hz`. “Frozen” prevents assigning new fields; it does not make an underlying NumPy array immutable. |
| `RecognitionResult` | `TypedDict` describing recognition's JSON-compatible fields. `status="ok"` means output was produced and parsed, not that the sounds are correct. Review and confidence fields preserve that distinction. |

### Assets: [`assets.py`](../pronouncedfish_engine/assets.py)

| Symbol | Responsibility |
| --- | --- |
| Constants `MODEL_ID`, `REVISION`, `MODEL_VERSION`, `WEIGHTS_SHA256`, `MODEL_FILES`, `MANIFEST_NAME` | Identify the approved upstream snapshot, files, weight digest, and local manifest. Version is model ID plus exact revision. |
| `_weights_digest(path)` | Reads a file in 8 MiB chunks and computes SHA-256. Despite its name, it hashes configuration/tokenizer files as well as weights. A hash verifies bytes, not model accuracy. |
| `download_pasketti(model_dir)` | Explicitly downloads the pinned public snapshot through Hugging Face, hashes files, checks the pinned weight digest, writes `pronouncedfish-model.json`, and returns the resolved directory. |
| `verify_model(model_dir)` | Offline check for all required files and the manifest, expected model version, each file's recorded digest, and the independently pinned weight digest. Raises if files are absent or changed. Never downloads missing files. |

### Audio preparation: [`audio.py`](../pronouncedfish_engine/audio.py)

`load_audio(path)` returns an `AudioInput`. It checks the local file's WAV/WAVEX
or FLAC format and duration, reads float32 samples with SoundFile, validates every
source channel, averages channels to mono, and resamples to 16 kHz with SoXR HQ
when needed. Validation before averaging prevents opposite invalid amplitudes
from cancelling each other. For fractional resampling lengths, padding/truncation
matches the established reference convention `ceil(N × 16000 / source_rate)`.

It rejects empty, over-30-second, nonfinite, or out-of-range input. It does not
peak-normalize, remove noise, or silently truncate an overlong recording. The
recognizer checks its direct Python input too, since a caller can construct
`AudioInput` without using this file loader.

### IPA handling: [`phonetics.py`](../pronouncedfish_engine/phonetics.py)

| Symbol | Responsibility |
| --- | --- |
| `BASE_SYMBOLS`, `MODIFIERS`, `TIE_BAR` | Define the Pasketti output parser's supported base inventory and marks. This is not a universal IPA parser. |
| `canonical_phone(phone)` | Normalizes supported spelling aliases and Unicode NFD for comparisons, retaining meaningful marks and leaving original labels untouched. |
| `tokenize_pasketti(transcription)` | Walks the decoded text. Whitespace creates a boundary; bases start phone tokens; length/nasal marks attach to the previous phone; a tie joins the next base to the preceding token. Rejects unknown or malformed sequences rather than dropping characters. |

For example, `t͡ʃ` is one complete phone token despite multiple Unicode
characters. Untied `a i` are two tokens. Length or nasality does not become an
independent phone. The parser's `boundary` and `pending_tie` state prevents a mark
or dangling tie from accidentally joining phones across a boundary.

### Model adapter: [`pasketti.py`](../pronouncedfish_engine/pasketti.py)

| Method | Responsibility |
| --- | --- |
| `PaskettiRecognizer.__init__(model_dir, device="cpu")` | Verifies the snapshot; lazily loads the local processor and `WavLMForCTC`; rejects incomplete/mismatched checkpoint loading; checks sample rate, CTC blank agreement, and CUDA availability. Uses float32 and evaluation mode. |
| `_result(...)` | Builds the consistent public recognition dictionary, including timing, uncalibrated/unavailable confidence, and mandatory review. A reason marks unassessable output. |
| `recognize(audio)` | Calls `_run(..., keep_evidence=False)` and returns just recognition. |
| `recognize_with_evidence(audio)` | Calls `_run(..., keep_evidence=True)` and returns a `RecognitionRun` for combined assessment. |
| `_run(audio, keep_evidence=...)` | Validates PCM, rejects too-short/long/nearly-silent input, processes the waveform, performs inference, decodes IDs, tokenizes IPA, and optionally constructs CTC evidence. |
| Nested `unassessable(...)` | Packages failed/empty recognition with `evidence=None`, preserving a raw malformed transcription when available. |

Important details inside `_run()`:

- The encoder needs at least 400 samples (25 ms at 16 kHz). RMS below `1e-5`
  is considered nearly silent; this is a basic guard, not a general noise detector.
- The processor normalizes waveform values and makes a tensor. One unpadded
  utterance needs no padding mask. Future padded batches would need explicit masks.
- `torch.inference_mode()` disables gradient tracking; `.eval()` disables training
  behavior. Neither operation trains or fine-tunes the model.
- Float32 avoids the known baseline's half-precision numerical problem. CUDA
  synchronization around timing makes GPU forward timing meaningful.
- `inference_time_ms` measures the forward pass, excluding loading and most
  preprocessing, decoding, analysis, and CTC scoring.
- Evidence uses `logits[0].log_softmax(-1)` on CPU. Phone mappings include supported
  base phone classes; the word separator is listed as ignored. Output modifier
  classes are not falsely advertised as independent complete phones.

### Symbolic comparison: [`analysis.py`](../pronouncedfish_engine/analysis.py)

| Function | Responsibility |
| --- | --- |
| `_tokens(phones, label)` | Copies and validates a nonempty sequence of complete, nonempty tokens with no internal whitespace. A string is rejected to avoid treating its characters as a list of phones. |
| `_feature_table()` | Reads PanPhon's packaged `ipa_all.csv` explicitly as UTF-8, translates signs to numbers, and returns ordered names plus vectors. `lru_cache(maxsize=1)` keeps the table in process memory after its first load. This avoids PanPhon's Windows default-encoding problem without patching installed packages. |
| `_features(expected, recognized, vectors)` | Exact canonical lookup, element-wise absolute differences, then sum. Missing lookup returns unavailable, not a guessed or shortened mapping. |
| `analyze(...)` | Validates targets/inventory, returns unassessable without invented omissions if recognition failed, runs per-variant Jiwer alignment, chooses a variant, expands alignment chunks to phone-pair rows, adds feature comparisons, and returns counts/review metadata. |

No model forward pass, waveform, CTC probability, or network connection is used
by `analyze()`. Re-running it on the same labels and options gives the same
symbolic results regardless of which recording originally produced those labels.

### Acoustic comparison: [`assessment.py`](../pronouncedfish_engine/assessment.py)

| Symbol | Responsibility |
| --- | --- |
| `METHOD` | Versioned identifier for the implemented calculation. |
| `CTCEvidence` | Internal dataclass: normalized `T×C` log probabilities, complete-phone-to-native-ID mapping, blank ID, ignored IDs, and model version. Not serialized into the returned JSON. |
| `RecognitionRun` | Holds a public recognition result and optional internal evidence from the same forward pass. |
| `EvidenceRecognizer` / `recognize_with_evidence(...)` | Small Python `Protocol` describing what `assess()` needs from an adapter; no inheritance or plugin registry required. |
| `_phone_map(evidence, classes)` | Validates class ranges, blank/ignored exclusions, aliases, and one-to-one phone mappings. Rejects conflicting aliases and distinct phones sharing one class. |
| `score_ctc(evidence, target_phones)` | Implements the sequence comparisons in section 5. Returns explicit unavailable output when there is no compatible evidence. |
| Nested `sequence_log_probs(sequences)` | Replicates the one evidence matrix across a candidate batch and obtains unnormalized-by-length sequence log probabilities using CTC loss. |
| `assess(recognizer, audio, expected_phones, ...)` | Orchestrates one recognition/evidence call, analysis, model-version agreement checking, and acoustic scoring against the selected target. Removes evidence from consideration when recognition is unassessable; returns the three public objects. |

### Command line: [`cli.py`](../pronouncedfish_engine/cli.py)

`main()` parses four subcommands and translates them into the library calls above.
Imports occur inside branches so downloading or analyzing saved output does not
need to construct the recognizer. `analyze` reads JSON bytes so Python can detect
UTF-8, UTF-16, UTF-32, and byte-order marks. It expects recognition alone, not the
entire combined assessment bundle.

For recognition/assessment, the CLI loads the model, loads audio, then calls the
chosen operation. JSON is printed to stdout; timing and errors go to stderr.
Redirected JSON escapes IPA as `\u....` so Windows PowerShell encoding conversions
do not corrupt it; a JSON reader restores the characters. Interactive output
displays IPA directly.

| Exit code | Meaning |
| --- | --- |
| 0 | Recognize/analyze returned `ok`, or assess returned acoustic status `ok`; does not mean correct pronunciation. Download completed successfully for `download-model`. |
| 2 | Recognize/analyze unassessable, assess acoustic result partial/unavailable, or an argparse usage error. A partial/unavailable assessment can still print valid JSON. |
| 1 | Caught dependency, file, validation, or runtime failure; inspect stderr. |

`model_load_ms` includes verification and loading. `preprocessing_ms` covers
`load_audio()`. `processing_ms` starts before `load_audio()` and includes it plus
recognition and, for `assess`, the analysis/scoring work. Do not add
`preprocessing_ms` again to `processing_ms` when estimating total time.

## 8. Frontend source, function by function

Everything is in [`frontend-demo.html`](frontend-demo.html): HTML structure, CSS,
an `application/json` examples block, and the executable JavaScript. The large
file size mainly comes from embedded example JSON and base64 WAV audio, rather
than a large JavaScript framework. There are no runtime library downloads,
backend calls, live model inference, or automatic recording uploads.

### Structure, state, and rendering

HTML defines the cards and controls. CSS defines layout, responsive behavior,
phone-kind colors, `heat0/heat1/heat2` cells, unavailable patterns, and plot markers.
Colors illustrate categories and magnitudes, not clinically validated judgments.

| Variable | What it holds |
| --- | --- |
| `examples` | Parsed built-in examples: illustrative phone inputs with real analysis, and actual synthetic recording runs. |
| `currentPayload` | Full current imported/built-in result, possibly the assessment bundle plus fixture metadata. Export uses this value. |
| `current` | The analysis object, either `currentPayload.analysis` or a standalone analysis. Most UI components read it. |
| `selected` | Alignment row index selected in the phone/heatmap/detail views. It is not necessarily the same as a target phone index when there are gaps. |
| `imported` | Whether the source was a user-imported result; used for labels/export naming. |
| `audioUrl` | Temporary object URL for a user-selected audio file; revoked when replaced or cleared. |
| `manualGroups` | Optional display-only target groups entered with the grouping control. Reset on a different result. |
| `featureLabels`, `kindLabels` | Human-readable names for backend feature codes and alignment kinds. |

| Function | What to look for in its body |
| --- | --- |
| `$` | Short form of `document.getElementById`. |
| `el` | Creates a DOM node and sets text/class. Uses `textContent` so imported labels are displayed as text. |
| `message` | Shows a status or error message with an appropriate accessibility role. |
| `phone` | Displays a missing phone as `∅`; this symbol represents a gap, not an IPA sound. |
| `vectorValue` | Displays positive one as `+1`. |
| `loadExample` | Selects built-in payload, labels its provenance, clears old audio, configures groups, attaches embedded audio, resets selection, and renders. |
| `clearAudio` | Pauses/resets the player, clears the file input, and revokes an old object URL. |
| `resetSelection` | Selects the first non-match alignment row, falling back to the first row. |
| `render` | Updates target, counts, summary/variant/review text; calls component renderers and displays the raw JSON. |
| `chooseRow` | Changes selected alignment row, refreshes phone/heatmap/detail/acoustic selection, and preserves scroll/focus. |
| `renderPhones` | Makes clickable expected/recognized phone-pair buttons with kinds and accessible labels. |
| `renderHeatmap` | Finds changed columns and draws absolute feature differences for each aligned pair; shows unavailable cells for gaps/unknown vectors. |
| `renderDetail` | Shows selected pair, distance, original changed feature values, and directional inventory flag. |
| `renderAcoustic` | Draws raw log support, best alternative, and log margin per target position. Missing acoustic output produces an explanation rather than invented scores. |
| `configureGroups` | Resets manual groups and chooses supplied syllables if fixture metadata provides them; otherwise starts with phones. |
| `setProvidedAudio` | Attaches an embedded fixture WAV and labels its synthesis prompt for playback. |
| `targetGroups` | Returns one-phone groups or supplied/manual phone intervals. |
| `groupMetrics` | Computes complete-group mean feature distance and minimum acoustic margin as described in section 6. |
| `referencePayload` | Finds the matching built-in synthetic control and checks selected target sequence and acoustic model version before using its marker. |
| `metricPlot` | Builds the numeric label, fixed-axis bar, current dot, and optional control marker; clamps positions for drawing only. |
| `renderProximity` | Draws each group's two metrics, provenance text, control toggle state, and separately listed additions. Clicking a group selects its first target-alignment row. |
| `validateAnalysis` | Checks shape, tokens, indices, counts, vector lengths/values, per-coordinate differences, and their sum. Rejects recognition-only input with guidance. |
| `validateDemoMetadata` | Checks optional synthetic labels, positive contiguous supplied groups covering the selected target, and bounded WAV data URL format. This is fixture metadata, not an engine inference result. |
| `validateAcoustic` | Checks supported method/unit/status, target agreement, model-version agreement when recognition is present, and finite score values. Unsupported formats are rejected. |
| `loadImported` | Extracts and validates analysis/acoustic/metadata before replacing state, then resets controls/audio/selection and renders. |
| `parseFileBytes` | Decodes UTF-8 or BOM-marked UTF-16 LE/BE bytes, then parses JSON. Unlike the Python reader, it does not implement UTF-32 decoding. |

### Events: what happens when you click something

| Control / event | Sequence |
| --- | --- |
| Example dropdown `change` | `loadExample()` → reset state/audio/groups → `render()`. |
| Phone or heatmap row click | `chooseRow()` → refresh linked views. |
| Changed-features checkbox | `renderHeatmap()` only. |
| Group mode / reference checkbox | `renderProximity()` only. |
| Apply custom groups | Validate positive integer counts summing to target length → set contiguous `manualGroups` → render proximity. Does not change exported engine output. |
| Integration navigation link | Opens the explanatory `<details>` panel. |
| JSON file selection | Enforce 2 MiB limit → read bytes → `parseFileBytes()` → `loadImported()`. Failure shows an error and preserves the prior result. |
| Download button | Serialize `currentPayload` → create JSON `Blob` → trigger local download → revoke its temporary URL. Original fixture metadata/audio are retained if present. |
| Audio file selection | Enforce 50 MiB playback limit → create object URL → attach player. Analysis and displayed scores stay unchanged. |
| Audio player error | Show a format/playback error. |
| Initial page load | Select the bundled `sunset-substitution` example, or the first example if absent. |

This is a result viewer. A full application would need its own recording/session
flow and a way to call the Python library. There is no implemented browser model,
HTTP endpoint, persistent patient database, or application backend hidden here.

## 9. Model files, dependencies, and generated files

### Files under `models/pasketti-phonetic/`

| File | Role |
| --- | --- |
| `model.safetensors` | Pretrained neural-network parameters. This is where the learned recognition behavior mainly lives. |
| `config.json` | Network architecture and model settings such as output vocabulary size and blank/pad ID. It is not code implementing our distance calculation. |
| `preprocessor_config.json` | Expected sample rate and waveform processing settings. |
| `vocab.json` | Model token text → native ID mapping. Never assume IDs match those of another model. |
| `tokenizer_config.json` | Tokenizer behavior/configuration. |
| `special_tokens_map.json` | Special token definitions. |
| `added_tokens.json` | Additional tokenizer entries supplied with the upstream snapshot. |
| `README.md` | Upstream model card; see also our [baseline notes](model-baseline.md). |
| `pronouncedfish-model.json` | Locally generated version/hash manifest used by verification. It is not model training output. |

Do not manually tweak the downloaded vocabulary/configuration to alter feedback:
verification will detect changes, and token IDs must agree with trained weights.
The current adapter expects the pinned Pasketti snapshot, not an arbitrary model
directory with similarly named files.

### Package and environment files

| File / dependency | Why it exists |
| --- | --- |
| [`pyproject.toml`](../pyproject.toml) | Package/build metadata, Python version range, pinned dependencies, console command, package discovery, and pytest configuration. |
| [`environment.yml`](../environment.yml) | Creates conda Python 3.12 and installs this package editable with analysis/test extras. The actual environment lives outside the repository. |
| [`.gitignore`](../.gitignore) | Keeps downloaded weights, recordings/results, generated PDF, Python/build caches, and other local artifacts out of normal version control. |
| PyTorch (`torch`) | Tensor operations, model inference, log-space calculations, and CTC dynamic programming. |
| Transformers | Loads the pretrained WavLM model and its processor/tokenizer. |
| NumPy | Waveform arrays and validation. |
| SoundFile / SoXR | Audio file decoding / resampling. |
| Jiwer / PanPhon (`analysis` extra) | Token alignment / fixed linguistic feature data. |
| pytest / librosa (`dev` extra) | Test execution / reference resampling comparison. Librosa is not used by the runtime audio loader. |

`pip install -e ".[dev,analysis]"` means install the package in editable mode plus
both optional dependency groups. Source edits are then used without reinstalling
the package. This is installation, not training.

`__pycache__`, `.pytest_cache`, `build`, and `*.egg-info` are tool-generated files.
`models/` contains downloaded assets; `examples/synthetic-soa/` contains generated
fixtures. None is an extra recognition stage. The earlier browser package was
removed; the current browser demonstration is the single HTML file in `docs/`.

## 10. Synthetic examples and tests

### Fixture generation

| Script | What it does |
| --- | --- |
| [`New-SmokeAudio.ps1`](../scripts/New-SmokeAudio.ps1) | Uses Windows System.Speech and Microsoft David Desktop to synthesize the smoke-test sentence to `sample.wav`; disposes the synthesizer. |
| [`New-ComparisonAudio.ps1`](../scripts/New-ComparisonAudio.ps1) | Synthesizes six recordings: Seat, Sheet, See, Seats, Sunset, and Sun sat. Writes `manifest.json` with targets, intended changes, and supplied syllable groups. Uses a slightly slowed adult synthetic voice, not a child voice. |
| [`Assess-ComparisonAudio.py`](../scripts/Assess-ComparisonAudio.py) / `main()` | Reads that manifest, loads one resident model, assesses each WAV, attaches `demo_metadata` and base64 audio, writes individual/aggregate JSON and a summary, then bundles the files in a ZIP. Does not modify the HTML automatically. |

The synthesis prompt expresses an intended change; the model's actual prediction
may differ. `demo_metadata` is optional fixture annotation added by the script,
not an extra inference layer or standard field emitted by `assess()`.
The aggregate `comparison-examples.json` is an array for embedding examples; import
an **individual** fixture JSON into the frontend. Existing built-in examples are
embedded copies, so regenerating files does not silently update the HTML.

### What each test module checks

| Test file | Meaningful coverage |
| --- | --- |
| [`test_audio.py`](../tests/test_audio.py) | Channel mixing, invalid samples before mixing, duration limits, rejection of URL sources, and direct SoXR output versus reference including fractional lengths. |
| [`test_phonetics.py`](../tests/test_phonetics.py) | Complete phone/mark preservation and rejection of malformed decoded IPA. |
| [`test_recognition.py`](../tests/test_recognition.py) | Controlled model outputs exercise CTC decoding, blank-separated repeats, invalid/empty results, PCM guards, nonfinite logits, and offline missing-model behavior. These are behavior tests, not recognition-accuracy measurements. |
| [`test_analysis.py`](../tests/test_analysis.py) | Known feature distances, gaps without fake zero distances, variants/ties, aliases, retained marks, unknown phones, indices/repeats, directional inventories, offline/input-preservation behavior, and saved JSON encodings/errors. |
| [`test_assessment.py`](../tests/test_assessment.py) | Compares CTC scores against exhaustive tiny-path enumeration; same decoded label with changed evidence; separator marginalization; native IDs and aliases; unsupported/impossible/partial cases; evidence validation; replacement adapter and one-pass orchestration; CLI bundle output. |
| [`test_integration.py`](../tests/test_integration.py) | Optional real local model/audio inference with network connections forbidden, checking actual recognition and evidence. Requires explicit environment paths. |

The path-enumeration test helper `enumerate_probability()` is a small independent
oracle for CTC math, not the production scoring algorithm. Helpers such as
`evidence()`, `recognition()`, `recognizer()`, `set_frames()`, and `speech_buffer()`
construct deterministic fixtures so tests can isolate one behavior.

Passing tests supports implementation behavior. It does not establish recognition
accuracy on children, clinical usefulness, calibrated thresholds, distortion
detection, or the quality of a future replacement model. Historical test counts
and manual frontend checks are recorded in [verification notes](recognition-verification.md).

## 11. Replacing the recognition model

The usable extension point is the `EvidenceRecognizer` protocol in Python:

```python
class MyRecognizer:
    def recognize_with_evidence(self, audio):
        # Run your actual model and produce the documented recognition fields.
        recognition = ...
        # Return compatible normalized CTC evidence, or None for a non-CTC model.
        evidence = ...
        return RecognitionRun(recognition=recognition, evidence=evidence)

result = assess(my_recognizer, audio, expected_phones)
```

This is a sketch of the required boundary, not a runnable model implementation.
The adapter must handle its model's sample rate/processing, decoding, complete
phone inventory, and unique model version. For acoustic scoring it must supply
normalized `T×C` log probabilities and correct one-phone-to-one-class IDs. The
recognition and evidence versions must agree. For non-CTC models, `evidence=None`
keeps symbolic analysis usable and reports acoustic assessment unavailable.

PanPhon remains usable only where the emitted phones have exact table entries.
A different script, inventory, or representation can require changes to the
adapter or a separately designed analysis method. Do not pretend arbitrary hidden
embeddings are PanPhon feature vectors or compatible CTC probabilities.

The current CLI constructs `PaskettiRecognizer` explicitly; it has no model
selection flag or automatic adapter discovery. A future adapter can first be used
through `assess()` from Python, then be wired into the CLI/application when needed.
No training, fine-tuning, dataset preparation, or replacement model is implemented
by declaring this protocol. The existing fake-adapter test checks this boundary.

## 12. Run, inspect, and troubleshoot

From `src/engine/` in your conda environment:

```powershell
conda activate phoneme-engine
python -m pip install -e ".[dev,analysis]"
# Download once if the pinned assets are not already present:
python -m pronouncedfish_engine download-model

# Recognition alone, then analysis of its saved labels:
python -m pronouncedfish_engine recognize sample.wav > recognition.json
python -m pronouncedfish_engine analyze recognition.json --expected-phones ð ə ɹ æ b ɪ t s ɪ t s ɪ n ð ə s ʌ n > analysis.json

# All three outputs, with fresh evidence from audio:
python -m pronouncedfish_engine assess sample.wav --expected-phones ð ə ɹ æ b ɪ t s ɪ t s ɪ n ð ə s ʌ n > assessment.json
Get-Item .\assessment.json
$result = Get-Content -Raw -Encoding UTF8 .\assessment.json | ConvertFrom-Json
$result.analysis.edit_counts
$result.acoustic_assessment.phone_scores | Format-Table
```

These target phones belong to the generated “The rabbit sits in the sun” sample.
Use the appropriate supplied target for your own recording. For BOM-marked output
from older PowerShell, `Get-Content` detects the BOM; the engine's JSON byte reader
also handles it. JSON escape sequences such as `\u0259` are valid encodings of IPA.

For a debugger, put breakpoints in `cli.main`, `load_audio`,
`PaskettiRecognizer._run`, `analyze`, and `score_ctc`. Watch `samples.shape`,
`logits.shape`, `phones`, `comparison.alignments`, `differences`, and
`probabilities` in that order. In browser DevTools, inspect `currentPayload`,
`current.alignment`, and `groupMetrics(currentPayload, targetGroups()[0])`.
Do not paste private recording arrays into logs simply to inspect a shape.

| Symptom | Explanation / next check |
| --- | --- |
| Missing `--expected-phones` | Analysis needs a caller-supplied target. The recording's intended word is not inferred by this command. |
| Empty-looking `assessment.json` | Check its absolute location and size. `>` writes relative to the shell's current directory; `src/assessment.json` and `src/engine/assessment.json` differ. Wait for the command to finish and inspect stderr/exit status. |
| Timing appears but terminal has no JSON | With `> assessment.json`, JSON goes to the file while stderr timing remains visible. |
| Model missing or hash mismatch | Run explicit `download-model` for the pinned snapshot. Recognition intentionally does not repair/download silently. |
| Dependency error | Check `python --version` and `python -m pip --version` point to the active conda environment; install the extras there. |
| Recognition-only JSON rejected by frontend | Import `analysis.json` or the combined `assessment.json`. Recognition alone has no alignment to draw. |
| All labels match but acoustic margins differ | Expected: greedy labels discard probability information retained by the acoustic scorer. |
| A phone distance is unavailable | Inspect gap status or exact PanPhon mapping. Missing data is not zero distance. |
| Acoustic output unavailable | Read `review_reason` and row `reason`; common causes are missing CTC capability, multi-class target phones, impossible paths, limits, or unassessable recognition. |
| A bar stops moving for a large value | The plotted axis is clipped; read its numeric label or raw JSON. |
| Uploaded audio seems to have old scores | The HTML only plays the new file. Run the Python engine on that file and import the corresponding result. |

Run `python -m pytest -q` for unit checks. To opt into the real-model test:

```powershell
$env:PRONOUNCEDFISH_MODEL_DIR = (Resolve-Path models\pasketti-phonetic).Path
$env:PRONOUNCEDFISH_SMOKE_AUDIO = (Resolve-Path sample.wav).Path
python -m pytest -q
```

When changing behavior, follow the same boundary as the change: audio changes
need waveform checks; token changes need mark/alias tests; feature changes need
known-vector examples; acoustic changes need independent CTC probability checks;
frontend changes need import, unavailable-state, numeric, and responsive checks.

## Source references

These links describe the upstream building blocks; the source files linked above
define the specific behavior implemented here.

- [Pinned Pasketti model](https://huggingface.co/drivendata/pasketti-phonetic/tree/675dfe392a2af7050f1374eeab4458cb1f003b3e)
- [PanPhon repository and feature data](https://github.com/dmort27/panphon)
- [PanPhon paper](https://aclanthology.org/C16-1328/)
- [Jiwer usage and alignment output](https://jitsi.github.io/jiwer/usage/)
- [PyTorch CTC loss documentation](https://pytorch.org/docs/2.6/generated/torch.nn.functional.ctc_loss.html)
- [CTC-based goodness of pronunciation research](https://www.isca-archive.org/interspeech_2024/cao24b_interspeech.html)

The published methods motivate the work; our restricted scorer should be identified
by its own method name rather than presented as a reproduction of a full paper.
