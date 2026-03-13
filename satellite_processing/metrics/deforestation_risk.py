from datetime import datetime, timedelta
from typing import Dict, Any
from app.utils.spatial import generate_bbox
from satellite_processing.client import search_sentinel2
from satellite_processing.indices.ndvi import calculate_ndvi_from_stac_items

def calculate_deforestation_risk(latitude: float, longitude: float, radius_km: float = 5.0) -> Dict[str, Any]:
    """
    Calculates a Deforestation Risk Metric (0-100 score).
    Logic: Compares recent NDVI to a historical baseline.
    If recent NDVI is significantly lower, risk is higher.
    """
    bbox = generate_bbox(latitude, longitude, radius_km)
    
    # 1. Fetch recent imagery (last 30 days)
    recent_items = search_sentinel2(latitude, longitude, radius_km, days_back=30)
    recent_ndvi_res = calculate_ndvi_from_stac_items(recent_items, bbox)
    
    # 2. Fetch baseline imagery (e.g., from a year ago)
    # Since Planetary Computer search doesn't easily allow "exactly 1 year ago" with our helper, 
    # we simulate an older fetch for the demo:
    historical_items = search_sentinel2(latitude, longitude, radius_km, days_back=365)
    # Just take items older than 330 days
    baseline_items = [i for i in historical_items if i.datetime < datetime.utcnow().replace(tzinfo=i.datetime.tzinfo) - timedelta(days=330)]
    baseline_ndvi_res = calculate_ndvi_from_stac_items(baseline_items, bbox)
    
    if recent_ndvi_res["status"] == "failed" or baseline_ndvi_res["status"] == "failed":
        return {"error": "Failed to calculate NDVI", "recent": recent_ndvi_res, "baseline": baseline_ndvi_res}
        
    recent_val = recent_ndvi_res["mean_ndvi"]
    baseline_val = baseline_ndvi_res["mean_ndvi"]
    
    # Calculate drop percentage
    # NDVI goes -1 to 1. Usually >0.2 is vegetation. 
    # A simple drop calculation: max(0, baseline - recent) / baseline
    
    if baseline_val <= 0:
        # If baseline wasn't vegetated, there's no deforestation risk
        risk_score = 0.0
    else:
        drop = max(0.0, baseline_val - recent_val)
        risk_score = min(100.0, (drop / baseline_val) * 100.0 * 2.5) # Scale factor for demo
        
    return {
        "metric_name": "Deforestation Risk",
        "score": round(risk_score, 2),
        "recent_ndvi": round(recent_val, 4),
        "baseline_ndvi": round(baseline_val, 4),
        "status": "success"
    }
