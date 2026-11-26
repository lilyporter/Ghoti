"""Evaluate the local Pasketti recognizer against hand-anchored IPA.

This script drives ``PaskettiRecognizer`` over a set of child speech clips and
reports how well the model's predicted phonetics match the reference
``actual_ipa`` transcription in the dataset CSV. It is meant to answer one
question: *what is the overall accuracy of the Pasketti model on this data?*

How it works
------------
1. Read ``dataset.csv`` (one row per utterance). The ``clip_file`` column names
   the WAV for each row; ``actual_ipa`` is the reference transcription.
2. For every row, load the WAV through :func:`pronouncedfish_engine.audio.load_audio`
   and run ``recognizer.recognize(...)`` to get the predicted phones.
3. Compare the predicted phones against the reference phones with a phone-level
   edit distance (Levenshtein). Per-clip accuracy is ``1 - edits / len(ref)``.
4. Overall accuracy is the mean per-clip accuracy across all assessed clips,
   plus a token-level aggregate and an exact-match rate for context.

Notation handling
------------------
The model and the reference use *different* IPA conventions:

* The model emits tokens from ``BASE_SYMBOLS`` (digraphs ``ʧ``/``ʤ``, stress
  marks, tie bars such as ``t͡ʃ``). Its tokenizer rejects superscripts.
* ``actual_ipa`` uses syllable dots (``.``), superscript coarticulation markers
  (``ʰ ʲ ʷ``), stress marks, and combining marks -- notation the model cannot
  produce.

Comparing the two raw would only measure notational disagreement. We therefore
reduce both sides to their *base segment* with :func:`to_base_phones`, dropping
syllable boundaries, stress/length marks, tie bars, and superscripts while
keeping every real phoneme. The edit distance then measures genuine phone-level
agreement on the model's own inventory.

Run it
------
    python test/pasketti_model/evaluate_pasketti.py \
        --csv  test/pasketti_model/ProcessedPreliminaryData/Paidologos/dataset.csv \
        --clips-dir test/pasketti_model/ProcessedPreliminaryData/Paidologos/clips \
        --model-dir ~/.pronouncedfish/models/pasketti

The WAV files are *not* shipped in the repo; point ``--clips-dir`` at the folder
that contains them (the ``clip_file`` names come from the CSV). Missing audio is
reported and skipped rather than aborting the run.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Make the engine importable when this script is run from a checkout without an
# installed package (``pip install -e .`` adds it too). The package lives under
# ``src/engine/pronouncedfish_engine`` and is imported as top-level
# ``pronouncedfish_engine``, so we add its parent directory to ``sys.path``.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _ensure_importable() -> None:
    try:
        import pronouncedfish_engine  # noqa: F401

        return
    except ImportError:
        pass
    for candidate in (_REPO_ROOT / "src" / "engine", _REPO_ROOT / "src", _REPO_ROOT):
        if (candidate / "pronouncedfish_engine").is_dir():
            sys.path.insert(0, str(candidate))
            return
    raise ImportError(
        f"Could not locate the pronouncedfish_engine package under {list(candidate.parents)}; "
        "install it with `pip install -e .` or run from the repo root.",
    )


_ensure_importable()

from pronouncedfish_engine.phonetics import BASE_SYMBOLS, TIE_BAR  # noqa: E402


# --------------------------------------------------------------------------- #
# Reference normalization
# --------------------------------------------------------------------------- #
def to_base_phones(text: str) -> list[str]:
    """Reduce an IPA string to a list of base-segment phone tokens.

    Syllable separators (``.``), stress/length modifiers, tie bars, and
    superscript coarticulation markers (``ʰ ʲ ʷ`` ...) are dropped; every real
    phoneme in ``BASE_SYMBOLS`` is kept. Applied identically to predicted and
    reference output so the comparison lives on common ground.

    >>> to_base_phones("kʰek")
    ['k', 'e', 'k']
    >>> to_base_phones("sɛ.vɪxn")
    ['s', 'ɛ', 'v', 'ɪ', 'x', 'n']
    >>> to_base_phones("t͡ʃa")   # tie bar dropped -> t, ʃ; 'a' is outside the model inventory
    ['t', 'ʃ']
    """
    if not text:
        return []
    phones: list[str] = []
    # Each phoneme in BASE_SYMBOLS is a single character, so emit one token per
    # symbol. Dropping the tie bar splits an affricate (t͡ʃ -> t, ʃ), which keeps
    # it aligned with actual_ipa's letter-by-letter notation.
    for symbol in text.replace(".", ""):
        if symbol.isspace() or symbol == TIE_BAR or symbol in {"ː", "̃"}:
            continue
        if symbol in BASE_SYMBOLS:
            phones.append(symbol)
        # else: superscripts (ʰ ʲ ʷ), stress (ˈ ˌ), combining marks, stray digits
        # or annotation symbols ('<', '1') are not base phonemes -> drop.
    return phones


# --------------------------------------------------------------------------- #
# Distance / accuracy
# --------------------------------------------------------------------------- #
def levenshtein(a: list[str], b: list[str]) -> int:
    """Minimum single-token edits (insert/delete/replace) to turn ``a`` into ``b``."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev, cur = cur, prev
    return prev[-1]


def phone_accuracy(pred: list[str], ref: list[str]) -> float:
    """Per-clip phonetic accuracy in ``[0, 1]``; a longer reference caps the score."""
    if not ref:
        return 0.0
    edits = levenshtein(pred, ref)
    return 1.0 - edits / len(ref)


# --------------------------------------------------------------------------- #
# Dataset IO
# --------------------------------------------------------------------------- #
def load_dataset(csv_path: Path) -> list[dict]:
    """Read the dataset CSV into a list of row dicts (header-driven)."""
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"clip_file", "actual_ipa"}
    missing_cols = required - set(rows[0]) if rows else required
    if missing_cols:
        raise ValueError(f"CSV is missing required column(s): {sorted(missing_cols)}")
    return rows


# --------------------------------------------------------------------------- #
# Evaluation report
# --------------------------------------------------------------------------- #
@dataclass
class ClipResult:
    session_id: str
    utterance_id: str
    word: str
    clip_file: str
    actual_ipa: str
    status: str = ""  # set by run_evaluation; see module docstring for the values
    ref_phones: list[str] = field(default_factory=list)
    pred_phones: list[str] = field(default_factory=list)
    accuracy: float = 0.0


@dataclass
class EvaluationReport:
    total_rows: int
    results: list[ClipResult] = field(default_factory=list)

    # --- aggregate metrics ------------------------------------------------- #
    @property
    def assessed(self) -> list[ClipResult]:
        return [r for r in self.results if r.status == "assessed"]

    @property
    def counts(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for r in self.results:
            tally[r.status] = tally.get(r.status, 0) + 1
        return tally

    @property
    def overall_phone_accuracy(self) -> Optional[float]:
        """Mean per-clip phone accuracy over assessed clips (primary metric)."""
        if not self.assessed:
            return None
        return sum(r.accuracy for r in self.assessed) / len(self.assessed)

    @property
    def token_level_accuracy(self) -> Optional[float]:
        """Total correct tokens / total reference tokens across assessed clips."""
        correct = total = 0
        for r in self.assessed:
            ref_len = len(r.ref_phones)
            if not ref_len:
                continue
            correct += ref_len - levenshtein(r.pred_phones, r.ref_phones)
            total += ref_len
        return correct / total if total else None

    @property
    def exact_match_rate(self) -> Optional[float]:
        """Fraction of assessed clips whose predicted phones exactly match."""
        if not self.assessed:
            return None
        hits = sum(1 for r in self.assessed if r.pred_phones == r.ref_phones)
        return hits / len(self.assessed)


# --------------------------------------------------------------------------- #
# Driver (torch-dependent; imported lazily so the pure helpers stay testable)
# --------------------------------------------------------------------------- #
def _load_recognizer(model_dir: Path, device: str):
    """Import-time-isolated model construction."""
    from pronouncedfish_engine.assets import download_pasketti, verify_model
    from pronouncedfish_engine.pasketti import PaskettiRecognizer

    if not (model_dir / "pronouncedfish-model.json").exists():
        print(f"Model snapshot not found at {model_dir}; downloading public weights ...")
        model_dir = download_pasketti(model_dir)
    else:
        verify_model(model_dir)
    return PaskettiRecognizer(model_dir, device=device)


def run_evaluation(
    csv_path: Path,
    clips_dir: Path,
    model_dir: Path,
    *,
    device: str = "cpu",
    max_clips: Optional[int] = None,
) -> EvaluationReport:
    """Run the recognizer over every row and build an :class:`EvaluationReport`.

    ``clips_dir`` is resolved against each row's ``clip_file``; audio that cannot
    be found or decoded is recorded as ``missing_audio`` / ``unassessable_model``
    and excluded from the accuracy totals.
    """
    rows = load_dataset(csv_path)
    if max_clips is not None:
        rows = rows[:max_clips]

    recognizer = _load_recognizer(model_dir, device)
    report = EvaluationReport(total_rows=len(rows))

    for row in rows:
        clip_file = (row.get("clip_file") or "").strip()
        actual_ipa = (row.get("actual_ipa") or "").strip()
        result = ClipResult(
            session_id=(row.get("session_id") or ""),
            utterance_id=(row.get("utterance_id") or ""),
            word=(row.get("word") or ""),
            clip_file=clip_file,
            actual_ipa=actual_ipa,
        )
        report.results.append(result)

        ref_phones = to_base_phones(actual_ipa)
        result.ref_phones = ref_phones
        if not ref_phones:
            result.status = "no_reference"  # nothing to grade against
            continue

        audio_path = clips_dir / clip_file
        if not audio_path.is_file():
            result.status = "missing_audio"
            continue

        try:
            from pronouncedfish_engine.audio import load_audio

            audio = load_audio(audio_path)
        except Exception as exc:  # noqa: BLE001 - report any decode failure
            print(f"  ! failed to load {audio_path.name}: {exc}")
            result.status = "missing_audio"
            continue

        try:
            recognition = recognizer.recognize(audio)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! inference failed for {audio_path.name}: {exc}")
            result.status = "unassessable_model"
            continue

        result.pred_phones = to_base_phones("".join(recognition["recognized_phones"]))
        if recognition["status"] != "ok" or not result.pred_phones:
            result.status = "unassessable_model"
            continue

        result.accuracy = phone_accuracy(result.pred_phones, ref_phones)
        result.status = "assessed"

    return report


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def _write_csv_report(path: Path, report: EvaluationReport) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "session_id", "utterance_id", "word", "clip_file", "actual_ipa",
            "status", "ref_phones", "pred_phones", "accuracy",
        ])
        for r in report.results:
            writer.writerow([
                r.session_id, r.utterance_id, r.word, r.clip_file, r.actual_ipa,
                r.status, "|".join(r.ref_phones), "|".join(r.pred_phones),
                f"{r.accuracy:.4f}",
            ])


def print_summary(report: EvaluationReport) -> None:
    """Print a human-readable accuracy summary to stdout."""
    counts = report.counts
    print("\n=== Pasketti model evaluation ===")
    print(f"Rows read              : {report.total_rows}")
    for status, n in counts.items():
        print(f"  {status:<20}: {n}")

    overall = report.overall_phone_accuracy
    token_level = report.token_level_accuracy
    exact = report.exact_match_rate

    print("\n--- Overall accuracy ---")
    if overall is None:
        print("No clips could be assessed (check --clips-dir and model download).")
    else:
        print(f"Overall phone accuracy : {overall * 100:.2f}%  "
              f"(mean per-clip edit-distance accuracy)")
        if token_level is not None:
            print(f"Token-level accuracy   : {token_level * 100:.2f}%  "
                  f"(correct tokens / reference tokens)")
        if exact is not None:
            print(f"Exact phone-seq match  : {exact * 100:.2f}%")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the Pasketti recognizer against actual_ipa in a dataset CSV.",
    )
    parser.add_argument("--csv", type=Path, required=True,
                        help="Path to the dataset.csv with an actual_ipa column.")
    parser.add_argument("--clips-dir", type=Path, required=True,
                        help="Directory holding the WAV clips (clip_file names from the CSV).")
    parser.add_argument("--model-dir", type=Path, default=Path(
        f"{Path.home()}/.pronouncedfish/models/pasketti"),
                        help="Local model snapshot directory (downloaded if absent).")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu",
                        help="Inference device (default: cpu).")
    parser.add_argument("--max-clips", type=int, default=None,
                        help="Optional cap on rows to evaluate (useful for a quick check).")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="If given, also write per-clip results as CSV here.")
    args = parser.parse_args(argv)

    if not args.csv.is_file():
        print(f"Error: CSV not found: {args.csv}", file=sys.stderr)
        return 2

    report = run_evaluation(
        args.csv, args.clips_dir, args.model_dir,
        device=args.device, max_clips=args.max_clips,
    )
    print_summary(report)

    if args.out_dir is not None:
        out_path = Path(args.out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        csv_out = out_path / "pasketti_evaluation_results.csv"
        _write_csv_report(csv_out, report)
        json_out = out_path / "pasketti_evaluation_summary.json"
        summary = {
            "total_rows": report.total_rows,
            "counts": report.counts,
            "overall_phone_accuracy": report.overall_phone_accuracy,
            "token_level_accuracy": report.token_level_accuracy,
            "exact_match_rate": report.exact_match_rate,
        }
        json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nWrote per-clip results -> {csv_out}")
        print(f"Wrote summary JSON     -> {json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
