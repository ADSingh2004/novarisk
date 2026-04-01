import math
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add backend to path so we can import app modules
_backend_path = os.path.join(os.path.dirname(__file__), '../../backend')
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from app.utils.spatial import generate_bbox
from satellite_processing.client import search_landsat
from satellite_processing.indices.land_surface_temperature import calculate_lst_from_stac_items

def calculate_urban_heat_island(latitude: float, longitude: float, facility_radius_km: float = 1.0, rural_radius_km: float = 10.0, reference_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculates Urban Heat Island (UHI) intensity proxy.
    Logic: Compares Land Surface Temperature (LST) immediately around the facility
    with the larger surrounding "rural" buffer area.
    Uses a pinned reference_time to ensure deterministic results within a single request.
    """
    # Pin a single reference time
    ref_time = reference_time if reference_time else datetime.utcnow()
    
    # 1. Fetch Landsat items for the larger extent
    rural_bbox = generate_bbox(latitude, longitude, rural_radius_km)
    facility_bbox = generate_bbox(latitude, longitude, facility_radius_km)
    
    items = search_landsat(latitude, longitude, rural_radius_km, days_back=60, reference_time=ref_time)
    
    if not items:
        return {"error": "No Landsat items found within the last 60 days", "status": "failed"}
    
    # Calculate for the inner facility area (high resolution)
    facility_lst_res = calculate_lst_from_stac_items(items, facility_bbox, resolution=30)
    
    # Calculate for the larger surrounding area (lower resolution for performance)
    # Note: A true UHI would ideally mask out the urban core, but for demo brevity
    # comparing a 1km core vs a 10km regional average provides a decent proxy.
    rural_lst_res = calculate_lst_from_stac_items(items, rural_bbox, resolution=100)
    
    if facility_lst_res["status"] == "failed" or rural_lst_res["status"] == "failed":

        return {"error": "Failed to calculate LST", "facility": facility_lst_res, "rural": rural_lst_res, "status": "partial"}
        
    facility_lst = facility_lst_res["mean_lst_celsius"]
    rural_lst = rural_lst_res["mean_lst_celsius"]
    
    # Guard against NaN
    if math.isnan(facility_lst) or math.isnan(rural_lst):

        return {
            "metric_name": "Urban Heat Island Intensity",
            "score": 0.0,
            "uhi_intensity_celsius": 0.0,
            "facility_lst": 0.0,
            "regional_lst": 0.0,
            "status": "partial",
            "warning": "LST values are NaN"
        }
    
    # UHI Intensity is the temperature difference
    uhi_intensity = facility_lst - rural_lst
    
    # Scale UHI to a 0-100 risk score (e.g., > 10 degrees diff = 100 risk)
    risk_score = max(0.0, min(100.0, uhi_intensity * 10.0))
    

    
    return {
        "metric_name": "Urban Heat Island Intensity",
        "score": round(risk_score, 2),
        "uhi_intensity_celsius": round(uhi_intensity, 2),
        "facility_lst": round(facility_lst, 2),
        "regional_lst": round(rural_lst, 2),
        "status": "success"
    }
