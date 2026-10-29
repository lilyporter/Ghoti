import pytest

from pronouncedfish_engine.phonetics import tokenize_pasketti


@pytest.mark.parametrize(
    ("transcription", "expected"),
    [
        ("wæbɪt", ["w", "æ", "b", "ɪ", "t"]),
        ("ʧɪn ʤæm", ["ʧ", "ɪ", "n", "ʤ", "æ", "m"]),
        ("e\u0303\u0361i nː", ["e\u0303\u0361i", "nː"]),
        ("t\u0361ʃ", ["t\u0361ʃ"]),
        ("ei ç g ɹ r", ["e", "i", "ç", "g", "ɹ", "r"]),
        ("", []),
    ],
)
def test_preserves_phone_units_and_inventory(transcription, expected):
    assert tokenize_pasketti(transcription) == expected


@pytest.mark.parametrize("transcription", ["\u0303e", "e\u0361", "e\u0361 i", "e ː", "e<unk>"])
def test_malformed_output_is_not_silently_dropped(transcription):
    with pytest.raises(ValueError):
        tokenize_pasketti(transcription)
