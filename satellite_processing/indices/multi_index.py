"""
Optimized multi-index computation module.
Computes multiple vegetation/water indices from a single stacked cube to avoid redundant tile downloads.
"""
import numpy as np
import math
import logging
from typing import Dict, Any, Tuple, Optional, List
from app.utils.spatial import generate_bbox
from app.core.cache import get_cache, set_cache
import hashlib

logger = logging.getLogger(__name__)

def _generate_composite_cache_key(latitude: float, longitude: float, radius_km: float, 
                                  days_back: int, satellite: str = "sentinel2") -> str:
    """Generate a cache key for stacked composites."""
    query_str = f"composite_{satellite}:{latitude:.4f}:{longitude:.4f}:{radius_km}:{days_back}"
    return f"composite:{hashlib.md5(query_str.encode()).hexdigest()}"

def compute_optical_indices_from_items(items: list, bbox: Tuple[float, float, float, float], 
                                      satellite: str = "sentinel2", 
                                      return_arrays: bool = False) -> Dict[str, Any]:
    """
    OPTIMIZED: Computes NDVI, NDWI, and RGB composite from a SINGLE stacked cube.
    Avoids redundant stackstac.stack() calls and tile downloads.
    
    Args:
        items: STAC items
        bbox: Bounding box
        satellite: 'sentinel2' or 'landsat'
        return_arrays: If True, include pixel arrays for explainability
        
    Returns:
        Dict with computed indices and optional arrays
    """
    if not items:
        logger.error("compute_optical_indices_from_items: No items provided")
        return {"status": "failed", "error": "No items provided"}
    
    # Lazy import of stackstac to avoid Windows Python 3.13 circular import issue
    import stackstac
    
    logger.info(f"compute_optical_indices_from_items: Processing {len(items)} items, bbox={bbox}")
    
    try:
        # Check what assets are available in the items
        available_assets = set()
        for item in items:
            if hasattr(item, 'assets'):
                available_assets.update(item.assets.keys())
        logger.info(f"Available assets in items: {available_assets}")
        
        # Determine which NIR band to use based on available assets (Landsat uses B05, Sentinel-2 uses B08)
        nir_band = "B08" if "B08" in available_assets else "B05"
        bands_to_stack = ["B04", "B03", "B02", nir_band]
        
        logger.info(f"Stacking bands {bands_to_stack} (NIR={nir_band})...")
        try:
            cube = stackstac.stack(
                items,
                assets=bands_to_stack,  # Red, Green, Blue, NIR (flexible for both Sentinel-2 and Landsat)
                bounds_latlon=bbox,
                resolution=20,
                epsg=3857
            )
        except Exception as e:
            logger.error(f"Failed to stack cube: {e}", exc_info=True)
            return {"status": "failed", "error": f"Stack failed: {e}"}
        
        logger.info(f"Cube shape: {cube.shape}, dims: {cube.dims}, coords keys: {list(cube.coords.keys())}")
        
        # Check if cube has any valid data
        valid_count_before = np.sum(~np.isnan(cube.values.ravel()))
        logger.info(f"Cube contains {valid_count_before} valid values out of {cube.size} total")
        
        if valid_count_before == 0:
            logger.warning("Cube has no valid data - all values are NaN")
            return {"status": "failed", "error": "All cube values are NaN - no valid satellite data"}
        
        # Mask nodata (values <= 0) before computing median once
        cube_masked = cube.where(cube > 0)
        valid_count_after = np.sum(~np.isnan(cube_masked.values.ravel()))
        logger.info(f"After masking (> 0): {valid_count_after} valid values remain")
        
        logger.info("Computing median composite...")
        composite = cube_masked.median(dim="time", skipna=True).compute()
        
        logger.info(f"Composite computed: shape={composite.shape}, dtype={composite.dtype}")
        
        # Extract all bands from single composite
        red = composite.sel(band="B04").astype(float)
        green = composite.sel(band="B03").astype(float)
        blue = composite.sel(band="B02").astype(float)
        nir = composite.sel(band=nir_band).astype(float)
        
        red_valid = np.sum(~np.isnan(red))
        nir_valid = np.sum(~np.isnan(nir))
        logger.info(f"Extracted bands - Red: {red.shape} ({red_valid} valid), NIR: {nir.shape} ({nir_valid} valid)")
        logger.info(f"Data ranges - Red: [{np.nanmin(red):.2f}, {np.nanmax(red):.2f}], NIR: [{np.nanmin(nir):.2f}, {np.nanmax(nir):.2f}]")
        
        if red_valid == 0 or nir_valid == 0:
            logger.warning(f"No valid Red or NIR data - Red valid: {red_valid}, NIR valid: {nir_valid}")
            return {"status": "failed", "error": f"Insufficient band data: Red={red_valid} valid, NIR={nir_valid} valid"}
        
        result = {"status": "success", "composite_created": True}
        
        # NDVI: (NIR - Red) / (NIR + Red)  
        # Note: Sentinel-2 and Landsat scale DN values 0-10000, so direct calculation is appropriate
        nir_red_denom = nir + red
        
        # Avoid division by zero
        ndvi = np.where(nir_red_denom != 0, (nir - red) / nir_red_denom, np.nan)
        
        # Get statistics
        valid_ndvi_pixels = np.sum(~np.isnan(ndvi))
        mean_ndvi = float(np.nanmean(ndvi))
        std_ndvi = float(np.nanstd(ndvi))
        min_ndvi = float(np.nanmin(ndvi))
        max_ndvi = float(np.nanmax(ndvi))
        
        logger.info(f"NDVI computed - Valid pixels: {valid_ndvi_pixels}, Mean: {mean_ndvi:.4f}, Std: {std_ndvi:.4f}, Range: [{min_ndvi:.4f}, {max_ndvi:.4f}]")
        
        # Warn if NDVI looks suspicious (all zero or all negative suggests calculation issue)
        if mean_ndvi < -0.5:
            logger.warning(f"NDVI suspiciously negative: {mean_ndvi:.4f} - check band scaling")
        elif mean_ndvi > 1.0:
            logger.warning(f"NDVI > 1.0: {mean_ndvi:.4f} - check band scaling (should be -1 to 1)")
        
        if math.isnan(mean_ndvi):
            logger.warning("NDVI is all NaN")
            result["ndvi"] = {"mean": 0.0, "status": "failed", "error": "All NaN", "details": {"valid_pixels": 0}}
        else:
            result["ndvi"] = {"mean": mean_ndvi, "status": "success", "min": min_ndvi, "max": max_ndvi, "std": std_ndvi}
            if return_arrays:
                result["ndvi"]["array"] = np.nan_to_num(ndvi, nan=0.0).tolist()
        

        # NDWI: (Green - NIR) / (Green + NIR)
        green_nir_denom = green + nir
        ndwi = np.where(green_nir_denom != 0, (green - nir) / green_nir_denom, np.nan)
        mean_ndwi = float(np.nanmean(ndwi))
        water_fraction = 0.0
        
        logger.info(f"NDWI computed - Valid pixels: {np.sum(~np.isnan(ndwi))}, Mean: {mean_ndwi:.4f}")
        
        if not math.isnan(mean_ndwi):
            valid_mask = ~np.isnan(ndwi)
            total_valid = np.sum(valid_mask)
            water_pixels = np.sum((ndwi > 0) & valid_mask)
            water_fraction = float(water_pixels / total_valid) if total_valid > 0 else 0.0
        
        result["ndwi"] = {"mean": mean_ndwi, "water_fraction": water_fraction, "status": "success"}
        if return_arrays:
            result["ndwi"]["array"] = np.nan_to_num(ndwi, nan=0.0).tolist()
        
        # RGB for visualization/classification
        result["rgb"] = {
            "shape": [int(red.shape[0]), int(red.shape[1])],
            "composite": [red.values, green.values, blue.values] if return_arrays else None
        }
        
        logger.info(f"Indices computed successfully: NDVI={mean_ndvi:.4f}, NDWI={mean_ndwi:.4f}")
        return result
        
    except Exception as e:
        logger.error(f"Error in compute_optical_indices_from_items: {type(e).__name__}: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}

def calculate_ndvi_from_stac_items_optimized(items: list, bbox: Tuple[float, float, float, float], 
                                            explain: bool = False) -> Dict[str, Any]:
    """
    OPTIMIZED version of NDVI calculation.
    Can piggyback on composite created for other indices if needed.
    """
    result = compute_optical_indices_from_items(items, bbox, return_arrays=explain)
    
    if result.get("status") == "failed":
        return {"status": "failed", "mean_ndvi": 0.0, "error": result.get("error")}
    
    ndvi_data = result.get("ndvi", {})
    response = {
        "mean_ndvi": ndvi_data.get("mean", 0.0),
        "status": ndvi_data.get("status", "success")
    }
    
    if explain and ndvi_data.get("array"):
        response["ndvi_array"] = ndvi_data["array"]
    
    if ndvi_data.get("error"):
        response["error"] = ndvi_data["error"]
    
    return response

def calculate_ndwi_from_stac_items_optimized(items: list, bbox: Tuple[float, float, float, float], 
                                            explain: bool = False) -> Dict[str, Any]:
    """
    OPTIMIZED version of NDWI calculation.
    Can piggyback on composite created for other indices if needed.
    """
    result = compute_optical_indices_from_items(items, bbox, return_arrays=explain)
    
    if result.get("status") == "failed":
        return {"status": "failed", "mean_ndwi": 0.0, "error": result.get("error")}
    
    ndwi_data = result.get("ndwi", {})
    response = {
        "mean_ndwi": ndwi_data.get("mean", 0.0),
        "water_fraction": ndwi_data.get("water_fraction", 0.0),
        "status": ndwi_data.get("status", "success")
    }
    
    if explain and ndwi_data.get("array"):
        response["ndwi_array"] = ndwi_data["array"]
    
    if ndwi_data.get("error"):
        response["error"] = ndwi_data["error"]
    
    return response
