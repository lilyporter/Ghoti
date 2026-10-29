"""FP32 local WavLM/CTC baseline using the published Pasketti phonetic weights."""

from pathlib import Path
from time import perf_counter
from typing import Optional, Union

from .assets import MODEL_VERSION, verify_model
from .audio import MAX_DURATION_SECONDS, SAMPLE_RATE_HZ
from .phonetics import tokenize_pasketti
from .recognition import AudioInput, RecognitionResult


class PaskettiRecognizer:
    """Load a pinned local snapshot once, then recognize one utterance at a time.

    Construction verifies weights and never downloads. All inference uses FP32;
    WavLM's relative-position calculations can produce NaNs in half precision.
    """

    sample_rate_hz = SAMPLE_RATE_HZ

    def __init__(self, model_dir: Union[str, Path], *, device: str = "cpu") -> None:
        if device not in {"cpu", "cuda"}:
            raise ValueError("device must be 'cpu' or 'cuda'.")
        directory = verify_model(model_dir)
        import torch
        from transformers import Wav2Vec2Processor, WavLMForCTC

        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA was requested but is not available.")
        self._device = torch.device(device)
        self._processor = Wav2Vec2Processor.from_pretrained(
            str(directory), local_files_only=True
        )
        self._model, loading_info = WavLMForCTC.from_pretrained(
            str(directory),
            local_files_only=True,
            use_safetensors=True,
            dtype=torch.float32,
            output_loading_info=True,
        )
        if any(loading_info.get(key) for key in (
            "missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs"
        )):
            raise ValueError("Checkpoint did not load exactly; refusing incomplete weights.")
        if self._processor.feature_extractor.sampling_rate != self.sample_rate_hz:
            raise ValueError("Unexpected model sample rate.")
        if self._model.config.pad_token_id != self._processor.tokenizer.pad_token_id:
            raise ValueError("Model and tokenizer disagree on the CTC blank.")
        self._model.to(device=self._device, dtype=torch.float32).eval()

    @staticmethod
    def _result(
        phones: list[str],
        transcription: str,
        time_ms: Optional[float],
        reason: Optional[str] = None,
    ) -> RecognitionResult:
        return RecognitionResult(
            status="unassessable" if reason else "ok",
            recognized_phones=phones,
            phonetic_transcription=transcription,
            model_version=MODEL_VERSION,
            inference_time_ms=time_ms,
            confidence_status="uncalibrated" if time_ms is not None else "unavailable",
            requires_review=True,
            review_reason=reason or "Uncalibrated baseline prediction; clinician review required.",
        )

    def recognize(self, audio: AudioInput) -> RecognitionResult:
        """Run local acoustic inference without target words or language correction."""
        import numpy as np
        import torch

        if audio.sample_rate_hz != self.sample_rate_hz:
            raise ValueError("Expected 16000 Hz mono PCM; use load_audio for resampling.")
        samples = np.asarray(audio.samples, dtype=np.float32)
        if samples.ndim != 1:
            raise ValueError("Expected a one-dimensional mono audio buffer.")
        if not np.isfinite(samples).all():
            raise ValueError("PCM samples must be finite.")
        if samples.size and np.max(np.abs(samples)) > 1.0:
            raise ValueError("PCM samples must lie in [-1, 1].")
        # The convolutional encoder requires at least 400 samples (25 ms).
        if samples.size < 400:
            return self._result([], "", None, "Audio is too short for the encoder.")
        if samples.size > MAX_DURATION_SECONDS * self.sample_rate_hz:
            return self._result([], "", None, "Audio exceeds the 30-second baseline limit.")
        if float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))) < 1e-5:
            return self._result([], "", None, "Audio is silent or nearly silent.")
        inputs = self._processor(
            samples, sampling_rate=self.sample_rate_hz, return_tensors="pt",
            # One unpadded utterance has no masked frames. Omitting this redundant
            # mask avoids WavLM mixing a boolean padding mask with FP32 position bias.
            # A future padded-batch API must handle padding masks explicitly.
            padding=False, return_attention_mask=False,
        ).to(self._device)
        if self._device.type == "cuda":
            torch.cuda.synchronize(self._device)
        started = perf_counter()
        with torch.inference_mode():
            logits = self._model(**inputs).logits
        if self._device.type == "cuda":
            torch.cuda.synchronize(self._device)
        time_ms = (perf_counter() - started) * 1000
        if not torch.isfinite(logits).all().item():
            return self._result([], "", time_ms, "Model produced non-finite logits.")
        # HF handles CTC repeat collapse, blank removal, and word delimiters.
        frame_ids = logits.argmax(dim=-1).cpu()
        transcription = self._processor.batch_decode(frame_ids)[0].strip()
        try:
            phones = tokenize_pasketti(transcription)
        except ValueError:
            return self._result(
                [], transcription, time_ms,
                "Decoded IPA has unsupported or malformed marks; review raw transcription.",
            )
        if not phones:
            return self._result([], transcription, time_ms, "Model decoded no phones.")
        return self._result(phones, transcription, time_ms)
