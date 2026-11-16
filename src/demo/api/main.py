"""Serve synthetic clips and run the existing engine on the selected clip."""

from functools import lru_cache
import json
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from pronouncedfish_engine import PaskettiRecognizer, analyze, load_audio


ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "demo" / "audio"
MODEL = ROOT / "engine" / "models" / "pasketti-phonetic"
app = FastAPI(title="PronouncedFish demo API")
_inference_lock = Lock()


@lru_cache(maxsize=1)
def _manifest():
    data = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
    return {item["id"]: item for item in data["samples"]}


@lru_cache(maxsize=1)
def _recognizer():
    # Load on first analysis, then retain the 1.26 GB checkpoint in memory.
    return PaskettiRecognizer(MODEL)


def _sample(sample_id: str):
    item = _manifest().get(sample_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown sample")
    return item


@app.get("/api/samples")
def samples():
    return [
        {"id": item["id"], "label": item["label"],
         "target_word": item["target_word"], "spoken_text": item["spoken_text"],
         "audio_url": f"/api/samples/{item['id']}/audio"}
        for item in _manifest().values()
    ]


@app.get("/api/samples/{sample_id}/audio")
def sample_audio(sample_id: str):
    item = _sample(sample_id)
    path = SAMPLES / item["filename"]
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Sample audio is missing")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "public, max-age=3600"})


@app.post("/api/samples/{sample_id}/analyze")
def analyze_sample(sample_id: str):
    item = _sample(sample_id)
    path = SAMPLES / item["filename"]
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Sample audio is missing")
    if not MODEL.is_dir():
        raise HTTPException(status_code=503, detail="Local recognition model is missing")
    try:
        with _inference_lock:
            recognition = _recognizer().recognize(load_audio(path))
        comparison = analyze(recognition, item["expected_phones"])
    except (OSError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {error}") from error
    return {"sample_id": sample_id, "recognition": recognition, "analysis": comparison}
