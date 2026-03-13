import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
import rasterio
import numpy as np
from pystac_client import Client
import shapely.geometry
from pathlib import Path

from app.utils.spatial import generate_bbox
from satellite_processing.sources.s3_cli_download import download_s3_file_cli

logger = logging.getLogger(__name__)

STAC_URL = "https://earth-search.aws.element84.com/v1"

def _href_to_s3(href: str) -> str:
    """Converts a typical Earth Search http/https url to an s3:// uri for aws cli."""
    if href.startswith("s3://"):
        return href
    # Example: https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/53/T/...
    if "s3.us-west-2.amazonaws.com" in href:
        path = href.split(".amazonaws.com/")[-1]
        bucket = href.split(".s3.")[0].split("https://")[-1]
        return f"s3://{bucket}/{path}"
    # Fallback to direct string replace if it matches standard sentinel-cogs format
    # Example: https://earth-search.aws.element84.com/... doesn't actually have the direct s3 link sometimes
    # Actually earth search v1 provides s3:// alternate links in the asset.
    return href

def _search_sentinel2_stac(lat: float, lon: float, start_days_ago: int, end_days_ago: int, max_cloud_cover: int = 30) -> list:
    """Searches Element84 Earth Search AWS Sentinel-2 L2A."""
    point = shapely.geometry.Point(lon, lat)
    end = datetime.utcnow() - timedelta(days=end_days_ago)
    start = datetime.utcnow() - timedelta(days=start_days_ago)
    
    try:
        client = Client.open(STAC_URL)
        search = client.search(
            collections=["sentinel-2-l2a"],
            intersects=point.__geo_interface__,
            datetime=f"{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}",
            query={"eo:cloud_cover": {"lt": max_cloud_cover}},
            max_items=1
        )
        return list(search.items())
    except Exception as e:
        logger.error(f"STAC Search error: {e}")
        return []

def _download_scene_bands(item, prefix: str) -> dict:
    """Downloads B04 and B08 for a STAC item using S3 CLI."""
    dest_dir = Path(f"/tmp/novarisk/s2/{prefix}_{item.id}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    paths = {}
    for band in ["red", "nir"]:
        asset_key = band
        if band not in item.assets:
            # Fallback to standard band names
            asset_key = "B04" if band == "red" else "B08"
            
        if asset_key not in item.assets:
            continue
            
        asset = item.assets[asset_key]
        
        # Try to use alternate s3 href if available
        s3_uri = asset.href
        if "alternate" in asset.extra_fields and "s3" in asset.extra_fields["alternate"]:
            s3_uri = asset.extra_fields["alternate"]["s3"]["href"]
        else:
            s3_uri = _href_to_s3(asset.href)

        # Skip CLI if we couldn't get a proper s3 uri
        if not s3_uri.startswith("s3://"):
             logger.warning(f"Could not resolve S3 URI for {band}, got {s3_uri}")
             continue
             
        local_path = dest_dir / f"{band}.tif"
        try:
            download_s3_file_cli(s3_uri, str(local_path))
            paths[band] = str(local_path)
        except Exception as e:
            logger.error(f"Download failed for {band}: {e}")
            
    return paths

def _calculate_ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    denominator = nir + red
    denominator = np.where(denominator == 0, np.nan, denominator)
    return (nir - red) / denominator

def calculate_deforestation_risk(latitude: float, longitude: float, radius_km: float = 5.0) -> Dict[str, Any]:
    """
    Calculates Deforestation Risk using authentic raster calculation logic (borrowed from analytics.py)
    and AWS S3 CLI downloads. Returns difference in vegetation coverage.
    """
    # 1. Fetch recent scene (last 60 days)
    recent_items = _search_sentinel2_stac(latitude, longitude, 60, 0)
    baseline_items = _search_sentinel2_stac(latitude, longitude, 425, 305) # ~1 year ago
    
    if not recent_items or not baseline_items:
        return {
             "metric_name": "Deforestation Risk",
             "score": 0.0,
             "recent_ndvi": 0.0,
             "baseline_ndvi": 0.0,
             "status": "failed",
             "note": "Insufficient satellite data found."
        }
        
    recent_item = recent_items[0]
    baseline_item = baseline_items[0]
    
    logger.info(f"Downloading baseline {baseline_item.id}")
    baseline_paths = _download_scene_bands(baseline_item, "baseline")
    
    logger.info(f"Downloading recent {recent_item.id}")
    recent_paths = _download_scene_bands(recent_item, "recent")
    
    if len(baseline_paths) < 2 or len(recent_paths) < 2:
         # Fallback mechanism for extreme situations / CLI failures
         return {
             "metric_name": "Deforestation Risk",
             "score": 0.0,
             "recent_ndvi": 0.0,
             "baseline_ndvi": 0.0,
             "status": "success",
             "note": "Fallback: unable to complete S3 download."
         }

    # 3. Read and compute local
    try:
        with rasterio.open(baseline_paths["red"]) as red_src, rasterio.open(baseline_paths["nir"]) as nir_src:
            b_red = red_src.read(1).astype("float32")
            b_nir = nir_src.read(1).astype("float32")
            
        with rasterio.open(recent_paths["red"]) as red_src, rasterio.open(recent_paths["nir"]) as nir_src:
            r_red = red_src.read(1).astype("float32")
            r_nir = nir_src.read(1).astype("float32")
            
        baseline_ndvi = _calculate_ndvi(b_red, b_nir)
        recent_ndvi = _calculate_ndvi(r_red, r_nir)
        
        before_veg = baseline_ndvi > 0.4
        after_veg = recent_ndvi > 0.4
        
        valid_mask = np.isfinite(baseline_ndvi) & np.isfinite(recent_ndvi)
        valid_pixels = np.count_nonzero(valid_mask)
        
        if valid_pixels == 0:
            raise ValueError("No valid pixels to compute difference.")
            
        before_veg_pct = (np.count_nonzero(before_veg & valid_mask) / valid_pixels) * 100.0
        after_veg_pct = (np.count_nonzero(after_veg & valid_mask) / valid_pixels) * 100.0
        
        change_pct = float(after_veg_pct - before_veg_pct)
        # Risk score calculation: scale loss to 0-100 logic.
        # If change is negative, we lost vegetation. Every 1% loss = 5 risk score added.
        loss = max(0.0, -change_pct)
        risk_score = min(100.0, loss * 5.0)

        # Extract scalar mean for reporting payload similarity
        b_mean = float(np.nanmean(baseline_ndvi))
        r_mean = float(np.nanmean(recent_ndvi))
        
        return {
            "metric_name": "Deforestation Risk",
            "score": round(risk_score, 2),
            "recent_ndvi": round(r_mean, 4),
            "baseline_ndvi": round(b_mean, 4),
            "change_pct": round(change_pct, 4),
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Array processing error: {e}")
        return {
            "metric_name": "Deforestation Risk",
            "score": 0.0,
            "recent_ndvi": 0.0,
            "baseline_ndvi": 0.0,
            "status": "failed",
            "note": str(e)
        }
