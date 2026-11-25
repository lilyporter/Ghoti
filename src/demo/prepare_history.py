"""Build demo history from recorded Penney sessions with the local engine."""

import argparse
import csv
import json
from pathlib import Path, PureWindowsPath
from shutil import copyfile

from pronouncedfish_engine import analyze, load_audio

from demo.api.main import SAMPLES, get_recognizer


SESSION_IDS = ("D10", "D38", "T44", "T65")
WORDS = ("boats", "glasses", "soap", "spoon", "star", "nose")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Path to Penney's dataset.csv")
    dataset = parser.parse_args().dataset
    with dataset.open(encoding="utf-8-sig", newline="") as source:
        rows = {(row["session_id"], row["word"]): row for row in csv.DictReader(source)}

    clips = SAMPLES / "penney"
    clips.mkdir(exist_ok=True)
    model = get_recognizer()
    sessions = []
    for session_id in SESSION_IDS:
        attempts = []
        for word in WORDS:
            row = rows[session_id, word]
            filename = PureWindowsPath(row["clip_file"]).name
            source = dataset.parent / "clips" / filename
            audio = load_audio(source)
            recognition = model.recognize(audio)
            # Penney uses an untied diphthong and marks vowel length.
            target = list(row["target_ipa"].replace("ː", "").replace("oʊ", "O"))
            target = ["o͡ʊ" if phone == "O" else phone for phone in target]
            analysis = analyze(recognition, target)
            attempts.append({
                "sample_id": Path(filename).stem,
                "target_word": word,
                "duration_seconds": round(len(audio.samples) / audio.sample_rate_hz, 2),
                "recognition": recognition,
                "analysis": {key: analysis[key] for key in (
                    "status", "matches_target", "expected_phones", "edit_counts",
                )} | {"alignment": [
                    {key: item[key] for key in (
                        "kind", "expected_index", "expected_phone", "recognized_phone",
                    )} for item in analysis["alignment"]
                ]},
            })
            copyfile(source, clips / filename)
        sessions.append({"id": session_id, "attempts": attempts})
        print(f"{session_id}: {len(attempts)} analyzed clips", flush=True)
    (SAMPLES.parent / "history.json").write_text(
        json.dumps(sessions, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
