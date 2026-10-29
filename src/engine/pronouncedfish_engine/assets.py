"""Explicit model acquisition, separate from offline inference."""

import hashlib
import json
from pathlib import Path
from typing import Union

MODEL_ID = "drivendata/pasketti-phonetic"
MODEL_REVISION = "675dfe392a2af7050f1374eeab4458cb1f003b3e"
WEIGHTS_SHA256 = "5b3eb5a1b7e03e25dc816ae891f18eeffa239d715a5868010b07973a077b5134"
MODEL_VERSION = f"{MODEL_ID}@{MODEL_REVISION}"
MODEL_FILES = (
    "config.json",
    "model.safetensors",
    "preprocessor_config.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "vocab.json",
    "README.md",
)
MANIFEST_NAME = "pronouncedfish-model.json"


def _weights_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_model(model_dir: Union[str, Path]) -> Path:
    """Verify a complete pinned snapshot without consulting the network."""
    directory = Path(model_dir).expanduser().resolve()
    required = (*MODEL_FILES, MANIFEST_NAME)
    if not directory.is_dir() or any(not (directory / f).is_file() for f in required):
        raise FileNotFoundError(
            "Model snapshot is incomplete. Run pronouncedfish-engine download-model "
            "--model-dir <directory> first."
        )
    manifest = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
    if manifest.get("model_version") != MODEL_VERSION:
        raise ValueError("Model manifest does not match the supported pinned revision.")
    for filename in MODEL_FILES:
        actual = _weights_digest(directory / filename)
        expected = manifest.get("sha256", {}).get(filename)
        if actual != expected or (filename == "model.safetensors" and actual != WEIGHTS_SHA256):
            raise ValueError(f"Model asset checksum mismatch: {filename}")
    return directory


def download_pasketti(model_dir: Union[str, Path]) -> Path:
    """Download public static assets only; no audio is accepted or transmitted."""
    from huggingface_hub import snapshot_download

    directory = Path(model_dir).expanduser().resolve()
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=str(directory),
        allow_patterns=list(MODEL_FILES),
        token=False,
    )
    hashes = {name: _weights_digest(directory / name) for name in MODEL_FILES}
    if hashes["model.safetensors"] != WEIGHTS_SHA256:
        raise ValueError("Downloaded weights do not match the pinned SHA-256 checksum.")
    (directory / MANIFEST_NAME).write_text(
        json.dumps({"model_version": MODEL_VERSION, "sha256": hashes}, indent=2) + "\n",
        encoding="utf-8",
    )
    return directory
