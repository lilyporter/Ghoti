# PronouncedFish source code

[engine/](engine/README.md) contains the working local Python phonetic recognizer.
It is a reusable package around Pasketti, with audio preparation, phone decoding,
and a command-line entry point. Its optional analysis module compares phone
tokens with target pronunciations and returns candidate differences and feature
distances for heatmaps. The rest of the application can import both.

The [standalone frontend demo](engine/docs/frontend-demo.html) renders example or
imported analysis as phone comparisons and an interactive feature heatmap.
Browser/iPad inference and production frontend integration remain future work.

| Component | Current state |
| --- | --- |
| Recognition | Local pretrained Pasketti inference; WAV/FLAC → IPA and complete phone tokens. |
| Analysis | Target alignment, acceptable variants, candidate substitutions/omissions/additions, and PanPhon feature comparisons. |
| Acoustic evidence | Experimental CTC single-substitution sequence support from audio; uncalibrated and separate from PanPhon. |
| Model expansion | Small evidence-adapter boundary used by assessment; a future CTC model supplies its own vocabulary/IDs, and non-CTC evidence can be unavailable. |
| Frontend | One offline HTML prototype; symbolic examples, a synthetic acoustic snapshot, imported results, feature heatmap, and local playback. |
| Product integration | Recording workflow, backend/browser inference connection, patient/session storage, and correction history are not implemented. |
| Validation | 85 software tests pass, including offline real-model inference/acoustic scoring. Intended-population accuracy, clinical interpretation, and iPad performance remain unverified. |

Start with the [engine README](engine/README.md) for commands and result fields.
The [team walkthrough](engine/docs/PronouncedFish-Engine-Walkthrough.html) explains
the complete flow, design decisions, phone pairs, SODA candidates, and feature
heatmaps. A PDF copy is available locally beside the HTML; PDFs are ignored by Git.
See [acoustic assessment and model expansion](engine/docs/acoustic-assessment.md)
for the new experimental method, result fields, and adapter contract.
See [verification evidence](engine/docs/recognition-verification.md) for measured
behavior and [traceability](TraceToDesign.md) for the scope of implemented requirements.
