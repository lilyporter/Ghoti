"""Explicit asset download, offline recognition, and target comparison commands."""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter


def main() -> int:
    parser = argparse.ArgumentParser(prog="pronouncedfish-engine")
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download-model", help="Download pinned public model assets")
    download.add_argument("--model-dir", type=Path, default=Path("models/pasketti-phonetic"))
    recognize = commands.add_parser("recognize", help="Recognize an authorized local WAV/FLAC")
    recognize.add_argument("audio", type=Path)
    recognize.add_argument("--model-dir", type=Path, default=Path("models/pasketti-phonetic"))
    recognize.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    analysis = commands.add_parser("analyze", help="Compare saved recognition JSON with target phone tokens")
    analysis.add_argument("recognition", type=Path)
    analysis.add_argument("--expected-phones", nargs="+", required=True)
    analysis.add_argument("--acceptable-variant", nargs="+", action="append", default=[])
    analysis.add_argument("--supported-substitution", nargs=2, action="append", default=[])
    assessment = commands.add_parser("assess", help="Experimental acoustic evidence plus recognition and analysis")
    assessment.add_argument("audio", type=Path)
    assessment.add_argument("--model-dir", type=Path, default=Path("models/pasketti-phonetic"))
    assessment.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    assessment.add_argument("--expected-phones", nargs="+", required=True)
    assessment.add_argument("--acceptable-variant", nargs="+", action="append", default=[])
    assessment.add_argument("--supported-substitution", nargs=2, action="append", default=[])
    args = parser.parse_args()
    try:
        if args.command == "analyze":
            from .analysis import analyze

            # Decode JSON bytes directly: the standard library detects UTF-8,
            # UTF-16 (Windows PowerShell redirection), UTF-32, and their BOMs.
            recognition_result = json.loads(args.recognition.read_bytes())
            if (not isinstance(recognition_result, dict)
                    or recognition_result.get("status") not in ("ok", "unassessable")
                    or not isinstance(recognition_result.get("recognized_phones"), list)):
                raise ValueError("Expected recognition JSON with status and recognized_phones.")
            result = analyze(
                recognition_result, args.expected_phones,
                acceptable_variants=args.acceptable_variant,
                supported_substitutions=args.supported_substitution,
            )
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(json.dumps(result, ensure_ascii=not sys.stdout.isatty(), indent=2))
            return 0 if result["status"] == "ok" else 2
        if args.command == "download-model":
            from .assets import download_pasketti

            directory = download_pasketti(args.model_dir)
            print(f"Verified model assets saved to {directory}")
            return 0
        from .audio import load_audio
        from .pasketti import PaskettiRecognizer

        started = perf_counter()
        engine = PaskettiRecognizer(args.model_dir, device=args.device)
        load_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        audio = load_audio(args.audio)
        preprocessing_ms = (perf_counter() - started) * 1000
        if args.command == "assess":
            from .assessment import assess

            result = assess(engine, audio, args.expected_phones,
                            acceptable_variants=args.acceptable_variant,
                            supported_substitutions=args.supported_substitution)
        else:
            result = engine.recognize(audio)
        total_ms = (perf_counter() - started) * 1000
        # Standard output is intentional local CLI output; no files or telemetry.
        # Escape non-ASCII in redirected JSON: Windows PowerShell can decode a
        # native program's UTF-8 as an OEM code page before writing UTF-16.
        # Interactive terminals retain readable IPA; JSON readers restore escapes.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(result, ensure_ascii=not sys.stdout.isatty(), indent=2))
        print(
            f"model_load_ms={load_ms:.1f} preprocessing_ms={preprocessing_ms:.1f} "
            f"processing_ms={total_ms:.1f}", file=sys.stderr,
        )
        if args.command == "assess":
            return 0 if result["acoustic_assessment"]["status"] == "ok" else 2
        return 0 if result["status"] == "ok" else 2
    except ImportError as error:
        print(
            "Engine dependencies are missing or incompatible. "
            "Install with: python -m pip install '.[analysis]' "
            f"({type(error).__name__})", file=sys.stderr,
        )
        return 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Engine error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
