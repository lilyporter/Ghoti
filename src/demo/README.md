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

The six included clips are pitch-shifted adult synthetic speech, not recordings
of children. Their labels describe the intended spoken words; the result screen
shows the engine's actual prediction and candidate sound differences. Those
results are not clinical assessments.
