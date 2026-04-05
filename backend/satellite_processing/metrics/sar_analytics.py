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
    Verify deforestation using SAR (Sentinel-1) data.
    Returns: confidence level or reason for unavailability
    
    Returns:
        str: "High", "Medium", "Low", or descriptive error message
    """
    try:
        logger.info("Downloading SAR Baseline data...")
        vv_baseline = download_s3_file_cli(s3_vv_baseline_uri, baseline_vv_path)
        vh_baseline = download_s3_file_cli(s3_vh_baseline_uri, baseline_vh_path)
        
        logger.info("Downloading SAR Recent data...")
        vv_recent = download_s3_file_cli(s3_vv_recent_uri, recent_vv_path)
        vh_recent = download_s3_file_cli(s3_vh_recent_uri, recent_vh_path)
        
        # If we have all bands, compute SAR-based deforestation verification
        # ... existing SAR computation code ...
        
        # Return confidence level
        return "High"  # or "Medium" / "Low" based on your SAR logic
    
    except Exception as e:
        error_str = str(e).lower()
        
        # More descriptive error messages instead of "Unknown (Missing VH band)"
        if "aws cli not installed" in error_str:
            logger.warning("SAR unavailable: AWS CLI not installed")
            return "Unavailable - AWS CLI not configured (using NDVI optical data)"
        
        if "connection refused" in error_str or "timeout" in error_str:
            logger.warning("SAR data unavailable due to network timeout")
            return "Unavailable - Network timeout (using NDVI optical data)"
        
        if "no such file" in error_str or "not found" in error_str:
            logger.warning("SAR data not found in S3 bucket")
            return "Unavailable - Data not in S3 (using NDVI optical data)"
        
        if "vh" in error_str or "vv" in error_str or "band" in error_str:
            logger.warning(f"SAR band missing: {e}")
            return "Partial - Band unavailable (using NDVI optical data)"
        
        # Default fallback with detailed error
        logger.warning(f"SAR verification failed: {e}")
        return f"Fallback - Using NDVI optical data ({str(e)[:40]}...)"
