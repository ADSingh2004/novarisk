from datetime import datetime, timedelta

import shapely.geometry
from pystac_client import Client


def search_sentinel2_scenes(
    lat: float, 
    lon: float, 
    start_date: str, 
    end_date: str, 
    max_cloud_cover: int = 20
):
    """
    Searches for Sentinel-2 Level-2A data using the Earth Search STAC API.
    
    Args:
        lat (float): Latitude of the point of interest.
        lon (float): Longitude of the point of interest.
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.
        max_cloud_cover (int): Maximum allowable cloud cover percentage (0-100).

    Returns:
        dict: A GeoJSON-like dictionary of found STAC items.
    """
    
    # Earth Search STAC API URL (AWS Public Dataset)
    STAC_API_URL = "https://earth-search.aws.element84.com/v1"

    # Define the Area of Interest (AOI) as a small point buffer or just the point
    # STAC clients typically take a bbox or intersects geometry. 
    # Let's create a small buffer around the point to ensure we catch covering tiles.
    # Note: 0.01 degrees is roughly 1km at the equator.
    point = shapely.geometry.Point(lon, lat)
    intersects_geojson = point.__geo_interface__
    # Using the point directly in intersects
    
    print(f"Searching Sentinel-2 data for Point({lon}, {lat})")
    print(f"Time Range: {start_date} to {end_date}")
    print(f"Max Cloud Cover: {max_cloud_cover}%")

    try:
        client = Client.open(STAC_API_URL)

        search = client.search(
            collections=["sentinel-2-l2a"],
            intersects=intersects_geojson,
            datetime=f"{start_date}/{end_date}",
            query={"eo:cloud_cover": {"lt": max_cloud_cover}},
        )

        items = search.item_collection()
        print(f"Found {len(items)} scenes.")
        
        results = []
        for item in items:
            print(f"- {item.id} | Date: {item.datetime} | Clouds: {item.properties['eo:cloud_cover']}%")
            thumb_asset = item.assets.get("thumbnail")
            results.append({
                "id": item.id,
                "date": str(item.datetime),
                "cloud_cover": item.properties['eo:cloud_cover'],
                "thumbnail": thumb_asset.href if thumb_asset else None,
                # Choose the visual asset or bands based on your needs
                "assets": {key: asset.href for key, asset in item.assets.items()}
            })
            
        return results

    except Exception as e:
        print(f"Error during search: {e}")
        return []

if __name__ == "__main__":
    # Example Usage:
    # Paris coordinates
    LAT = 48.8566
    LON = 2.3522
    
    # Last 30 days
    END = datetime.now()
    START = END - timedelta(days=30)
    
    search_sentinel2_scenes(
        lat=LAT, 
        lon=LON, 
        start_date=START.strftime("%Y-%m-%d"), 
        end_date=END.strftime("%Y-%m-%d"),
        max_cloud_cover=30
    )
