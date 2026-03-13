import pystac_client
import planetary_computer
from datetime import datetime, timedelta
from app.utils.spatial import generate_bbox

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

def get_stac_client() -> pystac_client.Client:
    """Returns an authenticated STAC client for Microsoft Planetary Computer."""
    return pystac_client.Client.open(
        STAC_URL,
        modifier=planetary_computer.sign_inplace
    )

def search_sentinel2(latitude: float, longitude: float, radius_km: float, days_back: int = 30):
    """
    Searches for Sentinel-2 L2A imagery within a bounding box and time range.
    """
    client = get_stac_client()
    bbox = generate_bbox(latitude, longitude, radius_km)
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    time_range = f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
    
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=time_range,
        query={"eo:cloud_cover": {"lt": 20}} # Less than 20% cloud cover
    )
    
    items = list(search.items())
    return items

def search_landsat(latitude: float, longitude: float, radius_km: float, days_back: int = 60):
    """
    Searches for Landsat Collection 2 Level-2 imagery (useful for LST/UHI).
    """
    client = get_stac_client()
    bbox = generate_bbox(latitude, longitude, radius_km)
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    time_range = f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
    
    search = client.search(
        collections=["landsat-c2-l2"],
        bbox=bbox,
        datetime=time_range,
        query={"eo:cloud_cover": {"lt": 20}}
    )
    
    items = list(search.items())
    return items
