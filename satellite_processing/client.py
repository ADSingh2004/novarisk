import pystac_client
import planetary_computer
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from app.utils.spatial import generate_bbox
from app.core.cache import get_cache, set_cache
import hashlib
import json
import logging
import urllib3
import os

# Suppress SSL warnings if verification is disabled
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Enable demo mode if environment variable is set or if connectivity to Planetary Computer is unavailable
USE_DEMO_MODE = os.getenv("USE_DEMO_MODE", "false").lower() == "true"

# In-memory cache for STAC searches during request lifecycle
_stac_search_cache: Dict[str, List] = {}

def get_stac_client() -> pystac_client.Client:
    """
    Returns a STAC client for Microsoft Planetary Computer.
    Uses anonymous access (no API key required).
    planetary_computer.sign_inplace modifier is optional - works for both authenticated and unauthenticated requests.
    """
    try:
        logger.info("Opening STAC client for Planetary Computer (anonymous access)")
        return pystac_client.Client.open(
            STAC_URL,
            modifier=planetary_computer.sign_inplace
        )
    except Exception as e:
        logger.warning(f"Failed to open STAC client with modifier, trying without modifier: {e}")
        try:
            # Fallback: try without modifier (pure anonymous access)
            return pystac_client.Client.open(STAC_URL)
        except Exception as e2:
            logger.error(f"Failed to open STAC client even without modifier: {e2}")
            raise

def _generate_cache_key(prefix: str, latitude: float, longitude: float, radius_km: float, 
                        days_back: int, reference_time: Optional[datetime]) -> str:
    """
    Generates a deterministic cache key for STAC searches.
    Includes all parameters to ensure cache hits for identical queries.
    """
    end_date = reference_time if reference_time else datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    
    # Truncate to date (not time) for more cache hits across the day
    date_key = f"{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}"
    
    # Create a stable hash
    query_str = f"{prefix}:{latitude:.4f}:{longitude:.4f}:{radius_km}:{date_key}"
    return f"stac_search:{hashlib.md5(query_str.encode()).hexdigest()}"

def _sort_items_by_datetime(items: list) -> list:
    """Sorts STAC items by datetime ascending for deterministic processing."""
    return sorted(items, key=lambda i: i.datetime if i.datetime else datetime.min.replace(tzinfo=None))

def _items_to_dicts(items: list) -> list:
    """Converts STAC Item objects to dictionaries for JSON serialization."""
    try:
        return [item.to_dict() if hasattr(item, 'to_dict') else dict(item) for item in items]
    except Exception as e:
        logger.warning(f"Failed to convert items to dicts: {e}")
        return []

def _dicts_to_items(item_dicts: list) -> list:
    """Converts dictionaries back to STAC Item objects."""
    try:
        from pystac import Item
        return [Item.from_dict(item_dict) if isinstance(item_dict, dict) else item_dict for item_dict in item_dicts]
    except Exception as e:
        logger.warning(f"Failed to convert dicts back to items: {e}")
        return []

def search_sentinel2(latitude: float, longitude: float, radius_km: float, days_back: int = 60, reference_time: Optional[datetime] = None, max_items: int = 10):
    """
    Searches for Sentinel-2 L2A imagery within a bounding box and time range.
    Uses reference_time as the end date if provided, otherwise falls back to utcnow().
    Results are sorted by datetime for deterministic ordering.
    max_items limits results at the API level for performance.
    
    OPTIMIZED: Caches results in Redis to avoid duplicate STAC API calls.
    Returns empty list if search fails (connection errors, SSL issues, etc.)
    """
    # Generate cache key
    cache_key = _generate_cache_key("sentinel2", latitude, longitude, radius_km, days_back, reference_time)
    
    # Check Redis cache first (24-hour TTL)
    cached_data = get_cache(cache_key)
    if cached_data:
        logger.debug(f"Sentinel-2 cache HIT for {latitude}, {longitude}")
        # Convert cached dicts back to Item objects
        items = _dicts_to_items(cached_data)
        if items:
            return items
    
    # If not cached, perform STAC search
    try:
        logger.info(f"Searching Sentinel-2 for lat={latitude}, lon={longitude}, days_back={days_back}")
        client = get_stac_client()
        bbox = generate_bbox(latitude, longitude, radius_km)
        
        end_date = reference_time if reference_time else datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        time_range = f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
        
        search = client.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox,
            datetime=time_range,
            query={"eo:cloud_cover": {"lt": 40}},
            max_items=max_items
        )
        
        items = _sort_items_by_datetime(list(search.items()))
        logger.info(f"Found {len(items)} Sentinel-2 items")
        
        # Cache for 24 hours only if we got results (convert to dicts for JSON serialization)
        if items:
            item_dicts = _items_to_dicts(items)
            set_cache(cache_key, item_dicts, 86400)
        
        return items
    except Exception as e:
        logger.error(f"Sentinel-2 search failed: {type(e).__name__}: {str(e)[:200]}")
        
        # Fallback to mock data for demo/testing when Planetary Computer is unreachable
        if USE_DEMO_MODE or "Failed to resolve" in str(e) or "getaddrinfo failed" in str(e):
            logger.info("Falling back to mock Sentinel-2 data for demo mode")
            try:
                from satellite_processing.mock_stac import generate_mock_sentinel2_items
                return generate_mock_sentinel2_items(latitude, longitude, days_back, num_items=3)
            except Exception as mock_err:
                logger.warning(f"Mock data generation failed: {mock_err}")
        
        return []

def search_landsat(latitude: float, longitude: float, radius_km: float, days_back: int = 90, reference_time: Optional[datetime] = None, max_items: int = 10):
    """
    Searches for Landsat Collection 2 Level-2 imagery (useful for LST/UHI).
    Uses reference_time as the end date if provided, otherwise falls back to utcnow().
    Results are sorted by datetime for deterministic ordering.
    max_items limits results at the API level for performance.
    
    OPTIMIZED: Caches results in Redis to avoid duplicate STAC API calls.
    Returns empty list if search fails (connection errors, SSL issues, etc.)
    """
    # Generate cache key
    cache_key = _generate_cache_key("landsat", latitude, longitude, radius_km, days_back, reference_time)
    
    # Check Redis cache first (24-hour TTL)
    cached_data = get_cache(cache_key)
    if cached_data:
        logger.debug(f"Landsat cache HIT for {latitude}, {longitude}")
        # Convert cached dicts back to Item objects
        items = _dicts_to_items(cached_data)
        if items:
            return items
    
    try:
        logger.info(f"Searching Landsat for lat={latitude}, lon={longitude}, days_back={days_back}")
        client = get_stac_client()
        bbox = generate_bbox(latitude, longitude, radius_km)
        
        end_date = reference_time if reference_time else datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        time_range = f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
        
        search = client.search(
            collections=["landsat-c2-l2"],
            bbox=bbox,
            datetime=time_range,
            query={"eo:cloud_cover": {"lt": 40}},
            max_items=max_items
        )
        
        items = _sort_items_by_datetime(list(search.items()))
        logger.info(f"Found {len(items)} Landsat items")
        
        # Cache for 24 hours only if we got results (convert to dicts for JSON serialization)
        if items:
            item_dicts = _items_to_dicts(items)
            set_cache(cache_key, item_dicts, 86400)
        
        return items
    except Exception as e:
        logger.error(f"Landsat search failed: {type(e).__name__}: {str(e)[:200]}")
        
        # Fallback to mock data for demo/testing when Planetary Computer is unreachable
        if USE_DEMO_MODE or "Failed to resolve" in str(e) or "getaddrinfo failed" in str(e):
            logger.info("Falling back to mock Landsat data for demo mode")
            try:
                from satellite_processing.mock_stac import generate_mock_landsat_items
                return generate_mock_landsat_items(latitude, longitude, days_back, num_items=2)
            except Exception as mock_err:
                logger.warning(f"Mock data generation failed: {mock_err}")
        
        return []

def search_sentinel1(latitude: float, longitude: float, radius_km: float, days_back: int = 30, reference_time: Optional[datetime] = None, max_items: int = 10):
    """
    Searches for Sentinel-1 GRD imagery (SAR) within a bounding box and time range.
    Uses reference_time as the end date if provided, otherwise falls back to utcnow().
    Results are sorted by datetime for deterministic ordering.
    max_items limits results at the API level for performance.
    
    OPTIMIZED: Caches results in Redis to avoid duplicate STAC API calls.
    Returns empty list if search fails (connection errors, SSL issues, etc.)
    """
    # Generate cache key
    cache_key = _generate_cache_key("sentinel1", latitude, longitude, radius_km, days_back, reference_time)
    
    # Check Redis cache first (24-hour TTL)
    cached_data = get_cache(cache_key)
    if cached_data:
        logger.debug(f"Sentinel-1 cache HIT for {latitude}, {longitude}")
        # Convert cached dicts back to Item objects
        items = _dicts_to_items(cached_data)
        if items:
            return items
    
    try:
        logger.info(f"Searching Sentinel-1 for lat={latitude}, lon={longitude}, days_back={days_back}")
        client = get_stac_client()
        bbox = generate_bbox(latitude, longitude, radius_km)
        
        end_date = reference_time if reference_time else datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        time_range = f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
        
        search = client.search(
            collections=["sentinel-1-grd"],
            bbox=bbox,
            datetime=time_range,
            max_items=max_items
        )
        
        items = _sort_items_by_datetime(list(search.items()))
        logger.info(f"Found {len(items)} Sentinel-1 items")
        
        # Cache for 24 hours only if we got results (convert to dicts for JSON serialization)
        if items:
            item_dicts = _items_to_dicts(items)
            set_cache(cache_key, item_dicts, 86400)
        
        return items
    except Exception as e:
        logger.error(f"Sentinel-1 search failed: {type(e).__name__}: {str(e)[:200]}")
        
        # Fallback to mock data for demo/testing when Planetary Computer is unreachable
        if USE_DEMO_MODE or "Failed to resolve" in str(e) or "getaddrinfo failed" in str(e):
            logger.info("Falling back to mock Sentinel-1 data for demo mode")
            try:
                from satellite_processing.mock_stac import generate_mock_sentinel1_items
                return generate_mock_sentinel1_items(latitude, longitude, days_back, num_items=2)
            except Exception as mock_err:
                logger.warning(f"Mock data generation failed: {mock_err}")
        
        return []
