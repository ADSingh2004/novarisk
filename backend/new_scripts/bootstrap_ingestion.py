from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ingestion.era5_ingestion import prepare_era5_dataset
from ingestion.sentinel1_search import search_sentinel1_scenes
from ingestion.sentinel_search import search_sentinel2_scenes
from ingestion.targets import TargetSite, load_target_sites

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _time_range(days_back: int, days_span: int) -> tuple[str, str]:
    end = datetime.utcnow()
    start = end - timedelta(days=days_back)
    window_start = end - timedelta(days=days_span)
    return start.strftime("%Y-%m-%d"), window_start.strftime("%Y-%m-%d")


def build_ingestion_plan(
    sites: List[TargetSite],
    recent_days: int = 60,
    search_span_days: int = 365,
    max_cloud_cover: int = 30,
) -> List[Dict[str, Any]]:
    start_date, baseline_date = _time_range(recent_days, search_span_days)
    plan: List[Dict[str, Any]] = []

    for site in sites:
        site.ensure_workspace()
        LOGGER.info("Planning ingestion for %s (%s)", site.site_id, site.name)

        s2_items = search_sentinel2_scenes(
            lat=site.lat,
            lon=site.lon,
            start_date=baseline_date,
            end_date=start_date,
            max_cloud_cover=max_cloud_cover,
        )
        s1_items = search_sentinel1_scenes(
            lat=site.lat,
            lon=site.lon,
            start_date=baseline_date,
            end_date=start_date,
        )
        era5_asset = site.assets.get("era5_netcdf") or f"data/dummy/era5/{site.site_id}_era5_land_t2m.nc"
        era5_path = prepare_era5_dataset(era5_asset)

        plan.append(
            {
                "site_id": site.site_id,
                "facility_id": site.facility_id,
                "name": site.name,
                "aoi_type": site.aoi_type,
                "workspace": f"data/working/{site.site_id}",
                "era5_path": era5_path,
                "sentinel2_candidates": s2_items[:5],
                "sentinel1_candidates": s1_items[:5],
            }
        )

    return plan


def bootstrap_ingestion(config_path: str = "data/reference/target_sites.json") -> List[Dict[str, Any]]:
    sites = load_target_sites(config_path)
    plan = build_ingestion_plan(sites)
    LOGGER.info("Prepared ingestion plan for %d sites", len(plan))
    return plan


if __name__ == "__main__":
    ingestion_plan = bootstrap_ingestion()
    for site_plan in ingestion_plan:
        LOGGER.info("Site %s: %d S2 scenes, %d S1 scenes, ERA5=%s",
                    site_plan["site_id"],
                    len(site_plan["sentinel2_candidates"]),
                    len(site_plan["sentinel1_candidates"]),
                    site_plan["era5_path"])
