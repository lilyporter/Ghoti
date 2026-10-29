# Experimental acoustic assessment and model expansion

Implemented 29 October 2026. This is an audio-dependent research baseline, not
validated pronunciation correctness, confidence, clinical severity, or distortion
detection. Existing recognition and analysis contracts are unchanged.

## Three separate results

| Result | Evidence used | Interpretation |
| --- | --- | --- |
| `recognition` | Audio through the model | Estimated produced phones and review state. |
| `analysis` | Recognized labels and supplied target/variants | Candidate S/O/A differences and fixed PanPhon category distances. |
| `acoustic_assessment` | Frame-level CTC log probabilities and the selected target | Relative support for the target versus restricted single-phone replacements. |

`recognize` still returns recognition alone. `analyze` still compares saved
recognition JSON. The new `assess` command returns all three objects from **one
neural-network forward pass**. Frame matrices stay in memory; they are not
serialized into JSON or saved as an automatic recording cache.

## Run it

From `src/engine/`, with the model already downloaded:

```powershell
conda activate phoneme-engine
python -m pip install -e ".[dev,analysis]"
python -m pronouncedfish_engine assess sample.wav --expected-phones ð ə ɹ æ b ɪ t s ɪ t s ɪ n ð ə s ʌ n > assessment.json
```

The target above belongs to the generated “The rabbit sits in the sun” fixture.
Use the pronunciation of your actual practice item for another recording. The
same repeatable `--acceptable-variant` and `--supported-substitution` options as
`analyze` are available. Symbolic analysis selects the closest supplied variant;
the acoustic scorer uses that same variant, not an independent acoustic reranking.

CLI exits: 0 if every acoustic phone score is available; 2 for partial/unavailable
assessment (JSON still contains recognition and analysis); 1 for execution errors.
An unsupported scoring target does not invalidate a usable recognition result.
Redirected Unicode escaping and UTF-16-safe file handling remain unchanged.

```python
from pronouncedfish_engine import PaskettiRecognizer, assess, load_audio

recognizer = PaskettiRecognizer("models/pasketti-phonetic")  # keep alive
bundle = assess(
    recognizer,
    load_audio("sample.wav"),
    expected_phones=["ð", "ə", "ɹ", "æ", "b", "ɪ", "t", "s", "ɪ", "t", "s",
                     "ɪ", "n", "ð", "ə", "s", "ʌ", "n"],
)
```

Open `assessment.json` in [frontend-demo.html](frontend-demo.html). Its separate
acoustic panel shows raw log support and margins. Save preserves the whole bundle.
There are six symbolic examples and one real-model synthetic-audio snapshot. The
page still cannot run inference; loading audio enables playback only.

## What the method actually calculates

Method identifier: `ctc-single-substitution-log-support-v1`.

Let `X` be the recording and `L` the complete selected target phone sequence.
For each position `i`, construct `L(i ← q)` for every model-declared candidate
phone `q`. The candidate set includes the target at that position.

```text
target_logp = log P_CTC(L | X)

conditional_log_support[i] = target_logp
    − logsumexp_q log P_CTC(L(i ← q) | X)

best_alternative = argmax over q different from the target
    log P_CTC(L(i ← q) | X)

log_margin_vs_best_alternative[i] = target_logp
    − log P_CTC(L(i ← best_alternative) | X)
```

PyTorch's CTC forward calculation sums paths, including blanks and repeats. No
single forced segment boundary is assumed. Computation uses detached CPU float64
log probabilities and checks normalization/finite values. Candidate replacement
sequences are batched per position. Different candidate sequences can have
different sets of valid repeat/blank paths; the CTC calculation retains that.

- Log support is at most zero. Closer to zero means greater relative support
  **within this candidate set and fixed surrounding target**.
- A positive margin favors the target over the best non-target alternative;
  a negative margin favors that alternative. Neither is a correctness threshold.
- The sequence log probability is length- and model-dependent. It is not a
  sentence quality score and should not be compared directly across models.
- The best alternative is a counterfactual under fixed target context, not an
  independent transcription or a confirmed substitution by the child.

The same winning phone label can have different acoustic scores for different
recordings. This is the new information beyond fixed PanPhon lookup.

This is **not the complete published segmentation-free GOP algorithm**: the
denominator permits only one replacement at a fixed target position. It has no
insertion/deletion alternatives, learned phone thresholds, segment-length
normalization, or clinical calibration. It does not independently predict the
24 PanPhon features. Its log support must not be renamed “percent correct.”

## Supported representation and explicit limits

Pasketti supplies one output class per basic phone/affricate, plus classes for
marks and a word separator. The adapter declares the complete single-class
phones it can score and merges the word-separator probability into CTC blank
for phone-only sequence scoring. Other output classes retain their mass; they
are not silently renormalized into phone candidates.

Comparison spelling normalization is shared with analysis: NFD and `g`/`ɡ`,
`ʧ`/`t͡ʃ`, `ʤ`/`d͡ʒ` equivalents. Distinct sounds such as `r` and `ɹ` stay distinct.

Pasketti targets requiring multiple native classes, such as a nasalized vowel,
length-marked phone, or tied sequence, make acoustic assessment unavailable for
the whole selected sequence. We cannot hold the surrounding sequence fixed if
it has no supported encoding. Recognition and symbolic analysis are still returned.
Another model can support a complete multi-character phone if it is ONE native
class in that model. No mark is stripped to manufacture a score.

Limits are 128 target phones, 2–128 distinct candidate classes, and 2,000 frames.
These bound this CPU research calculation; they are not clinical usability limits.
Impossible target paths return unavailable. If only some positions have finite
non-target alternative paths, the result is partial. No NaN/Infinity is serialized.
Short, silent, or otherwise unassessable recognition receives no acoustic scores.

## Acoustic result contract

Top-level `assess` JSON has exactly `recognition`, `analysis`, and
`acoustic_assessment`. The first two keep their existing fields.

| Acoustic field | Meaning |
| --- | --- |
| `status` | `"ok"`, `"partial"`, or `"unavailable"`; these describe score availability, not pronunciation. |
| `method` | Versioned method identifier above. |
| `model_version` | Model identity; preserved even when scoring is unavailable in the combined workflow. Standalone `score_ctc(None, ...)` has no model identity and returns `null`. |
| `calibration_status` | `"uncalibrated"` if any phone scores exist; otherwise `"unavailable"`. |
| `score_unit` | `"natural_log"`. |
| `target_phones` | Selected target used for scoring, preserving its supplied spellings. |
| `candidate_phones` | Sorted canonical names of the model's declared competitor set. |
| `target_sequence_log_probability` | Phone-only full-target CTC log probability, or `null` if unavailable. |
| `phone_scores` | Ordered per-target-phone evidence; empty if no target calculation can be made. |
| `requires_review` | Always `true`. |
| `review_reason` | Method limitations or explanation of unavailable evidence. |

Each entry in `phone_scores` contains:

| Field | Meaning |
| --- | --- |
| `expected_index` | Zero-based index into `target_phones`, not a timestamp. |
| `expected_phone` | Supplied target phone at that index. |
| `status` | `"ok"` or `"unavailable"`. |
| `conditional_log_support` | Restricted normalized log support, or `null`. |
| `best_alternative_phone` | Canonical spelling of the highest-scoring non-target candidate, or `null`. |
| `log_margin_vs_best_alternative` | Signed log-probability difference, or `null`. |
| `reason` | `null` for an available row; explanatory text otherwise. |

The `assess` CLI's `processing_ms` includes preprocessing, recognition, symbolic
analysis, and acoustic scoring. Recognition's `inference_time_ms` still measures
only the network forward pass. No additional aggregate clinical score is returned.

## Adding our own model

The small `EvidenceRecognizer` protocol is exercised by the current workflow and
tests. It requires `recognize_with_evidence(audio) -> RecognitionRun`:

```python
from pronouncedfish_engine import CTCEvidence, RecognitionRun

# Inside an adapter, after the model's own preprocessing and forward pass:
run = RecognitionRun(
    recognition=recognition_result,  # existing complete-phone result contract
    evidence=CTCEvidence(
        log_probs=frame_log_probs,  # shape: time frames × native classes
        phone_token_ids=complete_phone_to_native_id,
        blank_id=native_blank_id,
        model_version=recognition_result["model_version"],
        ignored_token_ids=word_separator_ids,
    ),
)
```

No Pasketti numeric IDs or hidden-vector dimensions are assumed in `score_ctc`.
An adapter owns its vocabulary, preprocessing, decoding, and complete-phone map.
Conflicting normalized mappings, reused IDs for distinct phones, invalid special
IDs, and evidence/recognition model-version mismatches are rejected. Future models
must return complete tokens compatible with the shared IPA comparison convention.

The CLI still constructs `PaskettiRecognizer`; model selection is not a registry
or a new CLI option. Use another adapter through Python `assess(adapter, ...)`.
Pasketti's loader still verifies the pinned snapshot: arbitrary custom weights
cannot simply be substituted via `--model-dir`. A custom adapter owns loading,
asset verification, and truthful model-version metadata for its own checkpoint.

A non-CTC model can return `RecognitionRun(recognition_result, None)`: symbolic
analysis remains available while CTC scoring explicitly returns unavailable.
Its own assessment method would need a separately identified implementation and
renderer support; nothing is relabelled as GOP. There is no plugin registry,
training framework, or empty model folder.

Three possible training projects remain distinct:

1. Fine-tune recognition using transcriptions of the sounds actually produced.
   Do not train a mispronounced recording against the correct practice target
   and then claim to preserve the child's substitutions.
2. Train a smaller assessment/calibration head using clinician judgments and
   acoustic features. Splits must hold out speakers, not only recordings.
3. Predict phonological feature probabilities directly from audio. This needs
   a suitable feature inventory/supervision and child-speech evaluation; the
   current symbolic heatmap is not this model.

Raw scores and thresholds are model-, method-, inventory-, and population-specific.
Replacing a model requires renewed assessment/calibration. No training data or
clinical validation has been obtained as part of this implementation.

## Research basis and next experiments

- [Cao et al., CTC pronunciation assessment (2024)](https://www.isca-archive.org/interspeech_2024/cao24b_interspeech.pdf)
  and [segmentation-free extension (2026 version)](https://arxiv.org/html/2507.16838v3)
  motivate sequence-based scoring. This implementation is a narrower independent baseline.
- [Hair et al. (2021)](https://www.isca-archive.org/interspeech_2021/hair21_interspeech.pdf)
  study learned posterior-based assessment on child speech therapy recordings.
- [Context-aware CTC (2026)](https://aclanthology.org/2026.bea-1.3/)
  shows why recognition training and posterior behavior matter for assessment.
- [Phonet (2019)](https://www.isca-archive.org/interspeech_2019/vasquezcorrea19_interspeech.pdf)
  demonstrates direct phonological-posterior prediction; its original Spanish
  models are not a validated English-child solution.

Next compare this restricted acoustic baseline against label matching and human
ratings on acceptable productions, substitutions, and same-label audible errors.
Measure false alarms/missed errors and per-phone behavior on held-out children.
More complete GOP, insertions/deletions, multi-class phones, calibrated decisions,
direct feature prediction, and target-device performance remain research work.
