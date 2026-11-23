"""Tokenize Pasketti's character alphabet into complete produced-phone tokens.

This is model-specific tokenization, not a universal IPA parser. Preserve the
published spelling (including g, r, and the single-character affricates ʤ/ʧ).
"""

BASE_SYMBOLS = frozenset("bcdefghijklmnoprstuvwxzæçðŋɐɑɔəɚɛɟɪɫɬɹɾʁʃʊʌʒʔʝʤʧθχ")
MODIFIERS = frozenset({"ː", "\u0303"})
TIE_BAR = "\u0361"


def canonical_phone(phone: str) -> str:
    """Comparison spelling only; preserve marks and distinct sounds such as r/ɹ."""
    import unicodedata

    return unicodedata.normalize("NFD", phone.translate(
        str.maketrans({"g": "ɡ", "ʧ": "t͡ʃ", "ʤ": "d͡ʒ"})
    ))


def tokenize_pasketti(transcription: str) -> list[str]:
    """Attach length/nasal marks and join explicitly tied sounds.

    Whitespace separates words and is retained in the raw transcription, not as
    a phone. Untied vowels remain separate. Dangling or unknown symbols fail
    explicitly rather than being silently dropped or mapped to expected phones.
    """
    phones: list[str] = []
    boundary = True
    pending_tie = False
    for symbol in transcription:
        if symbol.isspace():
            if pending_tie:
                raise ValueError("A tie bar cannot end a word.")
            boundary = True
        elif symbol == TIE_BAR:
            if boundary or pending_tie:
                raise ValueError("A tie bar must connect two sounds.")
            phones[-1] += symbol
            pending_tie = True
        elif symbol in MODIFIERS:
            if boundary or pending_tie:
                raise ValueError("A modifier must follow a sound.")
            if phones[-1].endswith(symbol):
                raise ValueError("Repeated IPA modifier.")
            phones[-1] += symbol
        elif symbol in BASE_SYMBOLS:
            if pending_tie:
                phones[-1] += symbol
                pending_tie = False
            else:
                phones.append(symbol)
            boundary = False
        else:
            raise ValueError("Decoded symbol is outside the Pasketti inventory.")
    if pending_tie:
        raise ValueError("A tie bar must connect two sounds.")
    return phones
