"""
Mock STAC data generator for local testing without Planetary Computer connectivity.
Provides realistic dummy satellite data for ESG metric calculations.
"""
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List
import logging

logger = logging.getLogger(__name__)

# Mock STAC Item class that mimics pystac.Item
class MockSTACItem:
    def __init__(self, item_id: str, datetime_val: datetime, assets: Dict[str, Any]):
        self.id = item_id
        self.datetime = datetime_val
        self.assets = assets
        self.bbox = [139.5, 35.5, 140.0, 36.0]  # Default bbox around Tokyo
        self.geometry = {
            "type": "Polygon",
            "coordinates": [[[139.5, 35.5], [140.0, 35.5], [140.0, 36.0], [139.5, 36.0], [139.5, 35.5]]]
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "datetime": self.datetime.isoformat(),
            "bbox": self.bbox,
            "geometry": self.geometry,
            "properties": {"datetime": self.datetime.isoformat()},
            "assets": self.assets
        }
    
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'MockSTACItem':
        """Reconstruct from dictionary."""
        dt = datetime.fromisoformat(d["properties"]["datetime"]) if isinstance(d["properties"]["datetime"], str) else d["properties"]["datetime"]
        item = MockSTACItem(d["id"], dt, d.get("assets", {}))
        item.bbox = d.get("bbox", item.bbox)
        item.geometry = d.get("geometry", item.geometry)
        return item


def generate_mock_sentinel2_items(latitude: float, longitude: float, days_back: int = 30, num_items: int = 3) -> List[MockSTACItem]:
    """
    Generates mock Sentinel-2 L2A STAC items with realistic data.
    Returns items with HTTP references to mock COG files.
    """
    items = []
    base_date = datetime.utcnow()
    
    for i in range(num_items):
        date = base_date - timedelta(days=i * 10)
        item_id = f"S2A_MSIL2A_{date.strftime('%Y%m%d')}_{i:03d}"
        
        # Mock asset URLs (these won't actually be fetched, but simulate the structure)
        assets = {
            "B02": {"href": f"https://example.com/S2/B02_{i}.tif"},  # Blue
            "B03": {"href": f"https://example.com/S2/B03_{i}.tif"},  # Green
            "B04": {"href": f"https://example.com/S2/B04_{i}.tif"},  # Red
            "B08": {"href": f"https://example.com/S2/B08_{i}.tif"},  # NIR
            "B11": {"href": f"https://example.com/S2/B11_{i}.tif"},  # SWIR
            "SCL": {"href": f"https://example.com/S2/SCL_{i}.tif"},  # Scene classification
        }
        
        item = MockSTACItem(item_id, date, assets)
        items.append(item)
    
    logger.info(f"Generated {len(items)} mock Sentinel-2 items")
    return items


def generate_mock_landsat_items(latitude: float, longitude: float, days_back: int = 60, num_items: int = 2) -> List[MockSTACItem]:
    """
    Generates mock Landsat Collection 2 Level-2 STAC items.
    """
    items = []
    base_date = datetime.utcnow()
    
    for i in range(num_items):
        date = base_date - timedelta(days=i * 30)
        item_id = f"LC08_L2SP_{date.strftime('%Y%m%d')}_{i:03d}"
        
        assets = {
            "B02": {"href": f"https://example.com/LANDSAT/B02_{i}.tif"},  # Blue
            "B03": {"href": f"https://example.com/LANDSAT/B03_{i}.tif"},  # Green
            "B04": {"href": f"https://example.com/LANDSAT/B04_{i}.tif"},  # Red
            "B05": {"href": f"https://example.com/LANDSAT/B05_{i}.tif"},  # NIR
            "B10": {"href": f"https://example.com/LANDSAT/B10_{i}.tif"},  # TIRS1 (thermal)
            "QA_PIXEL": {"href": f"https://example.com/LANDSAT/QA_{i}.tif"},
        }
        
        item = MockSTACItem(item_id, date, assets)
        items.append(item)
    
    logger.info(f"Generated {len(items)} mock Landsat items")
    return items


def generate_mock_sentinel1_items(latitude: float, longitude: float, days_back: int = 30, num_items: int = 2) -> List[MockSTACItem]:
    """
    Generates mock Sentinel-1 GRD STAC items (SAR data).
    """
    items = []
    base_date = datetime.utcnow()
    
    for i in range(num_items):
        date = base_date - timedelta(days=i * 15)
        item_id = f"S1A_IW_GRDH_{date.strftime('%Y%m%d')}_{i:03d}"
        
        assets = {
            "VV": {"href": f"https://example.com/S1/VV_{i}.tif"},  # VV polarization
            "VH": {"href": f"https://example.com/S1/VH_{i}.tif"},  # VH polarization
        }
        
        item = MockSTACItem(item_id, date, assets)
        items.append(item)
    
    logger.info(f"Generated {len(items)} mock Sentinel-1 items")
    return items


# Test/demo mock data for common locations
DEMO_LOCATIONS = {
    "tokyo": {"latitude": 35.6762, "longitude": 139.6503, "description": "Tokyo, Japan"},
    "amazon": {"latitude": -3.4653, "longitude": -62.2159, "description": "Amazon Rainforest, Brazil"},
    "aral_sea": {"latitude": 45.1481, "longitude": 59.5756, "description": "Aral Sea Region"},
}
