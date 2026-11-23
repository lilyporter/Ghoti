"""Audio input and result shapes used by the recognizer and CLI."""

from dataclasses import dataclass
from typing import Literal, Optional, Sequence, TypedDict


@dataclass(frozen=True)
class AudioInput:
    """Mono PCM samples in [-1, 1] at the recognizer's required sample rate.

    Capture, decoding, and resampling happen before this boundary. Implementations
    must validate finite samples, duration, and sample rate before inference.
    """

    samples: Sequence[float]
    sample_rate_hz: int


class RecognitionResult(TypedDict):
    """JSON-compatible output describing produced phones, never target words.

    Each string is one phone token, including any combining marks or affricate
    notation. An unassessable result must explain its status in review_reason.
    Missing measurements use None; confidence calibration is not assumed.
    """

    status: Literal["ok", "unassessable"]
    recognized_phones: list[str]
    phonetic_transcription: str
    model_version: str
    inference_time_ms: Optional[float]
    confidence_status: Literal["unavailable", "uncalibrated", "calibrated"]
    requires_review: bool
    review_reason: Optional[str]
