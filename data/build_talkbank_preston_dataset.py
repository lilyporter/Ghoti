"""
Build a Preston TalkBank dataset using the existing talkbank_auth.json.

Output: talkbank_preston/{transcripts,audio,clips,Preston.zip,dataset.csv}
"""
import csv
import io
import re
import wave
import zipfile
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright
from auth.talkbank_auth import authenticate

BASE_DIR = Path(__file__).resolve().parent
AUTH_STATE = BASE_DIR / "auth/talkbank_auth.json"
OUTPUT_DIR = BASE_DIR / "talkbank_preston"
TRANSCRIPTS_DIR = OUTPUT_DIR / "transcripts"
AUDIO_DIR = OUTPUT_DIR / "audio"
CLIPS_DIR = OUTPUT_DIR / "clips"
ZIP_PATH = OUTPUT_DIR / "Preston.zip"
CSV_PATH = OUTPUT_DIR / "dataset.csv"

TRANSCRIPT_URL = "https://talkbank.org/data/phon/Clinical/Preston?f=zip"
AUDIO_BASE_URL = "https://media.talkbank.org/phon/Clinical/Preston/CHAT"

CSV_COLUMNS = [
    "session_id", "utterance_id", "age", "sex",
    "word", "target_ipa", "actual_ipa", "start_ms", "end_ms",
    "source_xml", "source_audio", "clip_file",
]


def lname(tag):
    return tag.rsplit("}", 1)[-1]


def descendants(element, name):
    return [node for node in element.iter() if lname(node.tag) == name]


def text_of(element, name):
    nodes = descendants(element, name)
    return (nodes[0].text or "").strip() if nodes else ""


def tier_word(utterance, tier_name, form=None):
    for tier in utterance.iter():
        if lname(tier.tag) == tier_name and (
            form is None or tier.attrib.get("form") == form
        ):
            words = descendants(tier, "w")
            if words:
                return (words[0].text or "").strip()
    return ""


def format_age(value):
    match = re.search(r"P(?:(\d+)Y)?(?:(\d+)M)?", value or "")
    if not match:
        return value or ""
    return f'{int(match.group(1) or 0)};{int(match.group(2) or 0):02d}'


def participant_metadata(root):
    participants = descendants(root, "participant")
    for participant in participants:
        role = text_of(participant, "role").lower()
        pid = participant.attrib.get("id", "")
        if "target" in role or pid.upper() == "CHI":
            return (
                pid,
                format_age(text_of(participant, "age")),
                text_of(participant, "sex"),
                text_of(participant, "language"),
            )
    if participants:
        p = participants[0]
        return (
            p.attrib.get("id", ""),
            format_age(text_of(p, "age")),
            text_of(p, "sex"),
            text_of(p, "language"),
        )
    return "", "", "", ""


def download_transcript_zip(context):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists() and zipfile.is_zipfile(ZIP_PATH):
        print(f"Using existing ZIP: {ZIP_PATH}")
        return
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    print("Downloading Preston transcript ZIP...")
    response = context.request.get(TRANSCRIPT_URL, timeout=180000)
    if not response.ok:
        raise RuntimeError(f"Transcript ZIP download failed: HTTP {response.status}")

    data = response.body()
    if not zipfile.is_zipfile(io.BytesIO(data)):
        preview = data[:250].decode("utf-8", errors="replace")
        raise RuntimeError(f"Response is not a valid ZIP. Preview: {preview}")

    ZIP_PATH.write_bytes(data)
    print(f"Saved {ZIP_PATH}")


def extract_zip_safely():
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    base = TRANSCRIPTS_DIR.resolve()
    with zipfile.ZipFile(ZIP_PATH) as archive:
        for member in archive.infolist():
            destination = (TRANSCRIPTS_DIR / member.filename).resolve()
            if destination != base and base not in destination.parents:
                raise RuntimeError(f"Unsafe ZIP path: {member.filename}")
        archive.extractall(TRANSCRIPTS_DIR)
    print(f"Extracted transcripts to {TRANSCRIPTS_DIR}")


def download_audio(context, filename):
    filename = Path(filename).name
    path = AUDIO_DIR / filename
    if path.exists():
        try:
            with wave.open(str(path), "rb"):
                return path
        except (wave.Error, EOFError):
            path.unlink()

    url = f"{AUDIO_BASE_URL}/{quote(filename)}?f=save"
    response = context.request.get(url, timeout=180000)
    if not response.ok:
        print(f"Audio download failed for {filename}: HTTP {response.status}")
        return None

    data = response.body()
    if not data.startswith(b"RIFF") or b"WAVE" not in data[:16]:
        preview = data[:120].decode("utf-8", errors="replace")
        print(f"{filename} was not returned as WAV. Response: {preview}")
        return None

    path.write_bytes(data)
    try:
        with wave.open(str(path), "rb"):
            pass
    except (wave.Error, EOFError) as error:
        print(f"Invalid WAV {filename}: {error}")
        path.unlink(missing_ok=True)
        return None
    print(f"Downloaded {filename}")
    return path


def crop_audio(audio_path, start_ms, end_ms, output_path):
    try:
        with wave.open(str(audio_path), "rb") as source:
            params = source.getparams()
            rate = source.getframerate()
            first = max(0, int(float(start_ms) * rate / 1000))
            last = min(source.getnframes(), int(float(end_ms) * rate / 1000))
            if last <= first:
                return False
            source.setpos(first)
            frames = source.readframes(last - first)
        with wave.open(str(output_path), "wb") as output:
            output.setparams(params)
            output.writeframes(frames)
        return True
    except (wave.Error, EOFError, OSError, ValueError) as error:
        print(f"Could not crop {audio_path.name}: {error}")
        return False


def parse_xml(xml_path):
    root = ET.parse(xml_path).getroot()
    session_id = root.attrib.get("id", xml_path.stem)
    header = next((n for n in root.iter() if lname(n.tag) == "header"), root)
    audio_path = BASE_DIR / AUDIO_DIR / Path(text_of(header, "media") or f"{session_id}.wav")
    audio_name = audio_path.name
    pid, age, sex, participant_language = participant_metadata(root)
    languages = participant_language or text_of(header, "language")

    records = []
    for number, utterance in enumerate(descendants(root, "u"), start=1):
        segment = next(
            (n for n in utterance.iter() if lname(n.tag) == "segment"), None
        )
        start_ms = end_ms = ""
        if segment is not None:
            try:
                start = float(segment.attrib["startTime"])
                duration = float(segment.attrib["duration"])
                start_ms = round(start, 3)
                end_ms = round(start + duration, 3)
            except (KeyError, TypeError, ValueError):
                pass

        records.append({
            "session_id": session_id,
            "utterance_id": f"u{number - 1}",
            "age": age,
            "sex": sex,
            "word": tier_word(utterance, "orthography"),
            "target_ipa": tier_word(utterance, "ipaTier", "model"),
            "actual_ipa": tier_word(utterance, "ipaTier", "actual"),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "source_xml": str(xml_path.relative_to(OUTPUT_DIR)),
            "source_audio": str(audio_path.relative_to(OUTPUT_DIR)),
            "clip_file": "",
        })
    return session_id, audio_name, records


def build_dataset(context):
    xml_files = sorted(TRANSCRIPTS_DIR.glob("Preston/Phon/Preston/*.xml"))
    if not xml_files:
        xml_files = sorted(TRANSCRIPTS_DIR.glob("Phon/Preston/*.xml"))
    if not xml_files:
        raise FileNotFoundError(
            "No XML files found. Expected Preston/Phon/Preston/P##.xml "
            "inside the extracted ZIP."
        )

    print(f"Found {len(xml_files)} XML files.")
    all_records = []

    for xml_path in xml_files:
        print(f"\nProcessing {xml_path.name}...")
        try:
            session_id, audio_name, records = parse_xml(xml_path)
        except (ET.ParseError, OSError) as error:
            print(f"Skipping {xml_path.name}: {error}")
            continue

        audio_path = download_audio(context, audio_name)
        for record in records:
            if audio_path is not None and record["start_ms"] != "":
                clip_name = f'{session_id}_{record["utterance_id"]}.wav'
                clip_path = CLIPS_DIR / clip_name
                if clip_path.exists() or crop_audio(
                    audio_path, record["start_ms"], record["end_ms"], clip_path
                ):
                    record["clip_file"] = str(clip_path.relative_to(OUTPUT_DIR))
            all_records.append(record)

        print(f"Added {len(records)} utterances from {session_id}.")

    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_records)

    print("\nPreston extraction finished.")
    print(f"Sessions: {len(xml_files)}")
    print(f"Utterances: {len(all_records)}")
    print(f"Clips: {sum(bool(r['clip_file']) for r in all_records)}")
    print(f"CSV: {CSV_PATH}")


def main():
    if not AUTH_STATE.exists():
        authenticate()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(AUTH_STATE))
        try:
            download_transcript_zip(context)
            extract_zip_safely()
            build_dataset(context)
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
