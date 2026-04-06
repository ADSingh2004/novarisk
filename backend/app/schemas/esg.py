from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

class AnalyzeRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float

class FacilityRegisterRequest(BaseModel):
    name: str
    latitude: float
    longitude: float

class FacilityRegisterResponse(BaseModel):
    facility_id: str
    message: str


class ESGMetricsResponse(BaseModel):
    deforestation_risk: float
    deforestation_confidence: Optional[str] = None
    water_stress_proxy: float
    heat_island_index: float

class ReportResponse(BaseModel):
    report_url_pdf: str
    report_url_csv: str

class HistoryResponse(BaseModel):
    history: List[Dict[str, Any]]

class LocationSchema(BaseModel):
    latitude: float
    longitude: float

class VisualLayers(BaseModel):
    ndvi_map_url: Optional[str] = None
    change_map_url: Optional[str] = None

class DeforestationRiskResponse(BaseModel):
    facility_id: str
    location: LocationSchema
    ndvi_current: Optional[float] = None
    ndvi_past: Optional[float] = None
    delta_ndvi: Optional[float] = None
    risk_score: float
    risk_category: str  # "Low", "Moderate", "High"
    data_mode: str  # "satellite" or "predicted"
    confidence_score: Optional[float] = None
    timestamp: str = ""
    visual_layers: Optional[VisualLayers] = None

