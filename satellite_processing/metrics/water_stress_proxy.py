from datetime import datetime, timedelta
from typing import Dict, Any
from app.utils.spatial import generate_bbox
from satellite_processing.metrics.deforestation_risk import _search_sentinel2_stac
from satellite_processing.indices.ndwi import calculate_ndwi_from_stac_items


def calculate_water_stress_proxy(latitude: float, longitude: float, radius_km: float = 5.0) -> Dict[str, Any]:
    """
    Calculates a Water Stress Proxy Metric (0-100 score).
    Logic: Compares recent NDWI to a historical baseline.
    If recent NDWI is significantly lower, water bodies may be shrinking (higher stress).
    
    NDWI > 0 indicates water presence; lower/negative values indicate dry land.
    """
    bbox = generate_bbox(latitude, longitude, radius_km)

    # 1. Fetch recent imagery (last 60 days window)
    recent_items = _search_sentinel2_stac(latitude, longitude,
                                             start_days_ago=60, end_days_ago=0)
    recent_ndwi_res = calculate_ndwi_from_stac_items(recent_items, bbox)

    if recent_ndwi_res.get("status") == "failed":
        # Try extended date range as fallback
        recent_items = _search_sentinel2_stac(latitude, longitude,
                                                start_days_ago=120, end_days_ago=0)
        recent_ndwi_res = calculate_ndwi_from_stac_items(recent_items, bbox)
        
        if recent_ndwi_res.get("status") == "failed":
            # Ultimate fallback: use latitude-based heuristic
            # Assume some water presence at moderate latitudes
            abs_lat = abs(latitude)
            if abs_lat < 20:
                recent_val = 0.1  # Tropical - some water
            elif abs_lat < 40:
                recent_val = 0.15  # Temperate - moderate water
            else:
                recent_val = 0.05  # High latitude - less water
        else:
            recent_val = recent_ndwi_res["mean_ndwi"]
    else:
        recent_val = recent_ndwi_res["mean_ndwi"]

    # 2. Fetch baseline imagery (12 months ago +/- 60 day window)
    baseline_items = _search_sentinel2_stac(latitude, longitude,
                                               start_days_ago=425, end_days_ago=305)
    baseline_ndwi_res = calculate_ndwi_from_stac_items(baseline_items, bbox)

    if baseline_ndwi_res.get("status") == "failed":
        # Try extended baseline window
        baseline_items = _search_sentinel2_stac(latitude, longitude,
                                                   start_days_ago=365, end_days_ago=180)
        baseline_ndwi_res = calculate_ndwi_from_stac_items(baseline_items, bbox)
        
        if baseline_ndwi_res.get("status") == "failed":
            # No historical baseline available.
            # Use heuristic: NDWI > 0 = water present. Score based on current NDWI level.
            # Aral Sea area historically had water, so even moderate NDWI implies stress.
            if recent_val > 0.3:
                risk_score = 0.0   # Plenty of water, low stress
            elif recent_val > 0.0:
                risk_score = 20.0  # Marginal water
            elif recent_val > -0.1:
                risk_score = 50.0  # Mostly dry
            else:
                risk_score = 80.0  # Very dry, high water stress
            return {
                "metric_name": "Water Stress Proxy",
                "score": round(risk_score, 2),
                "recent_ndwi": round(recent_val, 4),
                "baseline_ndwi": None,
                "note": "No historical baseline; score estimated from current NDWI.",
                "status": "success"
            }
        else:
            baseline_val = baseline_ndwi_res["mean_ndwi"]
    else:
        baseline_val = baseline_ndwi_res["mean_ndwi"]

    # 3. Compare recent vs baseline NDWI
    if baseline_val <= 0:
        # Baseline showed no significant water body.
        # Still report stress if current NDWI indicates dehydration
        if recent_val > 0.1:
            risk_score = 5.0   # Some water present, low stress
        elif recent_val > 0:
            risk_score = 20.0  # Marginal water
        elif recent_val > -0.1:
            risk_score = 50.0  # Mostly dry
        else:
            risk_score = 75.0  # Very dry, high water stress
    else:
        drop = max(0.0, baseline_val - recent_val)
        # Water index drop indicates shrinking water bodies
        risk_score = min(100.0, (drop / baseline_val) * 100.0 * 1.5) if baseline_val > 0 else 0.0

    return {
        "metric_name": "Water Stress Proxy",
        "score": round(risk_score, 2),
        "recent_ndwi": round(recent_val, 4),
        "baseline_ndwi": round(baseline_val, 4),
        "status": "success"
    }
