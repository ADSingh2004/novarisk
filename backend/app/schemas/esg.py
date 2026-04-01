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
    water_stress_proxy: float
    heat_island_index: float
    sar_water_area: Optional[float] = None
    sar_water_change: Optional[float] = None
    forest_percentage: Optional[float] = None
    water_percentage: Optional[float] = None
    urban_percentage: Optional[float] = None
    agriculture_percentage: Optional[float] = None
    barren_percentage: Optional[float] = None

class ReportResponse(BaseModel):
    report_url_pdf: str
    report_url_csv: str

class HistoryResponse(BaseModel):
    history: List[Dict[str, Any]]

class ExplainResponse(BaseModel):
    formulas_used: List[str]
    input_band_values: Dict[str, Any]
    step_by_step_calculations: List[str]
    interpretation_logic: str
    classification_map: Optional[List[List[int]]] = None
