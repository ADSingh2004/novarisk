import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Add backend to path so we can import app modules
_backend_path = os.path.join(os.path.dirname(__file__), '../../backend')
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from app.utils.spatial import generate_bbox
from satellite_processing.client import search_sentinel2
from satellite_processing.indices.ndwi import calculate_ndwi_from_stac_items

def calculate_water_stress_proxy(latitude: float, longitude: float, radius_km: float = 5.0, reference_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculates a Water Stress Proxy Metric (0-100 score).
    Logic: Compares recent NDWI to a historical baseline.
    If recent NDWI is significantly lower, water bodies may be shrinking (higher stress).
    Uses a pinned reference_time to ensure deterministic results within a single request.
    """
    # Pin a single reference time for all date calculations in this function
    ref_time = reference_time if reference_time else datetime.utcnow()
    
    bbox = generate_bbox(latitude, longitude, radius_km)
    
    # 1. Fetch recent imagery (last 30 days)
    recent_items = search_sentinel2(latitude, longitude, radius_km, days_back=30, reference_time=ref_time)
    recent_ndwi_res = calculate_ndwi_from_stac_items(recent_items, bbox)
    
    # 2. Fetch baseline imagery (approx 1 year ago)
    historical_items = search_sentinel2(latitude, longitude, radius_km, days_back=365, reference_time=ref_time)
    baseline_items = [i for i in historical_items if i.datetime < ref_time.replace(tzinfo=i.datetime.tzinfo) - timedelta(days=330)]
    baseline_ndwi_res = calculate_ndwi_from_stac_items(baseline_items, bbox)
    
    if recent_ndwi_res["status"] == "failed" or baseline_ndwi_res["status"] == "failed":
        return {"error": "Failed to calculate NDWI", "recent": recent_ndwi_res, "baseline": baseline_ndwi_res}
        
    recent_val = recent_ndwi_res["mean_ndwi"]
    baseline_val = baseline_ndwi_res["mean_ndwi"]
    
    # Water has NDWI > 0 usually
    if baseline_val <= 0:
        # If no significant water bodies detected in baseline, metric is not applicable
        risk_score = 0.0
    else:
        drop = max(0.0, baseline_val - recent_val)
        risk_score = min(100.0, (drop / baseline_val) * 100.0 * 2.5) # Scale factor for demo
        
    return {
        "metric_name": "Water Stress Proxy",
        "score": round(risk_score, 2),
        "recent_ndwi": round(recent_val, 4),
        "baseline_ndwi": round(baseline_val, 4),
        "status": "success"
    }
