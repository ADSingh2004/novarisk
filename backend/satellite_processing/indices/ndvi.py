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
        return {"error": "No Sentinel-2 items found", "status": "failed"}
        
    try:
        import numpy as np
        # Create a datacube from the STAC items with explicit EPSG:4326 CRS
        # This avoids CRS mismatch errors between assets
        cube = stackstac.stack(
            items,
            assets=["B04", "B08"],  # Red, NIR
            bounds_latlon=bbox,     # Crop to our required bounding box
            epsg=4326               # Explicitly specify EPSG:4326 (WGS84)
        )
        
        # Take the median across time (if multiple items exist) to reduce cloud/shadow effects
        composite = cube.median(dim="time", skipna=True).compute()
        
        red = composite.sel(band="B04").astype(float)
        nir = composite.sel(band="B08").astype(float)
        
        # Mask pixels where both bands are 0 (nodata / fill values)
        valid_mask = (red + nir) > 0
        red = red.where(valid_mask)
        nir = nir.where(valid_mask)
        
        # Calculate NDVI, guard against divide-by-zero
        denom = (nir + red)
        ndvi = (nir - red) / denom.where(denom != 0)
        
        # Calculate mean NDVI over the area
        mean_ndvi = float(ndvi.mean(skipna=True).values)
        
        # Validate result is not NaN
        if np.isnan(mean_ndvi):
            return {"error": "NDVI calculation resulted in NaN", "status": "failed"}
        
        return {
            "mean_ndvi": mean_ndvi,
            "status": "success",
            "message": "NDVI calculated successfully"
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
