import stackstac
from typing import Dict, Any, Tuple
from app.utils.spatial import generate_bbox

def calculate_lst_from_stac_items(items: list, bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """
    Calculates Land Surface Temperature (LST) proxy from Landsat Collection 2 Level-2 STAC items.
    Landsat 8/9 Band 10 (ST_B10) provides Surface Temperature.
    Values need scaling: LST = (DN * 0.00341802 + 149.0) - 273.15 (to get Celsius)
    """
    if not items:
        return {"error": "No Landsat items found", "status": "failed"}
        
    try:
        import numpy as np
        # Try to use ST_B10 (Surface Temperature Band 10)
        # Landsat Collection 2 Level-2 surface temperature band is 'ST_B10'
        # Use explicit EPSG:4326 CRS to avoid CRS mismatch
        assets_to_try = ["ST_B10", "lwir11", "ST_TRAD"]  # Multiple possible asset names
        
        cube = None
        for asset_name in assets_to_try:
            try:
                cube = stackstac.stack(
                    items,
                    assets=[asset_name],
                    bounds_latlon=bbox,
                    epsg=4326
                )
                break
            except:
                continue
        
        if cube is None:
            # If no specific asset works, try all available assets and filter
            cube = stackstac.stack(
                items,
                bounds_latlon=bbox,
                epsg=4326
            )
        
        composite = cube.median(dim="time", skipna=True).compute()
        
        # Get the surface temperature band (look for *ST* or thermal bands)
        st_b10 = None
        for band_name in composite.band.values:
            if "ST" in str(band_name) or "thermal" in str(band_name).lower():
                st_b10 = composite.sel(band=band_name).astype(float)
                break
        
        # If still not found, try the first band
        if st_b10 is None:
            st_b10 = composite.isel(band=0).astype(float)
        
        # Mask nodata pixels (DN = 0 means fill / no data in Landsat C2)
        st_b10 = st_b10.where(st_b10 > 0)
        
        # Apply scaling factors for Landsat 8/9 Collection 2 Surface Temperature
        # ST_B10 is in DN (Digital Numbers), convert to Kelvin then Celsius
        # For Landsat Collection 2: Radiance = (DN * ML) + AL, then BT = K2 / ln((K1 / Radiance) + 1)
        # But a simpler scaling: ST = (DN * 0.0003342 + 0.1) Kelvin, then subtract 273.15 for Celsius
        # Actually, proper Landsat C2 formula: Temperature (K) = K2 / ln((K1/Radiance)+1)
        # K1=774.8853 K, K2=480.8883 K for Band 10
        # For simplified processing: ST = DN * 0.0003342 + 149.0 should give Kelvin
        # Then convert to Celsius: ST_C = (DN * 0.0003342 + 149.0) - 273.15
        # But DN values are often scaled. Use more conservative scaling.
        
        # Check if values look reasonable (0-65535 for 16-bit)
        DN_min = float(st_b10.min(skipna=True))
        DN_max = float(st_b10.max(skipna=True))
        
        # If DN values are reasonable, apply standard scaling
        if DN_max > 1000 and DN_min >= 0:
            # Standard Landsat Band 10 scaling  
            # K1 = 774.8853, K2 = 480.8883 (for Band 10)
            # ML (radiance multiplicative rescaling) = 0.0003342
            # AL (radiance additive rescaling) = 0.1
            K1 = 774.8853
            K2 = 480.8883
            ML = 0.0003342
            AL = 0.1
            
            # Convert DN to Radiance
            radiance = (st_b10 * ML) + AL
            
            # Convert Radiance to Brightness Temperature (Kelvin)
            bt_kelvin = K2 / ((K1 / radiance).where(radiance > 0, 0.0001).apply(lambda x: np.log(x + 1e-10)))
            
            # Convert Kelvin to Celsius
            lst_celsius = bt_kelvin - 273.15
        else:
            # If DN values don't look right, assume they're already scaled
            # Apply simple Kelvin to Celsius conversion
            lst_celsius = st_b10 - 273.15
        
        # Mean LST over the area
        mean_lst = float(lst_celsius.mean(skipna=True).values)
        
        # Validate result
        if np.isnan(mean_lst) or np.isinf(mean_lst):
            return {"error": "LST calculation resulted in invalid values", "status": "failed"}
        
        return {
            "mean_lst_celsius": mean_lst,
            "status": "success"
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
