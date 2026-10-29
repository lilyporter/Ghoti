"""Assess generated comparison recordings using one resident model.

Run after New-ComparisonAudio.ps1 from engine/: python scripts/Assess-ComparisonAudio.py
Writes local WAV/JSON comparison fixtures; does not modify the frontend source.
"""

import argparse
import base64
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from pronouncedfish_engine import PaskettiRecognizer, assess, load_audio


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=root / "examples/synthetic-soa")
    parser.add_argument("--model-dir", type=Path, default=root / "models/pasketti-phonetic")
    args = parser.parse_args()
    manifest = json.loads((args.directory / "manifest.json").read_bytes())
    model = PaskettiRecognizer(args.model_dir)
    examples = []
    summary = ["Synthetic adult comparison recordings, not a clinical validation set.",
               "Open the individual JSON files in frontend-demo.html for audio and results.",
               "Synthesis prompts describe intended changes; model predictions and alignments are retained unchanged.", ""]
    for fixture in manifest["fixtures"]:
        wav = args.directory / fixture["audio_file"]
        result = assess(model, load_audio(wav), fixture["expected_phones"])
        result["demo_metadata"] = {
            "label": fixture["label"], "target_word": fixture["target_word"],
            "synthetic": True, "voice": manifest["voice"],
            "spoken_text": fixture["spoken_text"], "intended_change": fixture["intended_change"],
            "syllables": fixture["syllables"],
            "audio_data_url": "data:audio/wav;base64," + base64.b64encode(wav.read_bytes()).decode("ascii"),
        }
        (args.directory / (fixture["id"] + ".json")).write_text(
            json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False), encoding="utf-8"
        )
        examples.append({"id": fixture["id"], "label": fixture["label"],
                         "caption": fixture["spoken_text"] + " vs target " + fixture["target_word"],
                         "analysis": result["analysis"], "payload": result})
        summary.extend([fixture["id"] + " | spoken: " + fixture["spoken_text"] + " | target: " + fixture["target_word"],
                        "Recognized IPA: " + result["recognition"]["phonetic_transcription"],
                        "Observed counts: " + json.dumps(result["analysis"]["edit_counts"]), ""])
        print(fixture["id"], "recognized:", ascii(result["recognition"]["recognized_phones"]),
              "counts:", result["analysis"]["edit_counts"],
              "acoustic:", result["acoustic_assessment"]["status"], flush=True)
    (args.directory / "comparison-examples.json").write_text(
        json.dumps(examples, ensure_ascii=True, allow_nan=False), encoding="utf-8"
    )
    (args.directory / "README.txt").write_text("\n".join(summary), encoding="utf-8")
    with ZipFile(args.directory / "comparison-pack.zip", "w", ZIP_DEFLATED) as archive:
        for pattern in ("*.wav", "*.json", "*.txt"):
            for path in sorted(args.directory.glob(pattern)):
                archive.write(path, path.name)
    print("Saved results and comparison-examples.json to", args.directory)


if __name__ == "__main__":
    main()
