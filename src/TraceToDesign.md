# Traceability between code files and design modules

The current engine implements local Python recognition, descriptive target
analysis, and a standalone frontend prototype. These mappings describe
responsibilities; they do not establish clinical accuracy or device acceptance.

| File | Responsibility | Requirements / context |
| --- | --- | --- |
| [recognition.py](engine/pronouncedfish_engine/recognition.py) | Concrete audio input and recognition result types | FR-AC3, FR-SA3 |
| [pasketti.py](engine/pronouncedfish_engine/pasketti.py) | Local FP32 inference, CTC decoding and review status | Recognition portion of FR-SA1; calibration and accuracy remain unverified |
| [audio.py](engine/pronouncedfish_engine/audio.py) | WAV/FLAC loading, mono conversion, resampling and basic checks | Partial FR-AC3; noise and clipping checks remain limited |
| [phonetics.py](engine/pronouncedfish_engine/phonetics.py) | Complete phone tokens for target comparison | Preserves affricates and modifiers rather than comparing raw Unicode characters |
| [analysis.py](engine/pronouncedfish_engine/analysis.py) | Align target and recognized tokens; select supplied acceptable variants; report candidate differences and feature vectors | Descriptive part of FR-SA1 and feature comparison supporting FR-RDV5; acoustic distortions and clinical substitution accuracy are not established |
| [assessment.py](engine/pronouncedfish_engine/assessment.py) | Model-evidence boundary and restricted single-substitution CTC sequence support | Experimental acoustic evidence; no numerical correctness calibration, full GOP-SF replication, or clinical substitution validation |
| [cli.py](engine/pronouncedfish_engine/cli.py) | Download, recognition, saved-JSON analysis, and combined assess commands | Reviewable local workflow; assess returns recognition, analysis, and acoustic evidence from one forward pass |
| [assets.py](engine/pronouncedfish_engine/assets.py) | Explicit download and local verification of a pinned model | Reproducible model identity; no audio upload |
| [frontend-demo.html](engine/docs/frontend-demo.html) | Render phone pairs, symbolic feature map, and a separate acoustic evidence panel | Prototype demonstration for FR-RDV5; acoustic values have no clinical thresholds, and inference is not connected live |

The supplied SRS identifies the 87% accuracy and under-10-second targets. These
remain unverified. Target analysis is implemented, but candidate differences are
not validated clinical findings. The caller must provide practice pronunciations,
acceptable variants, and any approved directional substitution inventory. Inventory
membership does not establish validity.

The optional CTC layer uses frame probabilities from audio. Its restricted
single-substitution scores are distinct from symbolic Manhattan distance and do
not implement acoustic feature prediction or distortion detection. Its model
adapter boundary is exercised by current code and a replacement-model test; no
plugin registry, training pipeline, or additional trained model is included.

Accepted-variant handling implements the comparison behavior described by
FR-SA2. FR-SA3's calibrated numerical confidence and validation-derived rejection
threshold are not implemented; explicit review/unassessable states do not satisfy
that requirement. Token indices also do not yet supply FR-SA1's word-position
labels for multiword items.

The SRS's feature representation and Manhattan-distance calculation appear in
[SRS.tex](../docs/SRS/SRS.tex), along with FR-RDV5's closeness heatmap. The
implemented distance compares symbolic PanPhon categories; it is not a calibrated
severity measure or a measurement of learned acoustic embedding distance.

Browser inference, iPad execution, microphone capture integration, patient/session
storage, and correction provenance remain unimplemented. The HTML prototype reads
results locally and offers audio playback only. A future development backend
connection would be a separate implementation choice and would not by itself
satisfy a production requirement for inference on the user's device.
See [model notes](engine/docs/model-baseline.md) and
[recorded verification](engine/docs/recognition-verification.md).
