import stackstac
import numpy as np
import math
from typing import Dict, Any, Tuple
from app.utils.spatial import generate_bbox

def calculate_ndwi_from_stac_items(items: list, bbox: Tuple[float, float, float, float], explain: bool = False) -> Dict[str, Any]:
    if not items:
        return {"error": "No Sentinel-2 items found", "status": "failed"}
            
    try:
        # Use Web Mercator (EPSG:3857) to ensure meter-based resolution works
        cube = stackstac.stack(
            items,
            assets=["B03", "B08"],  # Green, NIR
            bounds_latlon=bbox,
            resolution=20,          # 20 meters
            epsg=3857               # Web Mercator
        )

        
        # Mask nodata (0 values) before computing median
        cube = cube.where(cube > 0)
        composite = cube.median(dim="time", skipna=True).compute()
        
        green = composite.sel(band="B03").astype(float)
        nir = composite.sel(band="B08").astype(float)
        
        # Guard against division by zero
        denominator = green + nir
        ndwi = np.where(denominator != 0, (green - nir) / (green + nir), np.nan)
        
        mean_ndwi_val = float(np.nanmean(ndwi))
        
        # Check if result is NaN (all pixels were nodata)
        if math.isnan(mean_ndwi_val):
            return {"error": "NDWI calculation produced all-NaN values", "status": "failed", "mean_ndwi": 0.0}
        
        # Water fraction: proportion of pixels where ndwi > 0
        valid_mask = ~np.isnan(ndwi)
        total_valid = np.sum(valid_mask)
        water_pixels = np.sum((ndwi > 0) & valid_mask)
        water_fraction = float(water_pixels / total_valid) if total_valid > 0 else 0.0
        

        
        result = {
            "mean_ndwi": mean_ndwi_val,
            "water_fraction": water_fraction,
            "status": "success"
        }
        if explain:
            result["ndwi_array"] = np.nan_to_num(ndwi if isinstance(ndwi, np.ndarray) else ndwi.values, nan=0.0).tolist()
            
        return result
    except Exception as e:
        return {"error": str(e), "status": "failed"}
