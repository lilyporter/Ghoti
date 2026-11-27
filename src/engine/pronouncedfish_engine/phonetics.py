"""Shared IPA spelling normalization for phone comparison."""

import unicodedata


def canonical_phone(phone: str) -> str:
    """Comparison spelling only; preserve marks and distinct sounds such as r/ɹ."""
    return unicodedata.normalize("NFD", phone.translate(
        str.maketrans({"g": "ɡ", "ʧ": "t͡ʃ", "ʤ": "d͡ʒ"})
    ))
