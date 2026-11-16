# iPad demo

Run the React page and Python API on your laptop. Open the network URL printed by
Vite on your iPad, connected to the same Wi-Fi. Vite forwards `/api` requests to
FastAPI, which runs the existing `engine/` package. No router port forwarding is
needed.

One-time setup from `src/`:

```powershell
conda activate phoneme-engine
python -m pip install -e ".\engine[analysis]"
python -m pip install -r .\demo\api\requirements.txt
cd .\demo\web
npm install
```

Start the API in one terminal from `src/`:

```powershell
conda activate phoneme-engine
python -m uvicorn demo.api.main:app --host 127.0.0.1 --port 8000
```

Start the page in a second terminal:

```powershell
cd .\demo\web
npm run dev
```

Open the `Network` URL shown by Vite on the iPad. The model files must be present
in `engine/models/pasketti-phonetic/`. The first analysis takes longer while the
laptop loads the model.

The active demo uses ten real child recordings from ten different speakers in
`audio/real/`: sun, gift, seal, sheep, shell, ship, shoe, shop, soup, and chute.
The older generated clips in `audio/synthetic/` are not used. The terminal prints
model loading, audio preparation, recognition, comparison, and total time for each
analysis request.

The word targets come from the supplied Paidologos `dataset.csv`, except “sun”:
its CSV target is `/sən/` while its annotated production is `[sʌn]`, so this demo
compares against `/sʌn/`. Model predictions are never replaced by those annotations.
Results are candidate differences, not clinical assessments.

Audio source: [English Paidologos corpus](https://talkbank.org/phon/access/Eng-NA/PaidoEnglish.html).
Please cite Edwards, J., & Beckman, M. E. (2008), *Methodological questions in
studying consonant acquisition*, Clinical Linguistics & Phonetics 22(12), 937–956.
The corpus audio follows [TalkBank's data rules](https://talkbank.org/0share/rules.html),
including its noncommercial share-alike terms; it is separate from this project's
code license.
