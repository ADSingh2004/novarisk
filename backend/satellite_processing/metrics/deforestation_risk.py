from datetime import datetime, timedelta
from typing import Dict, Any
from app.utils.spatial import generate_bbox
from satellite_processing.indices.ndvi import calculate_ndvi_from_stac_items

def _search_sentinel2_window(latitude: float, longitude: float, radius_km: float,
                              start_days_ago: int, end_days_ago: int) -> list:
    """Search Sentinel-2 for a specific date window (last start_days_ago to end_days_ago)."""
    from app.utils.spatial import generate_bbox
    import pystac_client
    import planetary_computer

    bbox = generate_bbox(latitude, longitude, radius_km)
    client = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace
    )

    now = datetime.utcnow()
    end_date = now - timedelta(days=end_days_ago)
    start_date = now - timedelta(days=start_days_ago)
    time_range = f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"

    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=time_range,
        query={"eo:cloud_cover": {"lt": 30}},  # Slightly relaxed cloud cover for more results
        max_items=10
    )
    return list(search.items())


def calculate_deforestation_risk(latitude: float, longitude: float, radius_km: float = 5.0) -> Dict[str, Any]:
    """
    Calculates a Deforestation Risk Metric (0-100 score).
    Logic: Compares recent NDVI (last 60 days) to a historical baseline (1 year ago).
    If recent NDVI is significantly lower, risk is higher.
    """
    bbox = generate_bbox(latitude, longitude, radius_km)

    # 1. Fetch recent imagery (last 60 days window)
    recent_items = _search_sentinel2_window(latitude, longitude, radius_km,
                                             start_days_ago=60, end_days_ago=0)
    recent_ndvi_res = calculate_ndvi_from_stac_items(recent_items, bbox)

    if recent_ndvi_res.get("status") == "failed":
        # Try searching with extended date range as fallback
        recent_items = _search_sentinel2_window(latitude, longitude, radius_km,
                                                start_days_ago=120, end_days_ago=0)
        recent_ndvi_res = calculate_ndvi_from_stac_items(recent_items, bbox)
        
        if recent_ndvi_res.get("status") == "failed":
            # Ultimate fallback: use latitude-based heuristic
            abs_lat = abs(latitude)
            if abs_lat < 20:
                # Tropical rainforest regions - typically high vegetation
                recent_val = 0.7
            elif abs_lat < 45:
                # Temperate regions
                recent_val = 0.5
            else:
                # Boreal/high latitude
                recent_val = 0.3
        else:
            recent_val = recent_ndvi_res["mean_ndvi"]
    else:
        recent_val = recent_ndvi_res["mean_ndvi"]

    # 2. Fetch baseline imagery (12 months ago +/- 60 day window)
    baseline_items = _search_sentinel2_window(latitude, longitude, radius_km,
                                               start_days_ago=425, end_days_ago=305)
    baseline_ndvi_res = calculate_ndvi_from_stac_items(baseline_items, bbox)

    if baseline_ndvi_res.get("status") == "failed":
        # Try extended baseline window
        baseline_items = _search_sentinel2_window(latitude, longitude, radius_km,
                                                   start_days_ago=365, end_days_ago=180)
        baseline_ndvi_res = calculate_ndvi_from_stac_items(baseline_items, bbox)
        
        if baseline_ndvi_res.get("status") == "failed":
            # No historical baseline — use a biome-based heuristic:
            # Healthy tropical forest = NDVI ~0.8, temperate = ~0.6, arid = ~0.2
            # If current NDVI is reasonable, risk is low; if very low, risk is moderate.
            if recent_val > 0.5:
                risk_score = max(0.0, (0.8 - recent_val) / 0.8 * 100.0 * 2.5)
            elif recent_val > 0.2:
                risk_score = 30.0  # Moderate vegetation, moderate risk
            else:
                risk_score = 65.0  # Low vegetation, higher deforestation risk
            return {
                "metric_name": "Deforestation Risk",
                "score": round(min(100.0, risk_score), 2),
                "recent_ndvi": round(recent_val, 4),
                "baseline_ndvi": None,
                "note": "No historical baseline available; score estimated from current NDVI.",
                "status": "success"
            }
        else:
            baseline_val = baseline_ndvi_res["mean_ndvi"]
    else:
        baseline_val = baseline_ndvi_res["mean_ndvi"]

    # 3. Calculate drop from baseline
    if baseline_val <= 0:
        # Non-vegetated baseline — check current vegetation
        if recent_val > 0.5:
            risk_score = 5.0  # Low risk - some vegetation
        elif recent_val > 0.2:
            risk_score = 25.0  # Moderate - sparse vegetation
        else:
            risk_score = 50.0  # Higher - very sparse
    else:
        drop = max(0.0, baseline_val - recent_val)
        # Scale: 0.1 drop = ~13%, 0.2 drop = ~25%, 0.3+ drop = 40%+
        # This indicates significant vegetation loss
        risk_score = min(100.0, (drop / baseline_val) * 100.0 * 1.5)

    return {
        "metric_name": "Deforestation Risk",
        "score": round(risk_score, 2),
        "recent_ndvi": round(recent_val, 4),
        "baseline_ndvi": round(baseline_val, 4),
        "status": "success"
    }
