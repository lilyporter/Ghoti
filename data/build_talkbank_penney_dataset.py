import csv
import zipfile
import wave
from pathlib import Path
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright
from auth.talkbank_auth import authenticate


# ============================================================
# CONFIGURATION
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

BASE_DIR = SCRIPT_DIR / "talkbank_penney"

TRANSCRIPT_DIR = BASE_DIR / "transcripts"
AUDIO_DIR = BASE_DIR / "audio"
CLIPS_DIR = BASE_DIR / "clips"

ZIP_PATH = BASE_DIR / "Penney.zip"
CSV_PATH = BASE_DIR / "dataset.csv"

TRANSCRIPT_URL = (
    "https://talkbank.org/data/phon/Eng-NA/Penney?f=zip"
)

# This is the browsing page containing the WAV download links.
MEDIA_URL = (
    "https://sla.talkbank.org/TBB/phon/Eng-NA/Penney/CHAT/PictureNaming/"
)

AUTH_FILE = SCRIPT_DIR / "auth/talkbank_auth.json"


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

    # Download the ZIP only if it does not already exist.
    if not ZIP_PATH.exists():
        print("Downloading transcript ZIP...")

        response = context.request.get(TRANSCRIPT_URL, timeout=120000)
        if not response.ok:
            raise RuntimeError(
                f"Transcript download failed with HTTP status {response.status}"
            )

        data = response.body()
        if not zipfile.is_zipfile(__import__("io").BytesIO(data)):
            raise RuntimeError(
                "The downloaded transcript response is not a valid ZIP. "
                "The TalkBank login may have expired or the URL may be unavailable."
            )

        ZIP_PATH.write_bytes(data)

    # Make sure the downloaded file is a valid ZIP.
    if not zipfile.is_zipfile(ZIP_PATH):
        raise RuntimeError(
            "The downloaded transcript file is not a valid ZIP. "
            "Delete the ZIP and run the script again."
        )

    # Check whether the expected XML directory already contains files.
    expected_xml_dir = TRANSCRIPT_DIR / "Phon" / "PictureNaming"

    if expected_xml_dir.exists() and any(expected_xml_dir.glob("*.xml")):
        print("Transcripts already extracted. Skipping extraction.")
        return

    print("Extracting transcript ZIP...")

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:
        # Check ZIP paths to prevent unsafe extraction.
        for member in archive.infolist():
            destination = (TRANSCRIPT_DIR / member.filename).resolve()

            if not destination.is_relative_to(TRANSCRIPT_DIR.resolve()):
                raise RuntimeError("Unsafe ZIP file path detected.")

        archive.extractall(TRANSCRIPT_DIR)

    print("Transcript extraction complete.")


# ============================================================
# DOWNLOAD AUDIO FILES
# ============================================================


def download_audio(context):
    print("\n--- Downloading audio files ---")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Find all XML sessions in the PictureNaming directory.
    phon_dir = TRANSCRIPT_DIR / "Phon" / "PictureNaming"
    xml_files = sorted(phon_dir.glob("*.xml"))

    session_ids = [xml_file.stem for xml_file in xml_files]

    print(f"Found {len(session_ids)} sessions.")

    downloaded = 0
    skipped = 0
    failed = 0

    for i, session_id in enumerate(session_ids, start=1):
        filename = f"{session_id}.wav"
        destination = AUDIO_DIR / filename

        if destination.exists():
            print(f"[{i}/{len(session_ids)}] Already exists: {filename}")
            skipped += 1
            continue

        url = (
            "https://media.talkbank.org/phon/Eng-NA/"
            f"Penney/CHAT/PictureNaming/{filename}?f=save"
        )

        try:
            response = context.request.get(url, timeout=120000)
            data = response.body()

            if response.status != 200 or not data.startswith(b"RIFF"):
                print(f"[{i}/{len(session_ids)}] FAILED: {filename}")
                print("    Status:", response.status)
                print("    Content type:", response.headers.get("content-type"))
                print("    First 20 bytes:", data[:20])
                failed += 1
                continue

            destination.write_bytes(data)
            print(f"[{i}/{len(session_ids)}] Downloaded: {filename}")
            downloaded += 1

        except Exception as error:
            print(f"[{i}/{len(session_ids)}] ERROR: {filename}")
            print("   ", error)
            failed += 1

    print("\n--- Audio download summary ---")
    print("Downloaded:", downloaded)
    print("Already existed:", skipped)
    print("Failed:", failed)
    print("Total sessions:", len(session_ids))


# ============================================================
# XML HELPER FUNCTIONS
# ============================================================

def tag_name(element):
    """Return an XML tag name without its namespace."""

    return element.tag.split("}")[-1]


def find_children(element, name):
    """Find all descendants with the specified tag name."""

    return [
        child
        for child in element.iter()
        if tag_name(child) == name
    ]


def find_first(element, name):
    """Find the first descendant with the specified tag name."""

    for child in element.iter():
        if tag_name(child) == name:
            return child

    return None


def get_text(element):
    """Get all text contained within an XML element."""

    if element is None:
        return ""

    return "".join(element.itertext()).strip()


# ============================================================
# IPA EXTRACTION
# ============================================================

def extract_ipa(element):
    """
    Reconstruct an IPA transcription from the phonetic XML.

    This first-pass implementation collects the relevant
    phonetic elements in document order.
    """

    if element is None:
        return ""

    ipa_parts = []

    relevant_tags = {
        "stress",
        "base",
        "phlen",
        "suffix"
    }

    for child in element.iter():

        name = tag_name(child)

        if name in relevant_tags:
            value = get_text(child)

            if value:
                ipa_parts.append(value)

    return "".join(ipa_parts)


# ============================================================
# PARTICIPANT INFORMATION
# ============================================================

def format_age(value):
    """
    Convert an XML duration such as P6Y1M15D
    into 6;01;15 (years;months;days).
    """
    import re

    match = re.search(
        r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?",
        value or ""
    )

    if not match:
        return value or ""

    years = int(match.group(1) or 0)
    months = int(match.group(2) or 0)
    days = int(match.group(3) or 0)

    return f"{years};{months:02d};{days:02d}"

def extract_participants(root):
    """
    Extract participant metadata from the session XML.

    Returns a dictionary indexed by participant ID.
    """

    participants = {}

    for participant in find_children(root, "participant"):

        participant_id = participant.attrib.get("id", "")

        role = get_text(find_first(participant, "role"))
        name = get_text(find_first(participant, "name"))
        sex = get_text(find_first(participant, "sex"))
        age = format_age(get_text(find_first(participant, "age"))
)
        languages = get_text(find_first(participant, "languages"))

        participants[participant_id] = {
            "participant_id": participant_id,
            "role": role,
            "name": name,
            "sex": sex,
            "age": age,
            "languages": languages
        }

    return participants


# ============================================================
# TIMESTAMP EXTRACTION
# ============================================================

def extract_segment_times(record):
    """
    Extract the first segment's start and end timestamps.

    The XML may express timestamps in milliseconds or seconds.
    """

    segment = find_first(record, "segment")

    if segment is None:
        return None, None

    start = segment.attrib.get("start")
    end = segment.attrib.get("end")
    unit = segment.attrib.get("unit", "ms").lower()

    if start is None or end is None:
        return None, None

    try:
        start = float(start)
        end = float(end)

    except ValueError:
        return None, None

    if unit in ("s", "sec", "seconds"):
        start *= 1000
        end *= 1000

    return start, end


# ============================================================
# PARSE ONE XML FILE
# ============================================================

def parse_xml_file(xml_path):
    """
    Parse a single PictureNaming XML file.

    Extracts one-word utterances spoken by the target child.
    """

    print("Parsing:", xml_path.name)

    tree = ET.parse(xml_path)
    root = tree.getroot()

    session_id = root.attrib.get("name", xml_path.stem)

    media_location = get_text(
        find_first(root, "mediaLocation")
    )

    participants = extract_participants(root)

    records = []

    for utterance in find_children(root, "r"):

        speaker = utterance.attrib.get("speaker", "")

        # Only use the target child.
        if speaker != "CHI":
            continue

        utterance_id = utterance.attrib.get("id", "")

        # ----------------------------------------------------
        # Extract the written word.
        # ----------------------------------------------------

        orthography = find_first(utterance, "orthography")

        if orthography is None:
            continue

        words = find_children(orthography, "w")

        # Keep only utterances containing exactly one word.
        if len(words) != 1:
            continue

        word = get_text(words[0])

        if not word:
            continue

        # ----------------------------------------------------
        # Extract target IPA.
        # ----------------------------------------------------

        target_element = find_first(utterance, "ipaTarget")
        target_ipa = extract_ipa(target_element)

        # ----------------------------------------------------
        # Extract actual IPA.
        # ----------------------------------------------------

        actual_element = find_first(utterance, "ipaActual")
        actual_ipa = extract_ipa(actual_element)

        # Skip records without both transcriptions.
        if not target_ipa or not actual_ipa:
            continue

        # ----------------------------------------------------
        # Extract timestamps.
        # ----------------------------------------------------

        start_ms, end_ms = extract_segment_times(utterance)

        # ----------------------------------------------------
        # Extract participant information.
        # ----------------------------------------------------

        participant = participants.get(speaker, {})

        records.append({
            "session_id": session_id,
            "utterance_id": utterance_id,
            "age": participant.get("age", ""),
            "sex": participant.get("sex", ""),
            "word": word,
            "target_ipa": target_ipa,
            "actual_ipa": actual_ipa,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "source_xml": str(xml_path.relative_to(BASE_DIR))
        })

    return records


# ============================================================
# FIND MATCHING AUDIO FILE
# ============================================================

def find_audio(record):
    """
    Find the audio file corresponding to an XML record.

    Tries the XML mediaLocation first, then the session ID.
    """

    possible_names = []

    media_location = record.get("media_location", "")
    session_id = record.get("session_id", "")

    if media_location:
        possible_names.append(media_location)

    if session_id:
        possible_names.append(session_id)

    for name in possible_names:

        # Remove any extension if one is already present.
        name = Path(name).stem

        candidate = AUDIO_DIR / f"{name}.wav"

        if candidate.exists():
            return candidate

    return None


# ============================================================
# CROP AUDIO CLIP
# ============================================================

def crop_audio(audio_path, start_ms, end_ms, output_path):
    """
    Crop a WAV file using start and end timestamps in milliseconds.

    The WAV file must be readable by Python's wave module.
    """

    if start_ms is None or end_ms is None:
        return False

    if end_ms <= start_ms:
        return False

    try:
        with wave.open(str(audio_path), "rb") as source:

            params = source.getparams()
            sample_rate = source.getframerate()

            start_frame = int(
                start_ms / 1000 * sample_rate
            )

            end_frame = int(
                end_ms / 1000 * sample_rate
            )

            total_frames = source.getnframes()

            start_frame = max(0, start_frame)
            end_frame = min(total_frames, end_frame)

            if end_frame <= start_frame:
                return False

            source.setpos(start_frame)

            frames = source.readframes(
                end_frame - start_frame
            )

        with wave.open(str(output_path), "wb") as output:

            output.setparams(params)
            output.writeframes(frames)

        return True

    except (wave.Error, OSError) as error:
        print("Could not crop audio:", audio_path.name, error)
        return False


# ============================================================
# BUILD DATASET
# ============================================================

def build_dataset():
    print("\n--- Building dataset ---")

    # Only process XML files in the PictureNaming directory.
    phon_dir = TRANSCRIPT_DIR / "Phon" / "PictureNaming"

    xml_files = sorted(phon_dir.glob("*.xml"))

    if not xml_files:
        print("No XML files found in:", phon_dir.resolve())
        return

    print(f"Found {len(xml_files)} XML files.")

    all_records = []

    for xml_path in xml_files:

        try:
            records = parse_xml_file(xml_path)
            all_records.extend(records)

        except ET.ParseError as error:
            print("XML parsing failed:", xml_path.name, error)

    print(f"\nExtracted {len(all_records)} word records.")

    # --------------------------------------------------------
    # Match audio files and crop individual utterances.
    # --------------------------------------------------------

    for record in all_records:

        audio_path = find_audio(record)

        if audio_path is None:
            print(
                "No audio found for:",
                record["session_id"],
                record["utterance_id"]
            )

            record["source_audio"] = ""
            record["clip_file"] = ""
            continue

        record["source_audio"] = str(audio_path.relative_to(BASE_DIR))

        # Create a unique filename for each clip.
        clip_filename = (
            f'{record["session_id"]}_'
            f'{record["utterance_id"]}.wav'
        )

        clip_path = CLIPS_DIR / clip_filename

        if clip_path.exists():
            record["clip_file"] = str(clip_path.relative_to(BASE_DIR))
            continue

        success = crop_audio(
            audio_path,
            record["start_ms"],
            record["end_ms"],
            clip_path
        )

        if success:
            record["clip_file"] = clip_filename

        else:
            record["clip_file"] = ""
            print(
                "Could not create clip for:",
                record["session_id"],
                record["utterance_id"]
            )

    # --------------------------------------------------------
    # Write CSV.
    # --------------------------------------------------------

    columns = [
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

    with open(
        CSV_PATH,
        "w",
        newline="",
        encoding="utf-8"
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=columns,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(all_records)

    print("\nDataset creation complete.")
    print("CSV saved to:", CSV_PATH.resolve())
    print("Audio directory:", AUDIO_DIR.resolve())
    print("Clips directory:", CLIPS_DIR.resolve())


# ============================================================
# MAIN
# ============================================================

def main():
    """Run the Penney extraction using the shared saved TalkBank login."""

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

    build_dataset()


if __name__ == "__main__":
    main()
