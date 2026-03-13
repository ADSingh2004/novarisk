from pydantic import BaseModel
from typing import Optional, List, Dict, Any

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
