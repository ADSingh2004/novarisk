import stackstac
import math
import numpy as np
from typing import Dict, Any, Tuple
from app.utils.spatial import generate_bbox

def calculate_lst_from_stac_items(items: list, bbox: Tuple[float, float, float, float], resolution: int = 30) -> Dict[str, Any]:
    """
    Calculates Land Surface Temperature (LST) proxy from Landsat Collection 2 Level-2 STAC items.
    Landsat 8/9 Band 10 (ST_B10) provides Surface Temperature.
    Values need scaling: LST = (DN * 0.00341802 + 149.0) - 273.15 (to get Celsius)
    """
    if not items:
        return {"error": "No Landsat items found", "status": "failed"}
        
    try:
        # Landsat Collection 2 Level-2 surface temperature band is usually called lwir11
        # Use EPSG:3857 to ensure resolution is interpreted in meters
        cube = stackstac.stack(
            items,
            assets=["lwir11"],
            bounds_latlon=bbox,
            resolution=resolution,
            epsg=3857
        )
        
        # Mask out 0 (NoData) before temporal median
        cube = cube.where(cube > 0)
        composite = cube.median(dim="time", skipna=True).compute()
        st_b10 = composite.sel(band="lwir11").astype(float)
        
        # Planetary Computer Landsat C2 L2 lwir11 is already in Kelvin.
        # Convert Kelvin to Celsius by subtracting 273.15
        lst_celsius = st_b10 - 273.15
        
        # Mean LST over the area
        mean_lst = float(np.nanmean(lst_celsius))
        
        if math.isnan(mean_lst):
            return {"error": "LST calculation produced all-NaN values", "status": "failed", "mean_lst_celsius": 0.0}
        
        return {
            "mean_lst_celsius": mean_lst,
            "status": "success"
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
