"""Explicit asset download and offline local-file recognition commands."""

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
    args = parser.parse_args()
    try:
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
        result = engine.recognize(audio)
        total_ms = (perf_counter() - started) * 1000
        # Standard output is intentional local CLI output; no files or telemetry.
        # Use UTF-8 for redirected output too, including legacy Windows terminals.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(
            f"model_load_ms={load_ms:.1f} preprocessing_ms={preprocessing_ms:.1f} "
            f"processing_ms={total_ms:.1f}", file=sys.stderr,
        )
        return 0 if result["status"] == "ok" else 2
    except ImportError as error:
        print(
            "Recognition dependencies are missing or incompatible. "
            "Install with: python -m pip install . "
            f"({type(error).__name__})", file=sys.stderr,
        )
        return 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Engine error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
