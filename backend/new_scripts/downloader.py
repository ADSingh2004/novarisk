from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

LOGGER = logging.getLogger(__name__)
DEFAULT_CHUNK_SIZE = 1024 * 1024


def download_file(url: str, destination: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Path:
    """Download a file via streaming HTTP with resume support."""
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".part")

    headers = {}
    existing = tmp_path.stat().st_size if tmp_path.exists() else 0
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    LOGGER.info("Downloading %s -> %s", url, dest)
    with requests.get(url, stream=True, headers=headers, timeout=60) as resp:
        resp.raise_for_status()
        mode = "ab" if existing else "wb"
        with tmp_path.open(mode) as fh:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    fh.write(chunk)

    tmp_path.replace(dest)
    return dest


def maybe_download(url: Optional[str], destination: str) -> Path | None:
    if not url:
        return None
    dest = Path(destination)
    if dest.exists():
        LOGGER.info("Reusing existing file %s", dest)
        return dest
    try:
        return download_file(url, destination)
    except Exception as err:
        LOGGER.warning("Failed to download %s: %s", url, err)
        return None
