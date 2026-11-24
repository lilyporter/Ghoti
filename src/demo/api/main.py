"""Serve selected child speech clips and run the existing engine locally."""

from datetime import datetime, timezone
from functools import lru_cache
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from time import perf_counter
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from pronouncedfish_engine import PaskettiRecognizer, analyze, load_audio


ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "demo" / "audio"
MODEL = ROOT / "engine" / "models" / "pasketti-phonetic"
ANALYSIS = ROOT / "demo" / "saved_results.json"
LATEST_SESSION = ROOT / "demo" / "latest_session.json"
HISTORY = ROOT / "demo" / "history.json"
app = FastAPI(title="PronouncedFish demo API")
_inference_lock = Lock()


class SavedRecognition(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: Literal["ok", "unassessable"]
    recognized_phones: list[str]


class SavedAlignmentRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    kind: Literal["match", "substitution", "omission", "addition"]
    expected_phone: Optional[str]
    recognized_phone: Optional[str]


class SavedComparison(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: Literal["ok", "unassessable"]
    expected_phones: list[str]
    matches_target: Optional[bool]
    alignment: list[SavedAlignmentRow]


class SavedAttempt(BaseModel):
    sample_id: str
    recognition: SavedRecognition
    analysis: SavedComparison


@lru_cache(maxsize=1)
def _manifest():
    playlist = SAMPLES / "manifest.json"
    if not playlist.is_file():
        playlist = SAMPLES / "manifest.example.json"
    data = json.loads(playlist.read_text(encoding="utf-8"))
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
         "target_word": item["target_word"],
         "audio_url": f"/api/samples/{item['id']}/audio"}
        for item in _manifest().values()
    ]


@app.get("/api/analysis")
def saved_analysis(response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return json.loads(LATEST_SESSION.read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass
    if not ANALYSIS.is_file():
        return {"results": []}
    return json.loads(ANALYSIS.read_text(encoding="utf-8"))


@app.get("/api/history")
def session_history():
    return json.loads(HISTORY.read_bytes()) if HISTORY.is_file() else []


@app.get("/api/history/{sample_id}/audio")
def history_audio(sample_id: str):
    if any(attempt["sample_id"] == sample_id
           for session in session_history() for attempt in session["attempts"]):
        path = SAMPLES / "penney" / f"{sample_id}.wav"
        if path.is_file():
            return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})
    raise HTTPException(status_code=404, detail="History recording is missing")


@app.post("/api/session")
def save_session(results: list[SavedAttempt]):
    if [result.sample_id for result in results] != list(_manifest()):
        raise HTTPException(status_code=422, detail="A complete session is required")
    session = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "results": [result.model_dump(mode="json") for result in results],
    }
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=LATEST_SESSION.parent,
                                delete=False) as file:
            temporary = Path(file.name)
            json.dump(session, file, ensure_ascii=False)
        temporary.replace(LATEST_SESSION)
    except OSError as error:
        raise HTTPException(status_code=500, detail="Could not save the session") from error
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return {"completed_at": session["completed_at"]}


@app.get("/api/samples/{sample_id}/audio")
def sample_audio(sample_id: str):
    item = _sample(sample_id)
    path = SAMPLES / item["filename"]
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Sample audio is missing")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@app.post("/api/samples/{sample_id}/analyze")
def analyze_sample(sample_id: str):
    item = _sample(sample_id)
    path = SAMPLES / item["filename"]
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Sample audio is missing")
    if not MODEL.is_dir():
        raise HTTPException(status_code=503, detail="Local recognition model is missing")
    try:
        started = perf_counter()
        with _inference_lock:
            recognizer = _recognizer()
            model_ms = (perf_counter() - started) * 1000
            prepared = perf_counter()
            audio = load_audio(path)
            audio_ms = (perf_counter() - prepared) * 1000
            recognized = perf_counter()
            recognition = recognizer.recognize(audio)
            recognition_ms = (perf_counter() - recognized) * 1000
        compared = perf_counter()
        comparison = analyze(recognition, item["expected_phones"])
        comparison_ms = (perf_counter() - compared) * 1000
        total_ms = (perf_counter() - started) * 1000
        print(
            f"[{sample_id}] model load {model_ms:.0f} ms | audio prep {audio_ms:.0f} ms | "
            f"recognition {recognition_ms:.0f} ms | comparison {comparison_ms:.0f} ms | "
            f"total {total_ms:.0f} ms",
            flush=True,
        )
    except (OSError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {error}") from error
    return {"sample_id": sample_id, "recognition": recognition, "analysis": comparison}
