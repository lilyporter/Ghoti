"""Local file decoding and preprocessing for short development recordings."""

from pathlib import Path
from typing import Union

from .recognition import AudioInput

SAMPLE_RATE_HZ = 16000
MAX_DURATION_SECONDS = 30.0


def load_audio(path: Union[str, Path]) -> AudioInput:
    """Read a local WAV/FLAC, mix to mono, and resample with SoXR HQ.

    Only local files are accepted. Check source samples before mixing so invalid
    channels cannot be hidden by averaging. Do not peak-normalize quiet audio.
    Model-specific zero-mean/unit-variance normalization happens in the processor.
    """
    import numpy as np
    import soundfile as sf

    local_path = Path(path).expanduser()
    if not local_path.is_file():
        raise FileNotFoundError("Audio must be an existing local WAV or FLAC file.")
    with sf.SoundFile(str(local_path)) as stream:
        if stream.format not in {"WAV", "WAVEX", "FLAC"}:
            raise ValueError("Only WAV and FLAC audio are supported in this baseline.")
        if not 0 < stream.frames <= MAX_DURATION_SECONDS * stream.samplerate:
            raise ValueError("Audio must be nonempty and at most 30 seconds long.")
        samples = stream.read(dtype="float32", always_2d=True)
        source_rate = stream.samplerate
    if not np.isfinite(samples).all() or np.max(np.abs(samples)) > 1.0:
        raise ValueError("Audio samples must be finite PCM values in [-1, 1].")
    samples = samples.mean(axis=1)
    if source_rate != SAMPLE_RATE_HZ:
        import soxr

        # Same resampler/quality as librosa's soxr_hq, without its lazy import cost.
        # Preserve librosa's ceil-length convention (SoXR itself rounds length).
        output_length = int(np.ceil(len(samples) * (SAMPLE_RATE_HZ / source_rate)))
        samples = soxr.resample(
            samples, in_rate=source_rate, out_rate=SAMPLE_RATE_HZ, quality="HQ"
        )
        if len(samples) < output_length:
            samples = np.pad(samples, (0, output_length - len(samples)))
        else:
            samples = samples[:output_length]
        # Band-limited resampling can slightly overshoot even bounded input.
        if np.max(np.abs(samples)) > 1.0:
            raise ValueError("Resampled audio exceeds PCM range; lower its source level.")
    return AudioInput(np.ascontiguousarray(samples, dtype=np.float32), SAMPLE_RATE_HZ)
