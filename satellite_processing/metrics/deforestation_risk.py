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
from satellite_processing.client import search_sentinel2
from satellite_processing.indices.multi_index import calculate_ndvi_from_stac_items_optimized

logger = logging.getLogger(__name__)

def calculate_deforestation_risk(latitude: float, longitude: float, radius_km: float = 5.0, reference_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculates a Deforestation Risk Metric (0-100 score).
    Logic: Compares recent NDVI to a historical baseline.
    If recent NDVI is significantly lower, risk is higher.
    Uses a pinned reference_time to ensure deterministic results within a single request.
    
    OPTIMIZED: Uses multi_index module to avoid redundant composite calculations.
    Now uses cached STAC searches (see client.py).
    """
    # Pin a single reference time for all date calculations in this function
    ref_time = reference_time if reference_time else datetime.utcnow()
    bbox = generate_bbox(latitude, longitude, radius_km)
    
    logger.info(f"📍 Deforestation Risk Analysis: lat={latitude:.4f}, lon={longitude:.4f}, radius={radius_km}km")
    
    # 1. Fetch recent imagery (last 30 days) — cached on client side
    logger.info("🔍 Searching recent Sentinel-2 imagery (30 days)...")
    recent_items = search_sentinel2(latitude, longitude, radius_km, days_back=30, reference_time=ref_time, max_items=5)
    logger.info(f"  Found {len(recent_items)} recent items")
    recent_ndvi_res = calculate_ndvi_from_stac_items_optimized(recent_items[:5], bbox)
    logger.info(f"  Recent NDVI: {recent_ndvi_res}")
    
    # 2. Fetch baseline imagery (from a year ago) — cached on client side
    logger.info("🔍 Searching baseline Sentinel-2 imagery (180+ days old)...")
    historical_items = search_sentinel2(latitude, longitude, radius_km, days_back=365, reference_time=ref_time, max_items=10)
    logger.info(f"  Found {len(historical_items)} historical items")
    # Take items older than 180 days (more flexible than 330+ to avoid missing baseline for sparse regions)
    baseline_items = [i for i in historical_items if i.datetime < ref_time.replace(tzinfo=i.datetime.tzinfo) - timedelta(days=180)][:5]
    logger.info(f"  Filtered to {len(baseline_items)} baseline items (180+ days)")
    baseline_ndvi_res = calculate_ndvi_from_stac_items_optimized(baseline_items, bbox)
    logger.info(f"  Baseline NDVI: {baseline_ndvi_res}")

    
    if recent_ndvi_res["status"] == "failed" or baseline_ndvi_res["status"] == "failed":
        logger.error(f"❌ NDVI calculation failed. Recent status: {recent_ndvi_res.get('status')}, Baseline status: {baseline_ndvi_res.get('status')}")
        # Even if failed, return a structured response with score 0
        return {
            "metric_name": "Deforestation Risk",
            "score": 0.0,
            "recent_ndvi": recent_ndvi_res.get("mean_ndvi", 0.0),
            "baseline_ndvi": baseline_ndvi_res.get("mean_ndvi", 0.0),
            "status": "partial",
            "warning": "Some NDVI calculations failed — check satellite data availability",
            "recent_error": recent_ndvi_res.get("error"),
            "baseline_error": baseline_ndvi_res.get("error")
        }
        
    recent_val = recent_ndvi_res["mean_ndvi"]
    baseline_val = baseline_ndvi_res["mean_ndvi"]
    
    logger.info(f"📊 NDVI Values - Recent: {recent_val:.4f}, Baseline: {baseline_val:.4f}")
    
    # Guard against NaN values
    if math.isnan(recent_val) or math.isnan(baseline_val):
        logger.warning(f"⚠️ NaN values detected: Recent={recent_val}, Baseline={baseline_val}")
        return {
            "metric_name": "Deforestation Risk",
            "score": 0.0,
            "recent_ndvi": 0.0,
            "baseline_ndvi": 0.0,
            "status": "partial",
            "warning": "NDVI values are NaN"
        }
    
    # Calculate drop percentage
    # NDVI goes -1 to 1. Usually >0.2 is vegetation. 
    # A simple drop calculation: (baseline - recent) / max(|baseline|, 0.4)  
    # Using max(|baseline|, 0.4) handles arid regions where NDVI is already low
    
    # If both values are very low (arid region), calculate the relative change
    if abs(baseline_val) < 0.1 and abs(recent_val) < 0.1:
        # Both low - minimal deforestation risk in arid region
        logger.info("📍 Region has low vegetation (arid/desert) - both NDVI values < 0.1")
        risk_score = 0.0
    elif baseline_val <= 0 and recent_val <= 0:
        # Both non-positive - minimal deforestation risk
        logger.info(f"📍 Both NDVI values non-positive (water/barren) - Baseline: {baseline_val}, Recent: {recent_val}")
        risk_score = 0.0
    elif baseline_val <= 0 < recent_val:
        # Unusual: baseline was barren but recent has some vegetation
        logger.info(f"📈 Vegetation recovery detected: Baseline={baseline_val} → Recent={recent_val}")
        risk_score = 0.0
    else:
        # Normal case: baseline has vegetation
        drop = max(0.0, baseline_val - recent_val)
        # Use normalized denominator to handle small NDVI values
        denom = max(abs(baseline_val), 0.1)  # Avoid division issues in arid regions
        risk_score = min(100.0, (drop / denom) * 100.0 * 2.5)  # Scale factor
        logger.info(f"🔥 Deforestation Risk Calculation: drop={drop:.4f}, denom={denom:.4f}, risk_score={risk_score:.2f}")

        
    logger.info(f"✅ Final Deforestation Risk Score: {risk_score:.2f}")
    
    

        
    return {
        "metric_name": "Deforestation Risk",
        "score": round(risk_score, 2),
        "recent_ndvi": round(recent_val, 4),
        "baseline_ndvi": round(baseline_val, 4),
        "status": "success"
    }
