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
        return {"error": "No Landsat items found"}
        
    try:
        # Landsat Collection 2 Level-2 surface temperature band is usually called lwir11 or ST_B10
        # For simplicity in this demo, we assume the asset is named 'ST_B10'
        cube = stackstac.stack(
            items,
            assets=["ST_B10"],
            bounds_latlon=bbox
        )
        
        composite = cube.median(dim="time", skipna=True).compute()
        st_b10 = composite.sel(band="ST_B10").astype(float)
        
        # Apply scaling factors for Landsat 8/9 Collection 2 Surface Temperature
        # ST = (DN * 0.00341802 + 149.0)
        # Convert Kelvin to Celsius by subtracting 273.15
        lst_celsius = (st_b10 * 0.00341802 + 149.0) - 273.15
        
        # Mean LST over the area
        mean_lst = float(lst_celsius.mean(skipna=True).values)
        
        return {
            "mean_lst_celsius": mean_lst,
            "status": "success"
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
