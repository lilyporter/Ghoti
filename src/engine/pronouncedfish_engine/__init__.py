"""Local Pasketti recognition. Weights load when a recognizer is constructed."""

from .audio import load_audio
from .pasketti import PaskettiRecognizer
from .recognition import AudioInput, RecognitionResult

__all__ = ["AudioInput", "RecognitionResult", "PaskettiRecognizer", "load_audio"]
