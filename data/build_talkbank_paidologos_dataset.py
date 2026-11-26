import csv
import re
import zipfile
import wave
from datetime import date
from pathlib import Path
import xml.etree.ElementTree as ET
import eng_to_ipa as ipa

from playwright.sync_api import sync_playwright
from auth.talkbank_auth import authenticate


# ============================================================
# CONFIGURATION
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

BASE_DIR = SCRIPT_DIR / "talkbank_paidologos"

TRANSCRIPT_DIR = BASE_DIR / "transcripts"
AUDIO_DIR = BASE_DIR / "audio"
CLIPS_DIR = BASE_DIR / "clips"

ZIP_PATH = BASE_DIR / "PaidoEnglish.zip"
CSV_PATH = BASE_DIR / "dataset.csv"

# This is the link containing the transcript zip file
TRANSCRIPT_URL = (
    "https://talkbank.org/data/phon/Eng-NA/PaidoEnglish?f=zip"
)

# This is the browsing page to the browsable dataset, used to authenticate the browser.
MEDIA_URL = (
    "https://sla.talkbank.org/TBB/phon/Eng-NA/PaidoEnglish/CHAT"
)

MEDIA_BASE_URL = "https://media.talkbank.org/phon/Eng-NA/PaidoEnglish"

AUTH_FILE = SCRIPT_DIR / "auth/talkbank_auth.json"

AGES = ["4a","4b","5a","5b"]

# ============================================================
# DIRECTORY SETUP
# ============================================================

def setup_directories():
    """Create the required directories if they do not exist."""

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# DOWNLOAD AND EXTRACT TRANSCRIPTS
# ============================================================

def download_transcripts(context):
    print("\n--- Downloading transcripts ---")

    # Check whether the ZIP already exists and is valid.
    if ZIP_PATH.exists():
        if zipfile.is_zipfile(ZIP_PATH):
            print("Transcript ZIP already exists and is valid.")
            return

        print("Existing ZIP is invalid. Deleting it.")
        ZIP_PATH.unlink()

    print("Downloading transcript ZIP...")

    response = context.request.get(TRANSCRIPT_URL, timeout=60000)
    if not response.ok:
        raise Exception(f"Download failed with HTTP status {response.status}")

    data = response.body()

    if not zipfile.is_zipfile(__import__("io").BytesIO(data)):
        print("ERROR: Response is not a valid ZIP.")
        print(data[:500].decode("utf-8", errors="replace"))
        return

    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    ZIP_PATH.write_bytes(data)

    print("Transcript ZIP downloaded successfully.")
    print("Saved to:", ZIP_PATH)

    # Check whether the expected XML directory already contains files.
    # Checks if one of the dirs is empty, all will be
    expected_xml_dir = TRANSCRIPT_DIR / "Phon" / "5a"
    if expected_xml_dir.exists() and any(expected_xml_dir.glob("*.xml")):
        print("Transcripts already extracted. Skipping extraction.")
        return

    print("Extracting transcript ZIP...")

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:

        # Check ZIP paths to prevent unsafe extraction.
        for member in archive.infolist():
            destination = (
                TRANSCRIPT_DIR / member.filename
            ).resolve()

            if not destination.is_relative_to(
                TRANSCRIPT_DIR.resolve()
            ):
                raise RuntimeError(
                    "Unsafe ZIP file path detected."
                )

        archive.extractall(TRANSCRIPT_DIR)

    print("Transcript extraction complete.")

# ============================================================
# DOWNLOAD AUDIO FILES
# ============================================================


def download_audio(context):

    print("\n--- Downloading audio files ---")

    # Ensure audio directory exists.
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    for age_group in AGES:

        xml_dir = TRANSCRIPT_DIR / "Phon" / age_group

        if not xml_dir.exists():
            print(f"Missing directory: {xml_dir}")
            continue

        xml_files = sorted(xml_dir.glob("*.xml"))

        print(f"\n--- Downloading audio for {age_group} ---")

        for xml_file in xml_files:

            try:
                # Read session ID from XML.
                tree = ET.parse(xml_file)
                root = tree.getroot()

                session_id = root.attrib.get("name", "")

                if not session_id:
                    session_id = get_child_text(root, "mediaLocation")

                if not session_id:
                    print(f"Could not find session ID: {xml_file.name}")
                    continue

                filename = f"{session_id}.wav"
                output_path = AUDIO_DIR / filename

                # Skip existing audio files.
                if output_path.exists():
                    print(f"Already downloaded: {filename}")
                    continue

                # Use your existing corrected PaidoEnglish media URL.
                url = (
                    f"https://media.talkbank.org/phon/Eng-NA/PaidoEnglish/CHAT/{age_group}/{filename}?f=save"
                )

                response = context.request.get(url, timeout=60000)

                if not response.ok:
                    print(f"Download failed: {filename} "
                          f"(HTTP {response.status})")
                    continue

                data = response.body()

                # Verify that the response is a WAV file.
                if not data.startswith(b"RIFF"):
                    print(f"Invalid WAV response: {filename}")
                    continue

                output_path.write_bytes(data)

                print(f"Downloaded: {filename}")

            except Exception as error:
                print(f"Error processing {xml_file.name}: {error}")

    print("\nAudio downloading complete.")


# ============================================================
# XML HELPERS
# ============================================================

def get_tag_name(element):
    """Return an XML tag without its namespace."""
    return element.tag.split("}")[-1]


def get_child(element, tag_name):
    """Find a direct child by its tag name, ignoring namespaces."""
    for child in element:
        if get_tag_name(child) == tag_name:
            return child

    return None


def get_child_text(element, tag_name):
    """Get the text of a direct child element."""
    child = get_child(element, tag_name)

    if child is None or child.text is None:
        return ""

    return child.text.strip()


def calculate_age(birthday_text, session_date_text):
    """
    Calculate age at the time of recording.

    Returns age in years;months format.
    Example: 5;03 means 5 years and 3 months.
    """
    if not birthday_text or not session_date_text:
        return ""

    birthday = date.fromisoformat(birthday_text)
    session_date = date.fromisoformat(session_date_text)

    months = (
        (session_date.year - birthday.year) * 12
        + session_date.month - birthday.month
    )

    if session_date.day < birthday.day:
        months -= 1

    years = months // 12
    remaining_months = months % 12

    return f"{years};{remaining_months:02d}"


def get_tier_text(utterance, tier_name):
    """
    Extract the transcription text from a user tier.

    Timestamp entries are excluded.
    """
    for tier in utterance:
        if (
            get_tag_name(tier) == "userTier"
            and tier.attrib.get("name") == tier_name
        ):
            transcription_parts = []

            for element in tier.iter():
                if get_tag_name(element) != "tw":
                    continue

                if element.text is None:
                    continue

                value = element.text.strip()

                # Ignore timestamp entries such as:
                # (000:35.485-000:36.285)
                if re.fullmatch(
                    r"\(\d{3}:\d{2}\.\d{3}-\d{3}:\d{2}\.\d{3}\)",
                    value
                ):
                    continue

                transcription_parts.append(value)

            return "".join(transcription_parts)

    return ""


# ============================================================
# PARSE ONE PAIDOENGLISH XML FILE
# ============================================================

def parse_xml_file(xml_path):
    """Extract utterance records from one PaidoEnglish XML file."""

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Session metadata
    session_id = root.attrib.get("name", "")

    if not session_id:
        session_id = get_child_text(root, "mediaLocation")

    session_date = get_child_text(root, "date")
    session_languages = get_child_text(root, "languages")
    media_location = get_child_text(root, "mediaLocation")

    # Participant metadata
    participants = {}

    participants_element = get_child(root, "participants")

    if participants_element is not None:
        for participant in participants_element:

            if get_tag_name(participant) != "participant":
                continue

            participant_id = participant.attrib.get("id", "")

            participants[participant_id] = {
                "sex": get_child_text(participant, "sex"),
                "languages": (
                    get_child_text(participant, "languages")
                    or session_languages
                ),
                "birthday": get_child_text(participant, "birthday")
            }

    records = []

    # Each <r> element represents one utterance.
    for utterance in root.iter():

        if get_tag_name(utterance) != "r":
            continue

        utterance_id = utterance.attrib.get("id", "")
        participant_id = utterance.attrib.get("speaker", "")

        participant = participants.get(participant_id, {})

        # Extract written word.
        orthography = get_child(utterance, "orthography")
        word = ""

        if orthography is not None:
            for element in orthography.iter():
                if get_tag_name(element) == "w" and element.text:
                    word += element.text.strip()

        # Extract utterance timestamps.
        segment = get_child(utterance, "segment")

        start_ms = ""
        end_ms = ""

        if segment is not None:
            start_seconds = segment.attrib.get("start")
            end_seconds = segment.attrib.get("end")

            if start_seconds is not None and end_seconds is not None:
                start_ms = round(float(start_seconds) * 1000)
                end_ms = round(float(end_seconds) * 1000)

        # Extract the word-level phonetic transcription.
        actual_ipa = get_tier_text(utterance, "wb")

        # Calculate participant age.
        age = calculate_age(
            participant.get("birthday", ""),
            session_date
        )

        # Construct filenames.
        source_audio = f"{session_id}.wav"
        source_audio_full_path = AUDIO_DIR/ source_audio
        clip_file = f"{session_id}_{utterance_id}.wav"
        clip_file_full_path = CLIPS_DIR / clip_file

        records.append({
            "session_id": session_id,
            "utterance_id": utterance_id,
            "age": age,
            "sex": participant.get("sex", ""),
            "word": word,
            "target_ipa": "", # not given in transcript so library can be used: ipa.convert(word)
            "actual_ipa": actual_ipa,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "source_xml": str(xml_path.relative_to(BASE_DIR)),
            "source_audio": str(source_audio_full_path.relative_to(BASE_DIR)),
            "clip_file": str(clip_file_full_path.relative_to(BASE_DIR))
        })

    return records

DATASET_COLUMNS = [
    "session_id",
    "utterance_id",
    "age",
    "sex",
    "word",
    "target_ipa",
    "actual_ipa",
    "start_ms",
    "end_ms",
    "source_xml",
    "source_audio",
    "clip_file"
]


def create_utterance_clip(record):
    """
    Crops one utterance from its original WAV file using
    the start_ms and end_ms timestamps.
    """

    audio_path = BASE_DIR / record["source_audio"]

    if not audio_path.exists():
        print(f"Missing audio: {audio_path.name}")
        return False

    if record["start_ms"] == "" or record["end_ms"] == "":
        print(f"Missing timestamps: {record['session_id']} "
              f"/ {record['utterance_id']}")
        return False

    start_ms = int(record["start_ms"])
    end_ms = int(record["end_ms"])

    if end_ms <= start_ms:
        print(f"Invalid timestamps: {record['session_id']} "
              f"/ {record['utterance_id']}")
        return False

    output_path = BASE_DIR / record["clip_file"]

    try:
        with wave.open(str(audio_path), "rb") as source:
            frame_rate = source.getframerate()
            total_frames = source.getnframes()

            start_frame = int(start_ms * frame_rate / 1000)
            end_frame = int(end_ms * frame_rate / 1000)

            # Keep timestamps within the audio file.
            start_frame = max(0, min(start_frame, total_frames))
            end_frame = max(0, min(end_frame, total_frames))

            if end_frame <= start_frame:
                print(f"Invalid audio segment: {output_path.name}")
                return False

            source.setpos(start_frame)
            frames = source.readframes(end_frame - start_frame)

            with wave.open(str(output_path), "wb") as clip:
                clip.setparams(source.getparams())
                clip.writeframes(frames)

        return True

    except wave.Error as error:
        print(f"Could not process {audio_path.name}: {error}")
        return False


def build_dataset():
    """
    Parses all XML files, creates utterance clips,
    and exports the dataset to CSV.
    """

    records = []

    # Process every age group.
    for age_group in AGES:
        xml_dir = TRANSCRIPT_DIR / "Phon" / age_group

        if not xml_dir.exists():
            print(f"Missing transcript directory: {xml_dir}")
            continue

        xml_files = sorted(xml_dir.rglob("*.xml"))

        print(f"\n{age_group}: Found {len(xml_files)} XML files.")

        for xml_file in xml_files:
            try:
                file_records = parse_xml_file(xml_file)
                records.extend(file_records)

                print(f"Parsed {xml_file.name}: "
                      f"{len(file_records)} utterances")

            except ET.ParseError as error:
                print(f"Could not parse {xml_file.name}: {error}")

    print(f"\nTotal XML utterances parsed: {len(records)}")

    # Create utterance-level audio clips.
    successful_clips = 0

    for record in records:
        if create_utterance_clip(record):
            successful_clips += 1
        else:
            # Don't reference a clip that wasn't created.
            record["clip_file"] = ""

    # Export CSV.
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=DATASET_COLUMNS
        )

        writer.writeheader()
        writer.writerows(records)

    print("\nDataset generation complete.")
    print(f"Total utterances: {len(records)}")
    print(f"Successful clips: {successful_clips}")
    print(f"CSV saved to: {CSV_PATH}")

    return records


def validate_dataset(records):
    """
    Checks that the generated dataset references
    existing audio files and clips.
    """

    missing_audio = 0
    missing_clips = 0
    missing_transcriptions = 0
    missing_timestamps = 0

    for record in records:

        if not (AUDIO_DIR / record["source_audio"]).exists():
            missing_audio += 1

        if not record["clip_file"]:
            missing_clips += 1
        elif not (CLIPS_DIR / record["clip_file"]).exists():
            missing_clips += 1

        if not record["actual_ipa"]:
            missing_transcriptions += 1

        if record["start_ms"] == "" or record["end_ms"] == "":
            missing_timestamps += 1

    print("\n========== DATASET VALIDATION ==========")
    print(f"Total records: {len(records)}")
    print(f"Missing original audio: {missing_audio}")
    print(f"Missing utterance clips: {missing_clips}")
    print(f"Missing transcriptions: {missing_transcriptions}")
    print(f"Missing timestamps: {missing_timestamps}")
    print("========================================")


def main():
    """Run the PaidoEnglish extraction using the shared saved TalkBank login."""

    setup_directories()

    if not AUTH_FILE.exists():
        authenticate()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(AUTH_FILE))

        try:
            download_transcripts(context)
            download_audio(context)
        finally:
            context.close()
            browser.close()

    records = build_dataset()
    validate_dataset(records)


if __name__ == "__main__":
    main()
