import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import rasterio
import numpy as np
from pystac_client import Client
import shapely.geometry
from pathlib import Path

from satellite_processing.sources.s3_cli_download import download_s3_file_cli

logger = logging.getLogger(__name__)

STAC_URL = "https://earth-search.aws.element84.com/v1"

def _search_sentinel1_stac(lat: float, lon: float, start_days_ago: int, end_days_ago: int) -> list:
    """Searches Element84 Earth Search AWS Sentinel-1 GRD."""
    point = shapely.geometry.Point(lon, lat)
    end = datetime.utcnow() - timedelta(days=end_days_ago)
    start = datetime.utcnow() - timedelta(days=start_days_ago)
    
    try:
        client = Client.open(STAC_URL)
        search = client.search(
            collections=["sentinel-1-grd"],
            intersects=point.__geo_interface__,
            datetime=f"{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}",
            query={"sar:instrument_mode": {"eq": "IW"}},
            max_items=1
        )
        return list(search.items())
    except Exception as e:
        logger.error(f"S1 STAC Search error: {e}")
        return []

def _download_s1_bands(item, prefix: str) -> dict:
    """Downloads VV and VH for a STAC item using S3 CLI."""
    dest_dir = Path(f"/tmp/novarisk/s1/{prefix}_{item.id}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    paths = {}
    for band in ["vv", "vh"]:
        if band not in item.assets:
            continue
            
        asset = item.assets[band]
        s3_uri = asset.href
        
        # Earth search native
        if "alternate" in asset.extra_fields and "s3" in asset.extra_fields["alternate"]:
            s3_uri = asset.extra_fields["alternate"]["s3"]["href"]
            
        if not s3_uri.startswith("s3://"):
             # Fast conversion for element84 s3 assets
             if "s3.us-west-2.amazonaws.com" in s3_uri:
                 s3_uri = s3_uri.replace("https://sentinel-s1-rtc-indigo.s3.us-west-2.amazonaws.com/", "s3://sentinel-s1-rtc-indigo/")

        local_path = dest_dir / f"{band}.tif"
        try:
            download_s3_file_cli(s3_uri, str(local_path))
            paths[band] = str(local_path)
        except Exception as e:
            logger.error(f"Download failed for S1 {band}: {e}")
            
    return paths

def verify_deforestation_sar(latitude: float, longitude: float) -> str:
    """
    Downloads Sentinel-1 VV/VH via S3 CLI and computes proxy backscatter drop.
    Returns an explicit confidence flag ("High", "Moderate", "Low", "Unknown").
    """
    recent_items = _search_sentinel1_stac(latitude, longitude, 60, 0)
    baseline_items = _search_sentinel1_stac(latitude, longitude, 425, 305) # ~1 year ago
    
    if not recent_items or not baseline_items:
        return "Unknown (No S1 Data)"
        
    logger.info("Downloading SAR Baseline...")
    b_paths = _download_s1_bands(baseline_items[0], "baseline")
    logger.info("Downloading SAR Recent...")
    r_paths = _download_s1_bands(recent_items[0], "recent")
    
    if "vh" not in b_paths or "vh" not in r_paths:
         return "Unknown (Missing VH band)"
         
    try:
        with rasterio.open(b_paths["vh"]) as b_src:
            b_vh = b_src.read(1).astype("float32")
        with rasterio.open(r_paths["vh"]) as r_src:
            r_vh = r_src.read(1).astype("float32")
            
        # Handle nan values/borders
        b_vh = np.where(b_vh == 0, np.nan, b_vh)
        r_vh = np.where(r_vh == 0, np.nan, r_vh)
        
        b_mean = float(np.nanmean(b_vh))
        r_mean = float(np.nanmean(r_vh))
        
        # Loss of structural footprint (canopy) drops VH backscatter
        # Highly negative backscatter (db) dropping further indicates clearing.
        # Approximation: if recent is lower (more negative db) than baseline by > 1.5, it's strong evidence.
        drop = b_mean - r_mean 
        
        if drop > 1.5:
            return "High Confidence (SAR verified extensive loss)"
        elif drop > 0.5:
            return "Moderate Confidence (SAR detected partial loss)"
        else:
            return "Low Confidence (SAR stable, optical artifact possible)"
    except Exception as e:
        logger.error(f"SAR analytics error: {e}")
        return "Unknown (SAR processing failed)"
