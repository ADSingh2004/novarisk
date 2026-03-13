from typing import Tuple, Dict, Any

def generate_bbox(latitude: float, longitude: float, radius_km: float) -> Tuple[float, float, float, float]:
    """
    Generates a bounding box around a given coordinate with a specified radius.
    Returns (min_lon, min_lat, max_lon, max_lat).
    
    Note: A rough approximation using 1 degree ~ 111 km.
    For production, consider pyproj or geopy distance calculations.
    """
    lat_delta = radius_km / 111.0
    # Longitude delta depends on latitude
    import math
    lon_delta = radius_km / (111.0 * math.cos(math.radians(latitude)))
    
    min_lat = latitude - lat_delta
    max_lat = latitude + lat_delta
    min_lon = longitude - lon_delta
    max_lon = longitude + lon_delta
    
    return (min_lon, min_lat, max_lon, max_lat)

def create_buffer_polygon(latitude: float, longitude: float, radius_km: float) -> Dict[str, Any]:
    """
    Creates a GeoJSON Polygon representing a buffer around a facility.
    Note: A rough approximation using bounding box for STAC queries.
    """
    min_lon, min_lat, max_lon, max_lat = generate_bbox(latitude, longitude, radius_km)
    return {
        "type": "Polygon",
        "coordinates": [[
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat]
        ]]
    }

def latlon_to_projected_crs(latitude: float, longitude: float, target_crs: str = "EPSG:3857") -> Tuple[float, float]:
    """
    Transforms lat/lon to a projected CRS.
    Requires pyproj for actual implementation.
    """
    # Placeholder for actual pyproj transformation if needed later
    return (longitude, latitude)

def clip_raster_to_bbox(dataset, bbox: Tuple[float, float, float, float]):
    """
    Uses rasterio windowed reading to clip a raster directly during read.
    bbox is (min_lon, min_lat, max_lon, max_lat) in the CRS of the dataset.
    Returns the windowed data and the updated transform.
    """
    from rasterio.windows import from_bounds
    
    # Create a window from the bounding box
    window = from_bounds(*bbox, transform=dataset.transform)
    
    # Read the data for that window
    # Bound the window to the dataset's actual dimensions
    window = window.intersection(dataset.window(*dataset.bounds))
    
    data = dataset.read(window=window)
    window_transform = dataset.window_transform(window)
    
    return data, window_transform
