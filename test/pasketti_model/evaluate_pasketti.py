"""Evaluate Pasketti against the dataset's actual IPA transcriptions.

Scores compare base segments and omit stress, length and other diacritics.
The corpus phone error rate is total edit distance divided by the number of
reference phones in assessed clips. Missing audio, ambiguous transcriptions
and unassessable recognition are counted separately from scored clips.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PureWindowsPath
from time import perf_counter
from typing import Optional

# Prefer the engine in this checkout to any installed version.
_ENGINE_DIR = Path(__file__).resolve().parents[2] / "src" / "engine"
if (_ENGINE_DIR / "pronouncedfish_engine").is_dir():
    sys.path.insert(0, str(_ENGINE_DIR))

from pronouncedfish_engine.audio import load_audio
from pronouncedfish_engine.phonetics import canonical_phone


def to_base_phones(text: str) -> list[str]:
    """Normalize IPA spelling and keep base sounds outside the model alphabet.

    >>> to_base_phones("kʰek")
    ['k', 'e', 'k']
    >>> to_base_phones("ʧa ç ɡg")
    ['t͡ʃ', 'a', 'ç', 'ɡ', 'ɡ']
    >>> to_base_phones("tʃ.t͜ʃ t.ʃ")
    ['t͡ʃ', 't͡ʃ', 't', 'ʃ']
    """
    phones: list[str] = []
    adjacent = False
    tied = False
    # NFD decomposes ç, which is a distinct IPA base sound.
    text = canonical_phone(text).replace("c\u0327", "ç").replace("ʦ", "t͡s")
    for symbol in text:
        category = unicodedata.category(symbol)
        if symbol in {"\u0361", "\u035c"}:
            tied = adjacent
        elif category in {"Ll", "Lo"}:
            # Paidologos writes the English affricates without tie bars.
            if tied or (adjacent and phones[-1] + symbol in {"tʃ", "dʒ"}):
                phones[-1] += "\u0361" + symbol
            else:
                phones.append(symbol)
            adjacent, tied = True, False
        elif category[0] != "M" and category != "Lm":
            adjacent, tied = False, False
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


def load_dataset(csv_path: Path) -> list[dict]:
    """Read the dataset CSV into a list of row dicts (header-driven)."""
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing_cols = {"clip_file", "actual_ipa"} - set(reader.fieldnames or ())
        if missing_cols:
            raise ValueError(f"CSV is missing required column(s): {sorted(missing_cols)}")
        return list(reader)


def resolve_clip(clips_dir: Path, clip_file: str) -> Optional[Path]:
    """Resolve relative paths and re-root absolute export paths by filename."""
    exported = PureWindowsPath(clip_file)
    parts = (exported.name,) if exported.anchor else exported.parts
    audio_path = (clips_dir / Path(*parts)).resolve()
    if audio_path.is_relative_to(clips_dir) and audio_path.is_file():
        return audio_path
    return None


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
    status: str = ""
    ref_phones: list[str] = field(default_factory=list)
    pred_phones: list[str] = field(default_factory=list)
    edits: Optional[int] = None

    @property
    def phone_error_rate(self) -> Optional[float]:
        return self.edits / len(self.ref_phones) if self.edits is not None else None


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
    def mean_clip_phone_error_rate(self) -> Optional[float]:
        rates = [r.phone_error_rate for r in self.assessed]
        return sum(rates) / len(rates) if rates else None

    @property
    def phone_error_rate(self) -> Optional[float]:
        assessed = self.assessed
        if not assessed:
            return None
        return sum(r.edits for r in assessed) / sum(len(r.ref_phones) for r in assessed)

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
def _progress(message: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"{timestamp} {message}", file=sys.stderr, flush=True)


def _load_recognizer(model_dir: Path, device: str):
    """Import-time-isolated model construction."""
    from pronouncedfish_engine.assets import download_pasketti
    from pronouncedfish_engine.pasketti import PaskettiRecognizer

    if not (model_dir / "pronouncedfish-model.json").exists():
        _progress(f"Downloading pinned model to {model_dir}")
        model_dir = download_pasketti(model_dir)
    return PaskettiRecognizer(model_dir, device=device)


def run_evaluation(
    csv_path: Path,
    clips_dir: Path,
    model_dir: Path,
    *,
    device: str = "cpu",
    max_clips: Optional[int] = None,
) -> EvaluationReport:
    """Evaluate rows with an available reference and locally supplied clip."""
    rows = load_dataset(csv_path)
    if max_clips is not None:
        if max_clips < 1:
            raise ValueError("--max-clips must be at least 1.")
        rows = rows[:max_clips]

    clips_dir = clips_dir.resolve(strict=True)
    if not clips_dir.is_dir():
        raise ValueError(f"Clips path is not a directory: {clips_dir}")
    recognizer = None
    report = EvaluationReport(total_rows=len(rows))

    for index, row in enumerate(rows, start=1):
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

        # Paidologos uses angle markers for transcripts with alternatives.
        if "<" in actual_ipa or ">" in actual_ipa:
            result.status = "ambiguous_reference"
            continue
        ref_phones = to_base_phones(actual_ipa)
        result.ref_phones = ref_phones
        if not ref_phones:
            result.status = "no_reference"  # nothing to grade against
            continue

        audio_path = resolve_clip(clips_dir, clip_file)
        if audio_path is None:
            result.status = "missing_audio"
            continue

        label = f"[{index}/{report.total_rows}] {audio_path.name}"
        _progress(f"{label} started")
        started = perf_counter()
        try:
            audio = load_audio(audio_path)
        except (OSError, RuntimeError, ValueError) as exc:
            result.status = "invalid_audio"
            _progress(f"{label} finished in {perf_counter() - started:.2f}s, invalid audio: {exc}")
            continue

        if recognizer is None:
            _progress(f"Loading Pasketti model on {device}")
            model_started = perf_counter()
            recognizer = _load_recognizer(model_dir, device)
            model_elapsed = perf_counter() - model_started
            _progress(f"Pasketti model ready in {model_elapsed:.2f}s")
            started += model_elapsed
        try:
            recognition = recognizer.recognize(audio)
        except (RuntimeError, ValueError) as exc:
            result.status = "unassessable_model"
            _progress(f"{label} finished in {perf_counter() - started:.2f}s, inference failed: {exc}")
            continue

        result.pred_phones = to_base_phones(recognition["phonetic_transcription"])
        result.status = "unassessable_model"
        if recognition["status"] == "ok" and result.pred_phones:
            result.edits = levenshtein(ref_phones, result.pred_phones)
            result.status = "assessed"

        _progress(f"{label} finished in {perf_counter() - started:.2f}s, {result.status}")

    return report


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def _write_csv_report(path: Path, report: EvaluationReport) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "session_id", "utterance_id", "word", "clip_file", "actual_ipa",
            "status", "ref_phones", "pred_phones", "accuracy", "phone_error_rate",
        ])
        for r in report.results:
            error_rate = r.phone_error_rate
            writer.writerow([
                r.session_id, r.utterance_id, r.word, r.clip_file, r.actual_ipa,
                r.status, "|".join(r.ref_phones), "|".join(r.pred_phones),
                "" if error_rate is None else f"{1 - error_rate:.4f}",
                "" if error_rate is None else f"{error_rate:.4f}",
            ])


def print_summary(report: EvaluationReport) -> None:
    """Print error rates and counts to stdout."""
    print("\n=== Pasketti model evaluation ===")
    print(f"Rows read              : {report.total_rows}")
    for status, n in report.counts.items():
        print(f"  {status:<20}: {n}")

    assessed = len(report.assessed)
    print(f"Assessed clips         : {assessed}/{report.total_rows}")
    if not assessed:
        print("No clips could be assessed. Check the clip paths and row statuses.")
        return

    print(f"Corpus phone error rate: {report.phone_error_rate:.2%}")
    print(f"Mean clip error rate   : {report.mean_clip_phone_error_rate:.2%}")
    print(f"Exact phone-seq match  : {report.exact_match_rate:.2%}")


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

    try:
        report = run_evaluation(
            args.csv, args.clips_dir, args.model_dir,
            device=args.device, max_clips=args.max_clips,
        )
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 2
    print_summary(report)

    if args.out_dir is not None:
        out_path = Path(args.out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        csv_out = out_path / "pasketti_evaluation_results.csv"
        _write_csv_report(csv_out, report)
        json_out = out_path / "pasketti_evaluation_summary.json"
        mean_error = report.mean_clip_phone_error_rate
        corpus_error = report.phone_error_rate
        summary = {
            "total_rows": report.total_rows,
            "counts": report.counts,
            "mean_clip_phone_error_rate": mean_error,
            "phone_error_rate": corpus_error,
            "overall_phone_accuracy": None if mean_error is None else 1 - mean_error,
            "token_level_accuracy": None if corpus_error is None else 1 - corpus_error,
            "exact_match_rate": report.exact_match_rate,
        }
        json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nWrote per-clip results -> {csv_out}")
        print(f"Wrote summary JSON     -> {json_out}")

    return 0 if report.assessed else 2


if __name__ == "__main__":
    raise SystemExit(main())