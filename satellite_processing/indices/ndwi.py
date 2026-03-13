import stackstac
from typing import Dict, Any, Tuple
from app.utils.spatial import generate_bbox

def calculate_ndwi_from_stac_items(items: list, bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """
    Calculates NDWI (Normalized Difference Water Index) from Sentinel-2 STAC items.
    NDWI = (Green - NIR) / (Green + NIR)
    For Sentinel-2: Green is Band 3 (B03), NIR is Band 8 (B08)
    """
    if not items:
        return {"error": "No Sentinel-2 items found", "status": "failed"}
        
    try:
        import numpy as np
        # Create a datacube with explicit EPSG:4326 CRS to avoid CRS mismatch
        cube = stackstac.stack(
            items,
            assets=["B03", "B08"],  # Green, NIR
            bounds_latlon=bbox,
            epsg=4326               # Explicitly specify EPSG:4326 (WGS84)
        )
        
        composite = cube.median(dim="time", skipna=True).compute()
        
        green = composite.sel(band="B03").astype(float)
        nir = composite.sel(band="B08").astype(float)
        
        # Mask pixels where both bands are 0 (nodata / fill values)
        valid_mask = (green + nir) > 0
        green = green.where(valid_mask)
        nir = nir.where(valid_mask)
        
        # Calculate NDWI, guard against divide-by-zero
        denom = (green + nir)
        ndwi = (green - nir) / denom.where(denom != 0)
        
        # Mean NDWI over the area
        mean_ndwi = float(ndwi.mean(skipna=True).values)
        
        # Validate result is not NaN
        if np.isnan(mean_ndwi):
            return {"error": "NDWI calculation resulted in NaN", "status": "failed"}
        
        return {
            "mean_ndwi": mean_ndwi,
            "status": "success"
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
