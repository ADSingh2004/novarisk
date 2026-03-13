from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import rasterio

from ingestion.ancillary import ingest_jrc_water, ingest_worldcover
from ingestion.bootstrap_ingestion import build_ingestion_plan
from ingestion.downloader import maybe_download
from ingestion.generate_dummy_inputs import generate_dummy_optical_band, generate_dummy_sar_band
from ingestion.targets import TargetSite, load_target_sites

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SENTINEL2_BANDS = {
    "red": "B04",
    "nir": "B08",
    "green": "B03",
    "swir": "B11",
}
SENTINEL1_POLARIZATIONS = ("vv", "vh")


def _seed_for(site: TargetSite, stage: str, suffix: str) -> int:
    return abs(hash(f"{site.site_id}-{stage}-{suffix}")) % (2**32)


def _stack_two_band_raster(first_path: str, second_path: str, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(first_path) as first_src, rasterio.open(second_path) as second_src:
        first = first_src.read(1).astype("float32")
        second = second_src.read(1).astype("float32")
        if first.shape != second.shape:
            raise ValueError("Input rasters must share identical dimensions for stacking.")
        profile = first_src.profile.copy()
        profile.update(count=2, dtype="float32")
        with rasterio.open(destination, "w", **profile) as dst:
            dst.write(first, 1)
            dst.write(second, 2)
    return str(destination)


def _build_sentinel2_pair(
    site: TargetSite,
    bundle: Dict[str, Any] | None,
    stage: str,
    first_alias: str,
    second_alias: str,
    label: str,
) -> str | None:
    if not bundle:
        return None
    bands = bundle.get("bands", {})
    first_path = bands.get(first_alias)
    second_path = bands.get(second_alias)
    if not first_path or not second_path:
        return None

    composite_dir = site.workspace / "sentinel2" / "composites"
    composite_path = composite_dir / f"{stage}_{label}.tif"
    return _stack_two_band_raster(first_path, second_path, composite_path)


def _build_sentinel1_stack(site: TargetSite, bundle: Dict[str, Any] | None, stage: str, label: str = "vv_vh") -> str | None:
    if not bundle:
        return None
    polarizations = bundle.get("polarizations", {})
    vv_path = polarizations.get("vv")
    vh_path = polarizations.get("vh")
    if not vv_path or not vh_path:
        return None

    stack_dir = site.workspace / "sentinel1" / "stacks"
    stack_path = stack_dir / f"{stage}_{label}.tif"
    return _stack_two_band_raster(vv_path, vh_path, stack_path)


def _select_item_pair(items: List[Dict[str, Any]]) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    if not items:
        return None, None
    after = items[0]
    before = items[-1]
    return before, after


def _group_items_by_month(items: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for item in items:
        date_raw = str(item.get("date") or "")
        month_key = date_raw[:7] if len(date_raw) >= 7 else "unknown"
        grouped.setdefault(month_key, []).append(str(item.get("id", "")))
    return grouped


def _download_sentinel2_bundle(site: TargetSite, item: Dict[str, Any], stage: str) -> Dict[str, Any]:
    if not item:
        return {}
    workspace = site.workspace / "sentinel2" / stage
    workspace.mkdir(parents=True, exist_ok=True)
    band_paths: Dict[str, str] = {}
    for alias, band_name in SENTINEL2_BANDS.items():
        dest = workspace / f"{item['id']}_{band_name}.tif"
        href = item["assets"].get(band_name)
        path = maybe_download(href, str(dest)) if href else None
        if path:
            band_paths[alias] = str(path)
        else:
            LOGGER.warning(
                "Falling back to dummy Sentinel-2 %s band for %s (%s)",
                band_name,
                site.site_id,
                stage,
            )
            seed = _seed_for(site, stage, band_name)
            dummy_path = generate_dummy_optical_band(str(dest), seed=seed)
            band_paths[alias] = dummy_path
    return {
        "id": item["id"],
        "date": item.get("date"),
        "bands": band_paths,
    }


def _download_sentinel1_bundle(site: TargetSite, item: Dict[str, Any], stage: str) -> Dict[str, Any]:
    if not item:
        return {}
    workspace = site.workspace / "sentinel1" / stage
    workspace.mkdir(parents=True, exist_ok=True)
    pol_paths: Dict[str, str] = {}
    for pol in SENTINEL1_POLARIZATIONS:
        dest = workspace / f"{item['id']}_{pol}.tif"
        href = item["assets"].get(pol)
        path = maybe_download(href, str(dest)) if href else None
        if path:
            pol_paths[pol] = str(path)
        else:
            LOGGER.warning(
                "Falling back to dummy Sentinel-1 %s polarization for %s (%s)",
                pol,
                site.site_id,
                stage,
            )
            seed = _seed_for(site, stage, pol)
            dummy_path = generate_dummy_sar_band(str(dest), seed=seed)
            pol_paths[pol] = dummy_path
    return {
        "id": item["id"],
        "date": item.get("date"),
        "polarizations": pol_paths,
    }


def ingest_site(site: TargetSite, plan_entry: Dict[str, Any]) -> Dict[str, Any]:
    site.ensure_workspace()
    before_s2, after_s2 = _select_item_pair(plan_entry.get("sentinel2_candidates", []))
    before_s1, after_s1 = _select_item_pair(plan_entry.get("sentinel1_candidates", []))

    LOGGER.info("Ingesting EO assets for %s", site.site_id)

    sentinel2 = {
        "before": _download_sentinel2_bundle(site, before_s2, "before") if before_s2 else None,
        "after": _download_sentinel2_bundle(site, after_s2, "after") if after_s2 else None,
    }
    sentinel1 = {
        "before": _download_sentinel1_bundle(site, before_s1, "before") if before_s1 else None,
        "after": _download_sentinel1_bundle(site, after_s1, "after") if after_s1 else None,
    }

    sentinel2_composites: Dict[str, Dict[str, str | None]] = {
        "red_nir": {},
        "green_swir": {},
    }
    sentinel1_stacks: Dict[str, Dict[str, str | None]] = {
        "vv_vh": {},
    }

    for stage in ("before", "after"):
        sentinel2_bundle = sentinel2.get(stage)
        sentinel1_bundle = sentinel1.get(stage)

        sentinel2_composites["red_nir"][stage] = _build_sentinel2_pair(
            site,
            sentinel2_bundle,
            stage,
            "red",
            "nir",
            "red_nir",
        ) if sentinel2_bundle else None

        sentinel2_composites["green_swir"][stage] = _build_sentinel2_pair(
            site,
            sentinel2_bundle,
            stage,
            "green",
            "swir",
            "green_swir",
        ) if sentinel2_bundle else None

        sentinel1_stacks["vv_vh"][stage] = _build_sentinel1_stack(
            site,
            sentinel1_bundle,
            stage,
        ) if sentinel1_bundle else None

    worldcover_path = ingest_worldcover(site)
    jrc_water_path = ingest_jrc_water(site)

    manifest = {
        "site_id": site.site_id,
        "facility_id": site.facility_id,
        "name": site.name,
        "workspace": str(site.workspace),
        "sentinel2": sentinel2,
        "sentinel2_composites": sentinel2_composites,
        "sentinel1": sentinel1,
        "sentinel1_stacks": sentinel1_stacks,
        "era5": plan_entry.get("era5_path"),
        "worldcover": worldcover_path,
        "jrc_water": jrc_water_path,
        "monthly_products": {
            "sentinel2_scene_ids": _group_items_by_month(plan_entry.get("sentinel2_candidates", [])),
            "sentinel1_scene_ids": _group_items_by_month(plan_entry.get("sentinel1_candidates", [])),
            "era5": {
                "dataset_path": plan_entry.get("era5_path"),
                "cadence": "hourly_or_daily",
            },
        },
    }

    manifest_path = site.workspace / "ingestion_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def ingest_all_sites(config_path: str = "data/reference/target_sites.json") -> List[Dict[str, Any]]:
    sites = load_target_sites(config_path)
    plan_entries = build_ingestion_plan(sites)
    plan_by_site = {entry["site_id"]: entry for entry in plan_entries}

    manifests: List[Dict[str, Any]] = []
    for site in sites:
        entry = plan_by_site.get(site.site_id)
        if not entry:
            LOGGER.warning("No plan entry for %s", site.site_id)
            continue
        manifests.append(ingest_site(site, entry))

    aggregated_path = Path("data/working/ingestion_manifest.json")
    aggregated_path.parent.mkdir(parents=True, exist_ok=True)
    aggregated_path.write_text(json.dumps(manifests, indent=2), encoding="utf-8")
    LOGGER.info("Wrote aggregated ingestion manifest to %s", aggregated_path)
    return manifests


if __name__ == "__main__":
    ingest_all_sites()
