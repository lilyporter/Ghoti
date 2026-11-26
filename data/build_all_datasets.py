
import pandas as pd
import argparse
import subprocess
import sys
from pathlib import Path

from auth.talkbank_auth import authenticate, deauthenticate



CORPORA = {
    "Paidologos": {
        "folder": "talkbank_paidologos",
        "script": "build_talkbank_paidologos_dataset.py",
        "transcript_complete": False,
    },
    "Penney": {
        "folder": "talkbank_penney",
        "script": "build_talkbank_penney_dataset.py",
        "transcript_complete": True,
    },
    "Preston": {
        "folder": "talkbank_preston",
        "script": "build_talkbank_preston_dataset.py",
        "transcript_complete": True,
    },
    "Cummings": {
        "folder": "talkbank_cummings",
        "script": "build_talkbank_cummings_dataset.py",
        "transcript_complete": True,
    },
}

PATH_COLUMNS = [
    "clip_file",
    "media_location",
    "source_audio",
    "source_xml",
]


def run_dataset(name, function):
    """Run one dataset builder and return its result or exception."""
    print(f"\n========== Starting {name} ==========")
    function()
    print(f"========== Finished {name} ==========")
    return name


def compile_datasets(selected_corpora):
    datasets = []

    for source_name, config in selected_corpora.items():
        folder = config["folder"]
        csv_path = Path(folder) / "dataset.csv"

        df = pd.read_csv(csv_path)

        df["data_source"] = source_name

        for column in PATH_COLUMNS:
            if column in df.columns:
                df[column] = df[column].apply(
                    lambda x: (
                        f"{folder}/{str(x).replace(chr(92), '/').lstrip('/')}"
                        if pd.notna(x) and str(x).strip()
                        else x
                    )
                )

        datasets.append(df)

    combined = pd.concat(datasets, ignore_index=True)

    output = (
        "combined_dataset_all_transcript.csv"
        if len(selected_corpora) < len(CORPORA)
        else "combined_dataset.csv"
    )

    combined.to_csv(output, index=False)

    print(f"\nCombined {len(combined)} utterances.")
    print(f"Saved to {output}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-a",
        "--all-transcript",
        action="store_true",
        help="Only build datasets with complete transcript information."
    )

    args = parser.parse_args()

    selected_corpora = {
        name: config
        for name, config in CORPORA.items()
        if not args.all_transcript or config["transcript_complete"]
    }

    # Authenticate talkbank at start
    try:
        authenticate()

        # Run selected build scripts
        for name, config in selected_corpora.items():
            print(f"\nBuilding {name}...")

            subprocess.run(
                [sys.executable, config["script"]],
                check=True
            )

        # Compile only the selected datasets
        compile_datasets(selected_corpora)
    finally:
        # delete the authenticated json once the script is done
        deauthenticate()



if __name__ == "__main__":
    main()
