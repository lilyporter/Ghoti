import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from transformers import Wav2Vec2CTCTokenizer, Wav2Vec2FeatureExtractor, Wav2Vec2Processor

from pronouncedfish_engine import AudioInput, PaskettiRecognizer


@pytest.fixture
def recognizer(tmp_path):
    """Deterministic logits test double; no claim of acoustic recognition."""
    vocab = {"<blank>": 0, "b": 1, "|": 2, "ʧ": 3, "e": 4, "\u0303": 5, "<unk>": 6}
    path = tmp_path / "vocab.json"
    path.write_text(json.dumps(vocab), encoding="utf-8")
    tokenizer = Wav2Vec2CTCTokenizer(
        str(path), pad_token="<blank>", unk_token="<unk>",
        word_delimiter_token="|", bos_token=None, eos_token=None,
    )
    instance = PaskettiRecognizer.__new__(PaskettiRecognizer)
    instance._processor = Wav2Vec2Processor(
        Wav2Vec2FeatureExtractor(sampling_rate=16000, return_attention_mask=True),
        tokenizer,
    )
    instance._device = torch.device("cpu")
    return instance


def set_frames(recognizer, frames):
    logits = torch.full((1, len(frames), 7), -10.0)
    for index, frame in enumerate(frames):
        logits[0, index, frame] = 10.0
    recognizer._model = lambda **inputs: SimpleNamespace(logits=logits)


def speech_buffer():
    return AudioInput((0.1 * np.sin(np.arange(1600) / 10)).astype(np.float32), 16000)


def test_ctc_preserves_blank_separated_repeats_and_phone_marks(recognizer):
    set_frames(recognizer, [1, 1, 0, 1, 2, 3, 3, 4, 5, 5])
    result = recognizer.recognize(speech_buffer())
    assert result["status"] == "ok"
    assert result["recognized_phones"] == ["b", "b", "ʧ", "e\u0303"]
    assert result["phonetic_transcription"] == "bb ʧe\u0303"
    assert result["confidence_status"] == "uncalibrated"
    assert result["requires_review"] is True
    assert result["inference_time_ms"] >= 0


@pytest.mark.parametrize("frames", [[0, 0], [5, 4], [6]])
def test_empty_or_malformed_decodes_require_review(recognizer, frames):
    set_frames(recognizer, frames)
    result = recognizer.recognize(speech_buffer())
    assert result["status"] == "unassessable"
    assert result["recognized_phones"] == []
    assert result["review_reason"]


@pytest.mark.parametrize("samples", [[], [0.1] * 100, [0.0] * 1600, [0.1] * 480001])
def test_unusable_audio_skips_model(recognizer, samples):
    def forbidden(**kwargs):
        pytest.fail("Model must not run for unusable audio")

    recognizer._model = forbidden
    result = recognizer.recognize(AudioInput(samples, 16000))
    assert result["status"] == "unassessable"
    assert result["inference_time_ms"] is None
    assert result["confidence_status"] == "unavailable"


@pytest.mark.parametrize(
    "audio",
    [AudioInput([0.1] * 500, 44100), AudioInput([[0.1]] * 500, 16000),
     AudioInput([float("nan")] * 500, 16000), AudioInput([1.1] * 500, 16000)],
)
def test_malformed_pcm_is_rejected(recognizer, audio):
    with pytest.raises(ValueError):
        recognizer.recognize(audio)


def test_nonfinite_model_output_is_unassessable(recognizer):
    recognizer._model = lambda **inputs: SimpleNamespace(logits=torch.full((1, 4, 7), float("nan")))
    result = recognizer.recognize(speech_buffer())
    assert result["status"] == "unassessable"
    assert "non-finite" in result["review_reason"]


def test_missing_model_never_triggers_download(tmp_path):
    with pytest.raises(FileNotFoundError, match="download-model"):
        PaskettiRecognizer(tmp_path / "missing")
