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
        return {"error": "No Sentinel-2 items found"}
        
    try:
        cube = stackstac.stack(
            items,
            assets=["B03", "B08"],  # Green, NIR
            bounds_latlon=bbox
        )
        
        composite = cube.median(dim="time", skipna=True).compute()
        
        green = composite.sel(band="B03").astype(float)
        nir = composite.sel(band="B08").astype(float)
        
        # Calculate NDWI
        ndwi = (green - nir) / (green + nir)
        
        # Mean NDWI over the area
        mean_ndwi = float(ndwi.mean(skipna=True).values)
        
        return {
            "mean_ndwi": mean_ndwi,
            "status": "success"
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
