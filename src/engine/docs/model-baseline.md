# First recognition baseline

Decision recorded 2026-10-28: implement **drivendata/pasketti-phonetic** as the
local Python baseline. It is already a trained phonetic recognizer; no new model
training is needed to establish audio-to-phone inference.

| Candidate | Evidence and decision |
| --- | --- |
| [Pasketti Phonetic](https://huggingface.co/drivendata/pasketti-phonetic) | Child-speech WavLM Large fine-tune producing IPA. Selected for population relevance and available trained weights. Published overall PER is 33%; performance is worse for under-5s and atypical speech. That evidence does not establish our 87% target. |
| [wav2vec2-lv-60-espeak-cv-ft](https://huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft) | Apache-2.0 phonetic checkpoint trained on multilingual Common Voice. A possible comparison baseline; its card does not demonstrate accuracy for our child population, and it is also a large encoder. Not implemented here. |
| [WavLM Base Plus](https://huggingface.co/microsoft/wavlm-base-plus) | Smaller encoder candidate, with no pretrained phonetic head/tokenizer in this checkpoint. It requires labeled phonetic fine-tuning or distillation before it can replace the baseline. It is not a working deployment substitute. |

## Reproducible identity

- Revision: `675dfe392a2af7050f1374eeab4458cb1f003b3e`.
- Weight SHA-256: `5b3eb5a1b7e03e25dc816ae891f18eeffa239d715a5868010b07973a077b5134`.
- Published [asset metadata](https://huggingface.co/api/models/drivendata/pasketti-phonetic?blobs=true):
  315,509,495 FP32 parameters, 1,262,097,724-byte safetensors file.
- Runtime pins follow the publisher's Transformers 4.57.6 / PyTorch 2.6.0
  recipe. Our audio loader calls SoXR 1.1.0 HQ directly with NumPy 1.26.4,
  preserving librosa 0.11.0's `soxr_hq` waveform and output-length convention.
  Direct resampling avoids loading librosa's resampling dependency chain on the
  first recording. See `pyproject.toml` for the direct dependencies.

Weights are explicitly downloaded, checked, and then loaded with local-files-only
settings. The loader uses the standard Transformers WavLM implementation, not
remote Python code, and rejects incomplete checkpoint loads. It keeps FP32 because
the publisher warns of half-precision NaNs. One utterance is processed per call.
Since this call has no padding, the processor omits the redundant padding mask.
This avoids the upstream mixed-mask-type warning without suppressing warnings
or patching PyTorch. Any future padded-batch implementation must handle masks
explicitly again.

## Phone inventory and decoding

The pinned vocabulary has 55 model classes: CTC blank, word separator, and 53
characters including combining marks. `<unk>` is an extra tokenizer entry outside
the 55 output classes. See the pinned
[vocabulary](https://huggingface.co/drivendata/pasketti-phonetic/blob/675dfe392a2af7050f1374eeab4458cb1f003b3e/vocab.json).

Greedy CTC decoding uses Hugging Face's processor, preserving blank-separated
repetitions. The engine keeps the raw transcription and groups nasalization,
length marks, and explicit tie-bar sequences into complete tokens. Word spaces
are not phones. Untied adjacent vowels remain separate. The model's `ʧ` and `ʤ`
affricates remain single tokens, and its `g`, `r`, and `ɹ` spellings are preserved.
No expected-pronunciation correction, Unicode compatibility normalization, or
unstated phone-alphabet mapping is applied. Malformed marks make a result
unassessable while retaining its raw transcription for review.

Pasketti's published evaluation normalizes several marks and approximates PER
with character error rate. Our future evaluation must define token-level PER
explicitly; do not compare the two scores as if their conventions were identical.

## Analysis and frontend built on the recognition baseline

The recognition model remains unchanged. `analysis.py` adds descriptive comparison
of its complete phone tokens with caller-supplied target pronunciations. Jiwer
4.0.0 supplies token alignment, and PanPhon 0.22.2 supplies the 24-column feature
table. Both are optional `analysis` dependencies; no second model is loaded.

PanPhon data is read directly from its installed CSV as UTF-8 because the default
loader fails on Windows cp1252. The vectors are symbolic descriptions of IPA
categories, not WavLM's learned acoustic representations. Feature normalization
is explicit and confined to comparison: NFD plus `g`/`ɡ`, `ʧ`/`t͡ʃ`, and
`ʤ`/`d͡ʒ` spelling equivalences. Recognition output is preserved.

The official [Pasketti notebook](https://colab.research.google.com/drive/1Gj64XMfPThMuqCw1YD2CaYWLW6kg8hAH)
uses human produced-phone references for model-error comparisons. Its colors and
phone error rate do not measure a child's difference from a practice target.
Our analysis uses caller-supplied targets/variants and reports candidate S/O/A
differences; acoustic distortions are not assessed. No clinical severity or
calibrated probability follows from a feature distance.

`docs/frontend-demo.html` is an offline renderer of six illustrative engine
outputs and imported JSON. Audio selection enables playback only; it does not
perform inference. The notebook's Colab-backed inference and our static demo
are not browser/iPad inference implementations. See the
[team walkthrough](PronouncedFish-Engine-Walkthrough.html) for the full discussion.

## Licensing and deployment limits

The model card declares **BigCode OpenRAIL-M**, separate from the repository's
GPL source-code license. Its [license terms](https://huggingface.co/spaces/bigcode/bigcode-model-license-agreement/blob/main/app.py)
contain use restrictions and redistribution conditions, including preserving
documentation/notices and providing the license. They prohibit medical advice
intended to replace professional care. This baseline provides reviewable
transcriptions, not automated diagnosis. We download the model card alongside
the weights and do not redistribute weights in source or package artifacts.
Product redistribution requires a separate review of the actual model terms.

The checkpoint and inference recipe are public; that does not establish that
the original child-speech training corpus can be obtained or retraining reproduced
under the same permissions. No patient data or training corpus was acquired here.

ONNX export and Safari execution have not been tested. Large FP32 weights and
WavLM's relative-position computations are concrete deployment concerns. Preserve
this baseline for recognition comparisons while investigating an exported model
or trained smaller candidate. Browser compatibility and the 10-second target
must be measured on the actual target device.
