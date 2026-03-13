from __future__ import annotations

import logging
import math
from pathlib import Path

from ingestion.generate_dummy_inputs import (
    generate_dummy_jrc_water_occurrence,
    generate_dummy_worldcover_raster,
)
from ingestion.raster_ops import clip_cog_to_bbox
from ingestion.targets import TargetSite

LOGGER = logging.getLogger(__name__)

WORLD_COVER_COG = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_Map_COG.tif"
JRC_OCCURRENCE_BASE = "https://storage.googleapis.com/global-surface-water/tiles2021/occurrence"


def _format_lon_tile(lon: float) -> str:
    tile = int(math.floor(lon / 10.0) * 10)
    direction = "E" if tile >= 0 else "W"
    return f"{abs(tile):03d}{direction}"


def _format_lat_tile(lat: float) -> str:
    tile = int(math.floor(lat / 10.0) * 10)
    direction = "N" if tile >= 0 else "S"
    return f"{abs(tile):02d}{direction}"


def ingest_worldcover(site: TargetSite, destination: str | None = None, scale_factor: float = 1.5) -> str:
    dest = Path(destination or site.workspace / "worldcover_2021.tif")
    bbox = site.bounding_box(scale_factor)
    try:
        clip_cog_to_bbox(WORLD_COVER_COG, bbox, str(dest))
        LOGGER.info("WorldCover clipped for %s -> %s", site.site_id, dest)
        return str(dest)
    except Exception as err:
        LOGGER.warning("WorldCover fetch failed for %s: %s. Falling back to dummy.", site.site_id, err)
        return generate_dummy_worldcover_raster(str(dest))


def ingest_jrc_water(site: TargetSite, destination: str | None = None, scale_factor: float = 2.0) -> str:
    dest = Path(destination or site.workspace / "jrc_water_occurrence.tif")
    lon_component = _format_lon_tile(site.lon)
    lat_component = _format_lat_tile(site.lat)
    tile_name = f"occurrence_{lon_component}_{lat_component}.tif"
    url = f"{JRC_OCCURRENCE_BASE}/{tile_name}"
    bbox = site.bounding_box(scale_factor)
    try:
        clip_cog_to_bbox(url, bbox, str(dest))
        LOGGER.info("JRC water clipped for %s -> %s", site.site_id, dest)
        return str(dest)
    except Exception as err:
        LOGGER.warning("JRC water fetch failed for %s (%s): %s. Falling back to dummy.", site.site_id, url, err)
        return generate_dummy_jrc_water_occurrence(str(dest))
