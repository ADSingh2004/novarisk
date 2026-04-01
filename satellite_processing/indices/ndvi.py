import rasterio
import numpy as np
import stackstac
import math
from typing import Dict, Any, Tuple
from app.utils.spatial import generate_bbox

def calculate_ndvi_from_stac_items(items: list, bbox: Tuple[float, float, float, float], explain: bool = False) -> Dict[str, Any]:
    if not items:
        return {"error": "No Sentinel-2 items found", "status": "failed"}
            
    try:
        # Use native CRS from items instead of forcing epsg=4326
        # epsg=4326 can cause misaligned/empty grids for certain regions
        cube = stackstac.stack(
            items,
            assets=["B04", "B08"],  # Red, NIR
            bounds_latlon=bbox,     # Crop to our required bounding box
            resolution=20,          # Sentinel-2 B04/B08 native 10m, use 20m for speed
            epsg=3857               # Use 3857 for meters-based resolution
        )

        
        # Mask nodata (0 values) before computing median
        cube = cube.where(cube > 0)
        composite = cube.median(dim="time", skipna=True).compute()
        
        red = composite.sel(band="B04").astype(float)
        nir = composite.sel(band="B08").astype(float)
        
        # Guard against division by zero
        denominator = nir + red
        ndvi = np.where(denominator != 0, (nir - red) / denominator, np.nan)
        
        mean_ndvi = float(np.nanmean(ndvi))
        
        # Check if result is NaN (all pixels were nodata)
        if math.isnan(mean_ndvi):
            return {"error": "NDVI calculation produced all-NaN values (no valid pixels)", "status": "failed", "mean_ndvi": 0.0}
        
        result = {
            "mean_ndvi": mean_ndvi,
            "status": "success",
            "message": "NDVI calculated successfully"
        }
        if explain:
            result["ndvi_array"] = np.nan_to_num(ndvi if isinstance(ndvi, np.ndarray) else ndvi.values, nan=0.0).tolist()
            
        return result
    except Exception as e:
        return {"error": str(e), "status": "failed"}
