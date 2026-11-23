"""Descriptive target comparisons; these are candidates for human review.

No acoustic distortion detector or clinical severity/confidence score is implied.
Inputs are complete phone tokens, not words or individual Unicode characters.
"""

import csv
from functools import lru_cache
from importlib.resources import files
from typing import Any, Iterable, Sequence
import unicodedata

from .recognition import RecognitionResult
from .phonetics import canonical_phone as _canonical


def _tokens(phones: Sequence[str], label: str) -> list[str]:
    if isinstance(phones, (str, bytes)):
        raise ValueError(f"{label} must be a sequence of complete phone tokens.")
    result = list(phones)
    if not result or any(
        not isinstance(p, str) or not p or any(c.isspace() for c in p)
        for p in result
    ):
        raise ValueError(f"{label} must contain nonempty phone tokens without whitespace.")
    return result


@lru_cache(maxsize=1)
def _feature_table():
    # PanPhon 0.22.2's FeatureTable opens this file with the system encoding,
    # which fails on Windows cp1252. Read the published data as UTF-8 directly;
    # no global encoding changes or patches to the installed library are needed.
    with files("panphon").joinpath("data/ipa_all.csv").open(encoding="utf-8", newline="") as source:
        reader = csv.reader(source)
        names = next(reader)[1:]
        values = {"-": -1, "0": 0, "+": 1}
        vectors = {
            unicodedata.normalize("NFD", row[0]): [values[v] for v in row[1:]]
            for row in reader
        }
    return names, vectors


def _features(expected: str, recognized: str, vectors) -> dict[str, Any]:
    # Exact segment lookup prevents PanPhon silently skipping unknown characters
    # or splitting a tied diphthong into multiple, misleading feature vectors.
    av = vectors.get(_canonical(expected))
    bv = vectors.get(_canonical(recognized))
    if av is None or bv is None:
        return {"feature_status": "unavailable", "feature_comparison": None}
    differences = [abs(x - y) for x, y in zip(av, bv)]
    return {
        "feature_status": "available",
        "feature_comparison": {
            "expected_vector": list(av),
            "recognized_vector": list(bv),
            "absolute_differences": differences,
            "manhattan_distance": sum(differences),
        },
    }


def analyze(
    recognition: RecognitionResult,
    expected_phones: Sequence[str],
    *,
    acceptable_variants: Iterable[Sequence[str]] = (),
    supported_substitutions: Iterable[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Align recognition against the closest supplied acceptable pronunciation.

    The main target is variant 0; additional variants follow in caller order.
    Select by minimum unit-cost token edits, breaking ties by that order. The
    alignment is one possible minimum-edit explanation, not a clinical finding.
    Supported substitutions are directional (expected, recognized) pairs supplied
    by the caller's approved inventory; no substitutions are supported by default.
    PanPhon distances describe categories, not severity or acoustic distortion.
    """
    variants = [_tokens(expected_phones, "expected_phones")]
    variants.extend(_tokens(v, "acceptable variant") for v in acceptable_variants)
    supported = set()
    for pair in supported_substitutions:
        if isinstance(pair, (str, bytes)) or len(pair) != 2:
            raise ValueError("Supported substitutions must be (expected, recognized) pairs.")
        supported.add(tuple(_canonical(p) for p in _tokens(pair, "substitution pair")))
    base = {
        "status": "unassessable",
        "expected_phones": variants[0],
        "selected_variant_index": None,
        "selected_expected_phones": None,
        "matches_target": None,
        "edit_counts": None,
        "alignment": [],
        "feature_names": [],
        "feature_source": "panphon==0.22.2/spe+",
        "distortion_status": "not_assessed",
        "requires_review": True,
        "review_reason": "Recognition is unassessable or contains no phones; no production differences inferred.",
    }
    if recognition["status"] != "ok" or not recognition["recognized_phones"]:
        return base
    heard = _tokens(recognition["recognized_phones"], "recognized_phones")

    from jiwer import process_words

    hypothesis = " ".join(_canonical(p) for p in heard)
    comparisons = [
        process_words(" ".join(_canonical(p) for p in variant), hypothesis)
        for variant in variants
    ]
    chosen = min(range(len(variants)), key=lambda i: (
        comparisons[i].substitutions + comparisons[i].deletions + comparisons[i].insertions
    ))
    expected, comparison = variants[chosen], comparisons[chosen]
    names, vectors = _feature_table()
    rows = []
    kinds = {"equal": "match", "substitute": "substitution", "delete": "omission", "insert": "addition"}
    for chunk in comparison.alignments[0]:
        for offset in range(max(chunk.ref_end_idx - chunk.ref_start_idx,
                                chunk.hyp_end_idx - chunk.hyp_start_idx)):
            ei = chunk.ref_start_idx + offset if chunk.type != "insert" else None
            hi = chunk.hyp_start_idx + offset if chunk.type != "delete" else None
            ep = expected[ei] if ei is not None else None
            hp = heard[hi] if hi is not None else None
            row = {
                "kind": kinds[chunk.type],
                "expected_index": ei, "recognized_index": hi,
                "expected_phone": ep, "recognized_phone": hp,
                "supported_substitution": (
                    (_canonical(ep), _canonical(hp)) in supported
                    if chunk.type == "substitute" else None
                ),
                "feature_status": "not_applicable",
                "feature_comparison": None,
            }
            if ep is not None and hp is not None:
                row.update(_features(ep, hp, vectors))
            rows.append(row)
    counts = {"substitutions": comparison.substitutions,
              "omissions": comparison.deletions, "additions": comparison.insertions}
    base.update(
        status="ok", selected_variant_index=chosen,
        selected_expected_phones=expected, matches_target=not any(counts.values()),
        edit_counts=counts, alignment=rows, feature_names=list(names),
        review_reason="Candidate differences from an unvalidated recognizer; human review required. Feature distance is not clinical severity.",
    )
    return base
