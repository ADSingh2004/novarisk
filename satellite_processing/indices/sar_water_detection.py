import stackstac
import numpy as np
from typing import Dict, Any, Tuple
from app.utils.spatial import generate_bbox

def calculate_sar_water_mask_from_stac_items(
    items: list, 
    bbox: Tuple[float, float, float, float], 
    threshold_db: float = -15.0
) -> Dict[str, Any]:
    """
    Calculates water area using Sentinel-1 SAR (Synthetic Aperture Radar) items.
    Water typically exhibits very low radar backscatter in VV and VH polarizations.
    This function uses VV polarization backscatter converted to decibels.
    """
    if not items:
        return {"error": "No Sentinel-1 items found", "status": "failed"}
        
    try:
        # Load VV band - use explicit epsg=3857 to handle missing projection metadata
        # which is common in some Sentinel-1 STAC items on Planetary Computer.
        cube = stackstac.stack(
            items,
            assets=["vv"],
            bounds_latlon=bbox,
            resolution=10,
            epsg=3857
        )
        
        # Determine temporal median to reduce speckle noise
        composite = cube.median(dim="time", skipna=True).compute()
        
        # Convert amplitude backscatter (linear) to decibels (dB)
        # Note: Depending on the specific STAC product, the values might already be in dB
        # or require conversion. Planetary computer Sentinel-1 RTC is usually linear power or gamma0.
        # Ensure positive values before applying log10 to avoid NaNs.
        vv_linear = composite.sel(band="vv").astype(float).values
        # Mask out values <= 0
        vv_linear_valid = np.where(vv_linear > 0, vv_linear, np.nan)
        
        # Convert to dB
        vv_db = 10 * np.log10(vv_linear_valid)
        
        # Apply threshold to detect water
        water_mask = vv_db < threshold_db
        
        # Calculate fraction of water pixels (ignoring NaNs)
        valid_pixels = ~np.isnan(vv_db)
        total_valid = np.sum(valid_pixels)
        
        if total_valid == 0:
            return {"error": "No valid SAR data in bbox", "status": "failed"}
            
        water_pixels = np.sum(water_mask & valid_pixels)
        water_area_fraction = float(water_pixels / total_valid)
        
        return {
            "sar_water_area_fraction": water_area_fraction,
            "mean_vv_db": float(np.nanmean(vv_db)),
            "status": "success"
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
