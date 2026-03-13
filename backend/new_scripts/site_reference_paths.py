from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_REFERENCE_CONFIG_PATH = "data/reference/target_sites.json"


def _load_reference_config() -> dict[str, Any]:
    config_path = Path(os.getenv("SITE_REFERENCE_CONFIG_PATH", DEFAULT_REFERENCE_CONFIG_PATH))
    if not config_path.exists():
        return {"sites": []}

    with config_path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def resolve_site_reference_paths(
    site_id: str | None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any] | None:
    config = _load_reference_config()
    sites = config.get("sites", [])

    if site_id:
        for site in sites:
            if site.get("site_id") == site_id:
                return site

    if lat is not None and lon is not None:
        for site in sites:
            site_lat = site.get("lat")
            site_lon = site.get("lon")
            if site_lat is None or site_lon is None:
                continue
            if abs(float(site_lat) - lat) < 1e-6 and abs(float(site_lon) - lon) < 1e-6:
                return site

    return None


def assert_reference_paths_exist(site_reference: dict[str, Any]) -> None:
    required_keys = [
        "after_tif",
        "water_after_optical_tif",
        "water_after_sar_tif",
        "worldcover_tif",
        "jrc_water_tif",
    ]
    missing = [key for key in required_keys if not site_reference.get(key)]
    if missing:
        raise ValueError(f"Missing required reference path keys: {missing}")

    non_existing = [key for key in required_keys if not Path(str(site_reference[key])).exists()]
    if non_existing:
        raise FileNotFoundError(
            f"Configured reference files not found for keys: {non_existing}. "
            f"Check SITE_REFERENCE_CONFIG_PATH and file paths."
        )
