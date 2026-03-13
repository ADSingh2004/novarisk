from __future__ import annotations

from datetime import datetime, timedelta

import shapely.geometry
from pystac_client import Client


def search_sentinel1_scenes(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    instrument_mode: str = "IW",
    max_items: int = 20,
) -> list[dict]:
    stac_url = "https://earth-search.aws.element84.com/v1"
    point = shapely.geometry.Point(lon, lat)

    try:
        client = Client.open(stac_url)
        search = client.search(
            collections=["sentinel-1-grd"],
            intersects=point.__geo_interface__,
            datetime=f"{start_date}/{end_date}",
            query={"sar:instrument_mode": {"eq": instrument_mode}},
            max_items=max_items,
        )

        items = []
        for item in search.items():
            items.append(
                {
                    "id": item.id,
                    "date": str(item.datetime),
                    "orbit_state": item.properties.get("sat:orbit_state"),
                    "instrument_mode": item.properties.get("sar:instrument_mode"),
                    "assets": {k: v.href for k, v in item.assets.items()},
                }
            )
        print(f"Found {len(items)} Sentinel-1 scenes for ({lat}, {lon}).")
        return items
    except Exception as exc:
        print(f"Error during Sentinel-1 search: {exc}")
        return []


if __name__ == "__main__":
    end = datetime.utcnow()
    start = end - timedelta(days=30)
    data = search_sentinel1_scenes(28.6139, 77.209, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    print(f"Found {len(data)} Sentinel-1 scenes")
