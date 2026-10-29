"""Local recognition and descriptive target analysis; weights load on construction."""

from .audio import load_audio
from .analysis import analyze
from .pasketti import PaskettiRecognizer
from .recognition import AudioInput, RecognitionResult

__all__ = ["AudioInput", "RecognitionResult", "PaskettiRecognizer", "load_audio", "analyze"]
