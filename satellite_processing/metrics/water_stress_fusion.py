import math
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Add backend to path so we can import app modules
_backend_path = os.path.join(os.path.dirname(__file__), '../../backend')
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from app.utils.spatial import generate_bbox
from app.core.cache import get_cache, set_cache

from satellite_processing.client import search_sentinel2, search_sentinel1
from satellite_processing.indices.multi_index import calculate_ndwi_from_stac_items_optimized
from satellite_processing.indices.sar_water_detection import calculate_sar_water_mask_from_stac_items

logger = logging.getLogger(__name__)

def calculate_fused_water_stress_proxy(latitude: float, longitude: float, radius_km: float = 5.0, reference_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculates a fused Water Stress Proxy Metric (0-100 score).
    Uses both optical (Sentinel-2 NDWI) and radar (Sentinel-1 SAR) to build a more robust metric.
    Uses a pinned reference_time to ensure deterministic results within a single request.
    
    OPTIMIZED: Uses multi_index module and cached STAC searches.
    """
    # Pin a single reference time for all date calculations in this function
    ref_time = reference_time if reference_time else datetime.utcnow()
    
    bbox = generate_bbox(latitude, longitude, radius_km)
    
    logger.info(f"💧 Water Stress Analysis: lat={latitude:.4f}, lon={longitude:.4f}, radius={radius_km}km")
    
    # --- OPTICAL PIPELINE (NDWI) ---
    logger.info("🔍 Optical Pipeline (NDWI - Sentinel-2)")
    # STAC searches are already cached in client.py, so these return quickly if cached
    recent_items_opt = search_sentinel2(latitude, longitude, radius_km, days_back=30, reference_time=ref_time, max_items=5)
    logger.info(f"  Found {len(recent_items_opt)} recent Sentinel-2 items")
    recent_ndwi_res = calculate_ndwi_from_stac_items_optimized(recent_items_opt[:5], bbox)
    logger.info(f"  Recent NDWI: {recent_ndwi_res}")
    
    historical_items_opt = search_sentinel2(latitude, longitude, radius_km, days_back=365, reference_time=ref_time, max_items=10)
    logger.info(f"  Found {len(historical_items_opt)} historical Sentinel-2 items")
    baseline_items_opt = [i for i in historical_items_opt if i.datetime < ref_time.replace(tzinfo=i.datetime.tzinfo) - timedelta(days=180)][:5]
    logger.info(f"  Filtered to {len(baseline_items_opt)} baseline items (180+ days)")
    baseline_ndwi_res = calculate_ndwi_from_stac_items_optimized(baseline_items_opt, bbox)
    logger.info(f"  Baseline NDWI: {baseline_ndwi_res}")
    
    # --- RADAR PIPELINE (SAR) ---
    logger.info("🛰️  Radar Pipeline (SAR Water Mask - Sentinel-1)")
    # We cache SAR requests locally because processing SAR median is expensive.
    cache_key_sar_recent = f"sar_water_cache:{latitude}:{longitude}:{radius_km}:sentinel-1-grd:30"
    recent_sar_res = get_cache(cache_key_sar_recent)
    
    if not recent_sar_res:
        logger.info("  SAR recent cache miss - computing...")
        recent_items_sar = search_sentinel1(latitude, longitude, radius_km, days_back=30, reference_time=ref_time, max_items=5)
        logger.info(f"  Found {len(recent_items_sar)} recent Sentinel-1 items")
        recent_sar_res = calculate_sar_water_mask_from_stac_items(recent_items_sar[:5], bbox)
        logger.info(f"  Recent SAR: {recent_sar_res}")
        if recent_sar_res.get("status") == "success":
            set_cache(cache_key_sar_recent, recent_sar_res, 86400)
    else:
        logger.info(f"  SAR recent cache hit: {recent_sar_res}")
            
    cache_key_sar_baseline = f"sar_water_cache:{latitude}:{longitude}:{radius_km}:sentinel-1-grd:365"
    baseline_sar_res = get_cache(cache_key_sar_baseline)
    
    if not baseline_sar_res:
        logger.info("  SAR baseline cache miss - computing...")
        historical_items_sar = search_sentinel1(latitude, longitude, radius_km, days_back=365, reference_time=ref_time, max_items=10)
        logger.info(f"  Found {len(historical_items_sar)} historical Sentinel-1 items")
        # Filter for the baseline window using the same pinned reference time (180+ days)
        baseline_items_sar = [i for i in historical_items_sar if i.datetime < ref_time.replace(tzinfo=i.datetime.tzinfo) - timedelta(days=180)][:5]
        logger.info(f"  Filtered to {len(baseline_items_sar)} baseline items (180+ days)")
        baseline_sar_res = calculate_sar_water_mask_from_stac_items(baseline_items_sar, bbox)
        logger.info(f"  Baseline SAR: {baseline_sar_res}")
        if baseline_sar_res.get("status") == "success":
            set_cache(cache_key_sar_baseline, baseline_sar_res, 86400)
    else:
        logger.info(f"  SAR baseline cache hit: {baseline_sar_res}")

    # --- FUSION LOGIC ---
    logger.info("🔀 Fusion Logic - Combining NDWI + SAR")
    
    # Process Optical Drop
    optical_drop = 0.0
    optical_risk = 0.0
    optical_valid = False
    
    if recent_ndwi_res.get("status") == "success" and baseline_ndwi_res.get("status") == "success":
        recent_val = recent_ndwi_res.get("mean_ndwi", 0.0)
        baseline_val = baseline_ndwi_res.get("mean_ndwi", 0.0)
        
        logger.info(f"  📊 NDWI Values - Recent: {recent_val:.4f}, Baseline: {baseline_val:.4f}")
        
        # Guard against NaN
        if not math.isnan(recent_val) and not math.isnan(baseline_val):
            if baseline_val > 0:
                optical_valid = True
                optical_drop = max(0.0, baseline_val - recent_val)
                optical_risk = min(100.0, (optical_drop / baseline_val) * 100.0 * 2.5)
                logger.info(f"  ✓ Optical risk calculated: {optical_risk:.2f}")
            else:
                logger.info(f"  ⚠️ Baseline NDWI <= 0: {baseline_val} (likely arid/barren)")
        else:
            logger.warning(f"  ❌ NaN values in NDWI: Recent={recent_val}, Baseline={baseline_val}")
    else:
        logger.warning(f"  ❌ NDWI calculation failed - Recent status: {recent_ndwi_res.get('status')}, Baseline status: {baseline_ndwi_res.get('status')}")

    # Process Radar Drop
    sar_drop = 0.0
    sar_risk = 0.0
    sar_valid = False
    
    recent_sar_area = 0.0
    baseline_sar_area = 0.0
    
    if recent_sar_res and recent_sar_res.get("status") == "success" and baseline_sar_res and baseline_sar_res.get("status") == "success":
        recent_sar_area = recent_sar_res.get("sar_water_area_fraction", 0.0)
        baseline_sar_area = baseline_sar_res.get("sar_water_area_fraction", 0.0)
        
        # Guard against NaN
        if not math.isnan(recent_sar_area) and not math.isnan(baseline_sar_area):
            sar_drop = baseline_sar_area - recent_sar_area
            
            # If baseline had meaningful water > 1% of area
            if baseline_sar_area > 0.01:
                sar_valid = True
                # E.g. area fraction dropped by 50% => 0.5 * 100 * 2.0 = 100 risk
                sar_risk = min(100.0, max(0.0, (sar_drop / baseline_sar_area) * 100.0 * 2.5))

        else:
            pass  # NaN values — skip radar pipeline

    # Calculate Final Score
    if optical_valid and sar_valid:
        # Fusion: average the two risks if both are valid
        final_score = (optical_risk + sar_risk) / 2.0
    elif optical_valid:
        final_score = optical_risk
    elif sar_valid:
        final_score = sar_risk
    else:
        final_score = 0.0
        
    return {
        "metric_name": "Combined Water Stress Proxy",
        "score": round(final_score, 2),
        "recent_ndwi": round(recent_ndwi_res.get("mean_ndwi", 0.0), 4) if optical_valid else None,
        "baseline_ndwi": round(baseline_ndwi_res.get("mean_ndwi", 0.0), 4) if optical_valid else None,
        "sar_water_area": round(recent_sar_area, 4),
        "sar_water_change": round(-sar_drop, 4), # Negative means it decreased
        "status": "success" if (optical_valid or sar_valid) else "failed/no_water"
    }
