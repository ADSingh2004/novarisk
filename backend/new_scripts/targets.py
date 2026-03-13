from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class TargetSite:
    site_id: str
    lat: float
    lon: float
    site_radius_km: float = 5.0
    facility_id: str | None = None
    name: str | None = None
    sector: str | None = None
    country: str | None = None
    aoi_type: str | None = None
    metrics_enabled: List[str] = field(default_factory=list)
    assets: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "TargetSite":
        known_fields = {
            "site_id",
            "facility_id",
            "name",
            "sector",
            "country",
            "aoi_type",
            "lat",
            "lon",
            "site_radius_km",
            "metrics_enabled",
        }
        assets = {k: v for k, v in raw.items() if k not in known_fields}
        return cls(
            site_id=raw["site_id"],
            facility_id=raw.get("facility_id"),
            name=raw.get("name"),
            sector=raw.get("sector"),
            country=raw.get("country"),
            aoi_type=raw.get("aoi_type"),
            lat=float(raw["lat"]),
            lon=float(raw["lon"]),
            site_radius_km=float(raw.get("site_radius_km", 5.0)),
            metrics_enabled=list(raw.get("metrics_enabled", [])),
            assets=assets,
        )

    @property
    def workspace(self) -> Path:
        return Path("data/working") / self.site_id

    def ensure_workspace(self) -> Path:
        path = self.workspace
        path.mkdir(parents=True, exist_ok=True)
        return path

    def bounding_box(self, scale_factor: float = 1.0) -> tuple[float, float, float, float]:
        radius_deg_lat = (self.site_radius_km * scale_factor) / 111.0
        cos_lat = math.cos(math.radians(self.lat))
        cos_lat = cos_lat if abs(cos_lat) > 1e-6 else 1e-6
        radius_deg_lon = (self.site_radius_km * scale_factor) / (111.0 * cos_lat)
        min_lon = self.lon - radius_deg_lon
        max_lon = self.lon + radius_deg_lon
        min_lat = self.lat - radius_deg_lat
        max_lat = self.lat + radius_deg_lat
        return (min_lon, min_lat, max_lon, max_lat)


def load_target_sites(config_path: str = "data/reference/target_sites.json") -> List[TargetSite]:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return [TargetSite.from_dict(site) for site in payload.get("sites", [])]


def ensure_site_workspaces(sites: List[TargetSite]) -> None:
    for site in sites:
        site.ensure_workspace()
