"""Opt-in real-weight check using an explicitly supplied non-patient recording."""

import os
import socket
import warnings

import pytest

from pronouncedfish_engine import PaskettiRecognizer, load_audio


@pytest.mark.integration
def test_real_model_runs_with_network_connections_forbidden(monkeypatch):
    model_dir = os.environ.get("PRONOUNCEDFISH_MODEL_DIR")
    audio_path = os.environ.get("PRONOUNCEDFISH_SMOKE_AUDIO")
    if not model_dir or not audio_path:
        pytest.skip("Set model and authorized smoke-audio paths to run real inference.")

    def forbidden(*args, **kwargs):
        raise AssertionError("Inference attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    recognizer = PaskettiRecognizer(model_dir)
    audio = load_audio(audio_path)
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message="Support for mismatched key_padding_mask")
        result = recognizer.recognize(audio)
    assert result["status"] == "ok", result["review_reason"]
    assert result["recognized_phones"]
    assert result["phonetic_transcription"]
    assert result["inference_time_ms"] > 0
    assert result["requires_review"] is True

    # Omitting a redundant mask must preserve the original masked decoding.
    import torch

    inputs = recognizer._processor(
        audio.samples, sampling_rate=16000, return_tensors="pt", padding=False,
        return_attention_mask=True,
    )
    with warnings.catch_warnings():
        # Only the comparison path intentionally uses the deprecated mask pairing.
        warnings.filterwarnings("ignore", message="Support for mismatched key_padding_mask")
        with torch.inference_mode():
            baseline_ids = recognizer._model(**inputs).logits.argmax(dim=-1)
    baseline_text = recognizer._processor.batch_decode(baseline_ids)[0].strip()
    assert result["phonetic_transcription"] == baseline_text
