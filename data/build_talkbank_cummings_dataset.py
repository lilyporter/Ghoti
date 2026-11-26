
import csv
import io
import re
import wave
import zipfile
import requests
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright
from auth.talkbank_auth import authenticate


# ============================================================
# CONFIGURATION
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

BASE_DIR = SCRIPT_DIR / "talkbank_cummings"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
AUDIO_DIR = BASE_DIR / "audio"
CLIPS_DIR = BASE_DIR / "clips"

ZIP_PATH = BASE_DIR / "Cummings.zip"
CSV_PATH = BASE_DIR / "dataset.csv"

AUTH_FILE = SCRIPT_DIR / "auth" / "talkbank_auth.json"

TRANSCRIPT_URL = (
    "https://talkbank.org/data/phon/Clinical/Cummings?f=zip"
)

AUDIO_BASE_URL = (
    "https://media.talkbank.org/phon/Clinical/Cummings/CHAT"
)

CSV_COLUMNS = [
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
    "clip_file",
]


# ============================================================
# DIRECTORY SETUP
# ============================================================

def setup_directories():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# XML HELPERS
# ============================================================

def lname(tag):
    """Return an XML tag without its namespace."""
    return tag.rsplit("}", 1)[-1]


def descendants(element, name):
    """Find all descendants with the specified tag name."""
    return [
        node for node in element.iter()
        if lname(node.tag) == name
    ]


def text_of(element, name):
    """Get the text of the first matching descendant."""
    nodes = descendants(element, name)
    return "".join(nodes[0].itertext()).strip() if nodes else ""


def tier_word(utterance, tier_name, form=None):
    """Extract the first word from a specified XML tier."""
    for tier in utterance.iter():
        if lname(tier.tag) != tier_name:
            continue

        if form is not None and tier.attrib.get("form") != form:
            continue

        words = descendants(tier, "w")

        if words:
            return "".join(words[0].itertext()).strip()

    return ""


# ============================================================
# AGE HANDLING
# ============================================================

def format_age(value):
    """
    Convert an XML duration such as P6Y9M21DT0H0M0S
    into 6;09;21 (years;months;days).
    """
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


def age_from_filename(filename):
    """
    Cummings filenames encode age as YYMMDD.

    Example:
        060921 = 6 years, 9 months, 21 days
    """
    stem = Path(filename).stem

    if not re.fullmatch(r"\d{6}", stem):
        return ""

    years = int(stem[0:2])
    months = int(stem[2:4])
    days = int(stem[4:6])

    return f"{years};{months:02d};{days:02d}"


def is_target_age(filename):
    """
    Only process filenames beginning with 04, 05, or 06.
    """
    stem = Path(filename).stem

    return (
        re.fullmatch(r"\d{6}", stem) is not None
        and stem[:2] in {"04", "05", "06"}
    )


# ============================================================
# DOWNLOAD AND EXTRACT TRANSCRIPTS
# ============================================================

def download_transcript_zip(context):
    print("\n--- Downloading Cummings transcript ZIP ---")

    if ZIP_PATH.exists() and zipfile.is_zipfile(ZIP_PATH):
        print("Using existing ZIP:", ZIP_PATH)
        return

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    response = context.request.get(
        TRANSCRIPT_URL,
        timeout=180000
    )

    if not response.ok:
        raise RuntimeError(
            f"Transcript download failed: HTTP {response.status}"
        )

    data = response.body()

    if not zipfile.is_zipfile(io.BytesIO(data)):
        preview = data[:250].decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            "The downloaded transcript response is not a valid ZIP. "
            f"Response preview: {preview}"
        )

    ZIP_PATH.write_bytes(data)

    print("Saved:", ZIP_PATH)


def extract_zip_safely():
    print("\n--- Extracting transcripts ---")

    base = TRANSCRIPTS_DIR.resolve()

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:

        for member in archive.infolist():
            destination = (
                TRANSCRIPTS_DIR / member.filename
            ).resolve()

            if destination != base and base not in destination.parents:
                raise RuntimeError(
                    f"Unsafe ZIP path detected: {member.filename}"
                )

        archive.extractall(TRANSCRIPTS_DIR)

    print("Transcript extraction complete.")


# ============================================================
# PARTICIPANT METADATA
# ============================================================

def participant_metadata(root):
    """
    Extract the target child's participant metadata.
    """
    participants = descendants(root, "participant")

    for participant in participants:
        participant_id = participant.attrib.get("id", "")
        role = text_of(participant, "role").lower()

        if "target" in role or participant_id.upper() == "CHI":
            return (
                participant_id,
                format_age(text_of(participant, "age")),
                text_of(participant, "sex"),
                (
                    text_of(participant, "language")
                    or text_of(participant, "languages")
                ),
            )

    if participants:
        participant = participants[0]

        return (
            participant.attrib.get("id", ""),
            format_age(text_of(participant, "age")),
            text_of(participant, "sex"),
            (
                text_of(participant, "language")
                or text_of(participant, "languages")
            ),
        )

    return "", "", "", ""


# ============================================================
# PARSE ONE XML FILE
# ============================================================

def parse_xml(xml_path):
    root = ET.parse(xml_path).getroot()

    # Include the participant folder in the session ID.
    # Example: PD01_060921
    session_id = f"{xml_path.parent.name}_{root.attrib.get('name', xml_path.stem)}"

    participant_id, age, sex, languages = (
        participant_metadata(root)
    )

    if not age:
        age = age_from_filename(xml_path.name)

    # Get the audio filename from mediaLocation.
    media_location = text_of(root, "mediaLocation")

    audio_name = Path(
        media_location or session_id
    ).name

    if not audio_name.lower().endswith(".wav"):
        audio_name += ".wav"

    if not languages:
        languages = text_of(root, "languages")

    def extract_ipa(utterance, tier_name):
        """Extract IPA symbols from the specified tier."""
        tier = next(
            (
                node for node in utterance.iter()
                if lname(node.tag) == tier_name
            ),
            None
        )

        if tier is None:
            return ""

        return "".join(
            node.text or ""
            for node in tier.iter()
            if lname(node.tag) in {"base", "suffix", "phlen"}
        )

    records = []

    # Each <r> element represents one utterance.
    for utterance in descendants(root, "r"):

        speaker = utterance.attrib.get(
            "speaker",
            participant_id
        )

        # Only process the target child.
        if participant_id and speaker != participant_id:
            continue

        # Get the segment belonging to this <r> element.
        segment = next(
            (
                node for node in utterance.iter()
                if lname(node.tag) == "segment"
            ),
            None
        )

        start_ms = ""
        end_ms = ""

        if segment is not None:
            try:
                start = float(segment.attrib["start"])
                end = float(segment.attrib["end"])

                unit = segment.attrib.get("unit", "ms").lower()

                # Convert to milliseconds only if necessary.
                if unit in {"s", "sec", "seconds"}:
                    start *= 1000
                    end *= 1000

                start_ms = round(start)
                end_ms = round(end)

            except (KeyError, TypeError, ValueError):
                pass

        source_audio_name = f"{session_id}.wav"
        source_audio_Path = AUDIO_DIR / source_audio_name

        records.append({
            "session_id": session_id,
            "utterance_id": utterance.attrib.get(
                "id",
                f"u{len(records)}"
            ),
            "age": age,
            "sex": sex,

            "word": tier_word(
                utterance,
                "orthography"
            ),

            "target_ipa": extract_ipa(
                utterance,
                "ipaTarget"
            ),

            "actual_ipa": extract_ipa(
                utterance,
                "ipaActual"
            ),

            "start_ms": start_ms,
            "end_ms": end_ms,

            "source_xml": str(xml_path.relative_to(BASE_DIR)),
            "source_audio": str(source_audio_Path.relative_to(BASE_DIR)),
            "clip_file": "",
        })

    return session_id, audio_name, records


# ============================================================
# AUDIO DOWNLOAD
# ============================================================

def valid_wav(path):
    """Check whether a WAV file can be opened."""
    try:
        with wave.open(str(path), "rb"):
            return True
    except (wave.Error, EOFError, OSError):
        return False



def download_audio(context, filename, participant_folder, save_name=None):
    """
    Stream-download the matching WAV file.

    Try the flat CHAT directory first, followed by the
    participant's PD## subdirectory.

    Uses authenticated Playwright cookies with requests
    to stream large audio files directly to disk.
    """

    filename = Path(filename).name
    destination = AUDIO_DIR / (save_name or filename)

    if destination.exists():
        if valid_wav(destination):
            return destination

        print("Removing invalid existing audio:", destination.name)
        destination.unlink()

    # Transfer authentication from Playwright to requests
    session = requests.Session()

    for cookie in context.cookies(AUDIO_BASE_URL):
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/")
        )

    relative_paths = [
        filename,
        f"{participant_folder}/{filename}",
    ]

    attempted = set()

    for relative_path in relative_paths:

        if relative_path in attempted:
            continue

        attempted.add(relative_path)

        url = (
            f"{AUDIO_BASE_URL}/"
            f"{quote(relative_path, safe='/')}?f=save"
        )

        temp_path = destination.with_name(
            destination.name + ".part"
        )

        try:
            with session.get(
                url,
                stream=True,
                timeout=(30, 300)
            ) as response:

                if not response.ok:
                    continue

                bytes_written = 0

                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024
                    ):
                        if chunk:
                            f.write(chunk)
                            bytes_written += len(chunk)

                # Validate WAV header
                with open(temp_path, "rb") as f:
                    header = f.read(16)

                if not (
                    header.startswith(b"RIFF")
                    and b"WAVE" in header
                ):
                    temp_path.unlink(missing_ok=True)
                    continue

                # Validate complete WAV file
                if valid_wav(temp_path):
                    temp_path.replace(destination)

                    print(
                        f"Downloaded: {destination.name} "
                        f"({bytes_written / (1024 * 1024):.1f} MB)"
                    )

                    session.close()
                    return destination

                print("Invalid or incomplete WAV:", filename)
                temp_path.unlink(missing_ok=True)

        except Exception as error:
            print(
                f"Audio download error for {filename}: {error}"
            )

            temp_path.unlink(missing_ok=True)

    session.close()

    print("Could not download audio:", filename)
    return None



# ============================================================
# CROP AUDIO CLIPS
# ============================================================

def crop_audio(audio_path, start_ms, end_ms, output_path):
    try:
        with wave.open(str(audio_path), "rb") as source:
            params = source.getparams()
            rate = source.getframerate()

            first = max(
                0,
                int(float(start_ms) * rate / 1000)
            )

            last = min(
                source.getnframes(),
                int(float(end_ms) * rate / 1000)
            )

            if last <= first:
                return False

            source.setpos(first)
            frames = source.readframes(last - first)

        with wave.open(str(output_path), "wb") as output:
            output.setparams(params)
            output.writeframes(frames)

        return True

    except (
        wave.Error,
        EOFError,
        OSError,
        ValueError
    ) as error:
        print(
            f"Could not crop {audio_path.name}: {error}"
        )
        return False

# CHECK ACTUAL XML FILE FOR CHILD AGE TO AVOID INVALID RECORDS
def is_valid_xml_age(root):
    """
    Check whether the participant's XML age is between
    4 and 6 years, inclusive.

    Returns False if the age is missing or invalid.
    """

    age_element = next(
        (
            element
            for element in root.iter()
            if element.tag.split("}")[-1] == "age"
        ),
        None
    )

    if age_element is None or not age_element.text:
        return False

    age_text = age_element.text.strip()

    match = re.match(r"^P(\d+)Y", age_text)

    if not match:
        return False

    age_years = int(match.group(1))

    return 4 <= age_years <= 6


# ============================================================
# BUILD DATASET
# ============================================================

def build_dataset(context):
    print("\n--- Building Cummings dataset ---")

    # Find XML files recursively.
    all_xml_files = sorted(
        TRANSCRIPTS_DIR.rglob("*.xml")
    )

    # Only retain age-coded XML files in the target range.
    xml_files = [
        path for path in all_xml_files
        if is_target_age(path.name)
    ]

    # Restrict discovery to the expected PD## directories.
    xml_files = [
        path for path in xml_files
        if re.fullmatch(r"PD\d+", path.parent.name)
    ]

    if not xml_files:
        raise FileNotFoundError(
            "No eligible Cummings XML files found. "
            "Expected files such as "
            "Cummings/Phon/PD##/060921.xml."
        )

    xml_files.sort(
        key=lambda path: (
            int(path.stem),
            path.parent.name
        )
    )

    print("Total XML files found:", len(all_xml_files))
    print("Eligible age 4-6 XML files:", len(xml_files))

    # Count unique participant age codes.
    age_codes = sorted({
        path.stem for path in xml_files
    })

    print("Unique age-coded filenames:", len(age_codes))

    all_records = []
    downloaded = 0
    failed = 0

    for index, xml_path in enumerate(xml_files, start=1):
        participant_folder = xml_path.parent.name

        print(
            f"\n[{index}/{len(xml_files)}] "
            f"Processing {participant_folder}/{xml_path.name}"
        )

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            if not is_valid_xml_age(root):
                print(f"Skipping {xml_path.name}: participant outside age range 4-6")
                continue
            session_id, audio_name, records = parse_xml(xml_path)

        except (ET.ParseError, OSError) as error:
            print("Skipping XML:", xml_path.name, error)
            continue



        audio_path = download_audio(
            context,
            audio_name,
            participant_folder,
            save_name=f"{session_id}.wav"
        )

        if audio_path is not None:
            downloaded += 1
        else:
            failed += 1

        for record in records:
            if (
                audio_path is not None
                and record["start_ms"] != ""
                and record["end_ms"] != ""
            ):
                # utterance_id already includes the session prefix.
                clip_name = f'{session_id}_{record["utterance_id"]}.wav'

                clip_path = CLIPS_DIR / clip_name

                if clip_path.exists() and valid_wav(clip_path):
                    record["clip_file"] = str(clip_path.relative_to(BASE_DIR))

                elif crop_audio(
                    audio_path,
                    record["start_ms"],
                    record["end_ms"],
                    clip_path
                ):
                    record["clip_file"] = str(clip_path.relative_to(BASE_DIR))

            all_records.append(record)

        print(
            f"Added {len(records)} utterances "
            f"from {session_id}."
        )

    # Write CSV.
    with CSV_PATH.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=CSV_COLUMNS
        )

        writer.writeheader()
        writer.writerows(all_records)

    print("\n--- Cummings extraction summary ---")
    print("Eligible XML files:", len(xml_files))
    print("Unique age-coded filenames:", len(age_codes))
    print("Audio downloaded or already present:", downloaded)
    print("Audio failures:", failed)
    print("Total utterances:", len(all_records))
    print(
        "Clips created/reused:",
        sum(bool(record["clip_file"]) for record in all_records)
    )
    print("CSV:", CSV_PATH)


# ============================================================
# MAIN
# ============================================================

def main():
    setup_directories()

    if not AUTH_FILE.exists():
        authenticate()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            storage_state=str(AUTH_FILE)
        )

        try:
            download_transcript_zip(context)
            extract_zip_safely()
            build_dataset(context)

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()