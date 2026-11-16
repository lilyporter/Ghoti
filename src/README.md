# PronouncedFish source code

[engine/](engine/README.md) contains the working local Python phonetic recognizer.
It is a reusable package around Pasketti, with audio preparation, phone decoding,
and a command-line entry point. Its optional analysis module compares phone
tokens with target pronunciations and returns candidate differences and feature
distances for heatmaps. The rest of the application can import both.

The [laptop-hosted iPad demo](demo/README.md) uses React and FastAPI with a Vite
`/api` proxy. It plays one of ten different words recorded by children on the iPad and runs
live recognition and target comparison on the laptop after playback.

| Component | Current state |
| --- | --- |
| Recognition | Local pretrained Pasketti inference; WAV/FLAC → IPA and complete phone tokens. |
| Analysis | Target alignment, acceptable variants, candidate substitutions/omissions/additions, and PanPhon feature comparisons. |
| Acoustic evidence | Experimental CTC single-substitution sequence support from audio; uncalibrated and separate from PanPhon. |
| Demo | React page on the iPad; FastAPI and live recognition on the laptop. |
| Remaining work | Browser-only inference, patient/session features, and clinical validation. |

Start with the [engine README](engine/README.md) for commands and result fields.
For a detailed explanation of how the code works, read the
[code guide](engine/docs/code-walkthrough.md) for the recognition and analysis flow.
See [acoustic assessment and model expansion](engine/docs/acoustic-assessment.md)
for the experimental method and result fields.
See [verification evidence](engine/docs/recognition-verification.md) for measured
behavior and [traceability](TraceToDesign.md) for the scope of implemented requirements.
