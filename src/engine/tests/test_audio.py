import numpy as np
import pytest
import soundfile as sf

from pronouncedfish_engine import load_audio


def test_stereo_audio_is_mixed_and_resampled(tmp_path):
    rate = 48000
    wave = (0.2 * np.sin(2 * np.pi * 440 * np.arange(rate) / rate)).astype(np.float32)
    path = tmp_path / "stereo.wav"
    sf.write(path, np.stack([wave, wave / 2], axis=1), rate, subtype="FLOAT")
    audio = load_audio(path)
    assert audio.sample_rate_hz == 16000
    assert audio.samples.shape == (16000,)
    expected = 0.15 * np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)
    np.testing.assert_allclose(audio.samples[100:-100], expected[100:-100], atol=1e-4)


@pytest.mark.parametrize("values", [[float("nan")], [1.2]])
def test_invalid_source_pcm_is_rejected_before_channel_mixing(tmp_path, values):
    path = tmp_path / "invalid.wav"
    sf.write(path, np.array([values * 2] * 1000), 16000, subtype="FLOAT")
    with pytest.raises(ValueError, match="finite PCM"):
        load_audio(path)


def test_long_file_is_not_silently_truncated(tmp_path):
    path = tmp_path / "long.wav"
    sf.write(path, np.zeros(31 * 16000), 16000)
    with pytest.raises(ValueError, match="30 seconds"):
        load_audio(path)


def test_remote_url_is_not_an_audio_source():
    with pytest.raises(FileNotFoundError, match="local WAV"):
        load_audio("https://example.invalid/recording.wav")


@pytest.mark.parametrize("rate", [8000, 22050, 44100, 48000])
def test_direct_resampler_matches_reference_including_fractional_length(tmp_path, rate):
    import librosa

    # Odd lengths exercise SoXR rounding versus librosa's ceil-and-pad convention.
    wave = (0.1 * np.sin(np.arange(1001) / 10)).astype(np.float32)
    path = tmp_path / "fractional.wav"
    sf.write(path, wave, rate, subtype="FLOAT")
    expected = librosa.resample(wave, orig_sr=rate, target_sr=16000, res_type="soxr_hq")
    actual = load_audio(path).samples
    np.testing.assert_array_equal(actual, expected)
