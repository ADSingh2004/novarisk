import rasterio
import numpy as np
import stackstac
from typing import Dict, Any, Tuple
from app.utils.spatial import generate_bbox

def calculate_ndvi_from_stac_items(items: list, bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """
    Calculates NDVI from a list of Sentinel-2 STAC items.
    Uses stackstac to create an xarray DataArray from the items, cropped to the bbox.
    NDVI = (NIR - Red) / (NIR + Red)
    For Sentinel-2: NIR is Band 8 (B08), Red is Band 4 (B04)
    """
    if not items:
        return {"error": "No Sentinel-2 items found"}
        
    try:
        # Create a datacube from the STAC items. 
        # stackstac handles fetching and reprojecting automatically.
        # We limit assets to just what we need to save memory/bandwidth.
        cube = stackstac.stack(
            items,
            assets=["B04", "B08"],  # Red, NIR
            bounds_latlon=bbox      # Crop to our required bounding box
        )
        
        # Take the median across time (if multiple items exist) to reduce cloud/shadow effects
        composite = cube.median(dim="time", skipna=True).compute()
        
        red = composite.sel(band="B04").astype(float)
        nir = composite.sel(band="B08").astype(float)
        
        # Calculate NDVI
        ndvi = (nir - red) / (nir + red)
        
        # Calculate mean NDVI over the area
        mean_ndvi = float(ndvi.mean(skipna=True).values)
        
        return {
            "mean_ndvi": mean_ndvi,
            "status": "success",
            "message": "NDVI calculated successfully"
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
