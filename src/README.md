# PronouncedFish

This demo illustrates SLP-led guided practice. The iPad shows picture prompts,
and prerecorded responses stand in for a child speaking. The laptop runs
Pasketti and shows the SLP the target phones, model output, and audio playback
at `/slp`. The demo stores sessions in local JSON.

The [SRS](../docs/SRS/SRS.tex) treats guided practice and standardized testing
as separate workflows. The dashboard's match counts compare model output
with the practice targets. Its Penney history uses recordings from different
speakers and illustrates session review.

## Setup

From `src/` in PowerShell:

```powershell
conda create -n phoneme-engine python=3.12 -y
conda activate phoneme-engine
python -m pip install -e "./engine[analysis]" -r demo/api/requirements.txt
python -m pronouncedfish_engine download-model --model-dir engine/models/pasketti-phonetic
npm --prefix demo/web ci
```

Reuse your local `demo/audio/manifest.json` and referenced WAVs. For a new
playlist, put the WAVs under `demo/audio/` and add one object per clip in playback order:

```json
{"samples":[{"id":"child-01","label":"Child voice 1","filename":"penney/T65_u7.wav","target_word":"spoon","expected_phones":["s","p","u","n"]}]}
```

Optional past sessions can be generated from the Penney dataset export:

```powershell
python -m demo.prepare_history "C:/path/to/Penney/dataset.csv"
```

The playlist, recordings, generated results, tests, and Supabase configuration
are local. Supabase is independent of the demo.

## Run

In separate terminals from `src/`:

```powershell
conda activate phoneme-engine
python -m uvicorn demo.api.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

```powershell
npm --prefix demo/web run dev
```

Open Vite's Network URL on the iPad and
[the SLP dashboard](http://localhost:5173/slp) on the laptop. Tap **Play recording**
to begin. The dashboard updates when the playlist finishes. Inter and Nunito
load from Google Fonts when online.

## Sources

- [Pasketti checkpoint and model license](https://huggingface.co/drivendata/pasketti-phonetic/tree/675dfe392a2af7050f1374eeab4458cb1f003b3e)
- [Penney corpus](https://talkbank.org/phon/access/Eng-NA/Penney.html). Alyson Judd
  (2018), *Exploring Relationships between Phonological Awareness and Phonological
  Productive Abilities of Kindergarten-Aged Children*.
- [English Paidologos corpus](https://talkbank.org/phon/access/Eng-NA/PaidoEnglish.html).
  Edwards and Beckman (2008), *Methodological questions in studying consonant acquisition*.
  See [TalkBank's usage rules](https://talkbank.org/0share/rules.html).
