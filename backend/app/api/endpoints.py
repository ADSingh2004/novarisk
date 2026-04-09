from fastapi import APIRouter, HTTPException
from app.schemas.esg import AnalyzeRequest, ESGMetricsResponse, ReportResponse, HistoryResponse, FacilityRegisterRequest, FacilityRegisterResponse
from app.db import get_cache_db, set_cache_db
import sys
import os
import uuid
import gc

# Add satellite processing to path so imports work from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from satellite_processing.metrics.deforestation_risk import calculate_deforestation_risk
from satellite_processing.metrics.water_stress_proxy import calculate_water_stress_proxy
from satellite_processing.metrics.urban_heat_island import calculate_urban_heat_island
from satellite_processing.metrics.sar_analytics import verify_deforestation_sar
router = APIRouter()

@router.post("/facility/register", response_model=FacilityRegisterResponse)
async def register_facility(request: FacilityRegisterRequest):
    """
    Registers a facility before analysis.
    Validates coordinates and generates a PostGIS mock point.
    """
    # TODO: Implement actual database insertion later
    new_id = str(uuid.uuid4())
    return FacilityRegisterResponse(
        facility_id=new_id,
        message=f"Facility '{request.name}' registered successfully."
    )

@router.get("/facility/analyze", response_model=ESGMetricsResponse)
async def analyze_facility(latitude: float, longitude: float, radius_km: float = 2.0):
    """
    Analyzes a facility location and returns ESG risk indicators.
    Uses Redis caching to avoid redundant satellite processing.
    """
    import logging
    logger = logging.getLogger(__name__)

    cache_key = f"esg_metrics:{latitude}:{longitude}:{radius_km}"
    
    # 1. Check Postgres Cache
    cached_data = get_cache_db(cache_key)
    if cached_data:
        logger.info(f"Cache HIT for {cache_key}")
        return ESGMetricsResponse(**cached_data)
        
    # 2. If not cached, calculate metrics using satellite pipelines
    try:
        import asyncio
        logger.info(f"Running parallel optical/SAR deforestation sequence for ({latitude}, {longitude})")
        def_risk, sar_conf = await asyncio.gather(
            asyncio.to_thread(calculate_deforestation_risk, latitude, longitude, radius_km),
            asyncio.to_thread(verify_deforestation_sar, latitude, longitude)
        )
        logger.info(f"Deforestation result: {def_risk} | Verification: {sar_conf}")

        logger.info(f"Running water stress proxy for ({latitude}, {longitude})")
        water_risk = calculate_water_stress_proxy(latitude, longitude, radius_km)
        logger.info(f"Water stress result: {water_risk}")

        # UHI uses standard 1km vs 10km comparison
        logger.info(f"Running UHI for ({latitude}, {longitude})")
        uhi_risk = calculate_urban_heat_island(latitude, longitude, facility_radius_km=1.0, rural_radius_km=10.0)
        logger.info(f"UHI result: {uhi_risk}")
        
        # 3. Compile Response
        response_data = {
            "deforestation_risk": def_risk.get("score", 0.0),
            "deforestation_confidence": sar_conf,
            "water_stress_proxy": water_risk.get("score", 0.0),
            "heat_island_index": uhi_risk.get("score", 0.0)
        }
        logger.info(f"Final ESG response: {response_data}")
        
        # 4. Store in cache persistently
        set_cache_db(cache_key, latitude, longitude, radius_km, response_data)
        
        # 5. Erase heavy pipeline data variables to free memory immediately
        del def_risk
        del sar_conf
        del water_risk
        del uhi_risk
        gc.collect()
        
        return ESGMetricsResponse(**response_data)
    except Exception as e:
        logger.error(f"Pipeline error for ({latitude}, {longitude}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import Response

# Add reporting to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from reporting.generator import generate_pdf_report, generate_csv_report

@router.get("/facility/report/pdf")
async def get_report_pdf(latitude: float, longitude: float, radius_km: float = 2.0):
    """Generates and returns a PDF compliance report."""
    # Run analysis first to get the data
    cache_key = f"esg_metrics:{latitude}:{longitude}:{radius_km}"
    cached_data = get_cache_db(cache_key)
    
    if cached_data:
        metrics = cached_data
    else:
        # In a real app we'd await the actual process or separate out logic
        metrics = {
            "deforestation_risk": calculate_deforestation_risk(latitude, longitude, radius_km).get("score", 0),
            "water_stress_proxy": calculate_water_stress_proxy(latitude, longitude, radius_km).get("score", 0),
            "heat_island_index": calculate_urban_heat_island(latitude, longitude).get("score", 0)
        }
    
    pdf_bytes = generate_pdf_report(latitude, longitude, metrics, radius_km)
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=NovaRisk_ESG_Report_{latitude}_{longitude}.pdf"})

@router.get("/facility/report/csv")
async def get_report_csv(latitude: float, longitude: float, radius_km: float = 2.0):
    """Generates and returns a CSV compliance report."""
    cache_key = f"esg_metrics:{latitude}:{longitude}:{radius_km}"
    cached_data = get_cache_db(cache_key)
    
    if cached_data:
        metrics = cached_data
    else:
        metrics = {
            "deforestation_risk": calculate_deforestation_risk(latitude, longitude, radius_km).get("score", 0),
            "water_stress_proxy": calculate_water_stress_proxy(latitude, longitude, radius_km).get("score", 0),
            "heat_island_index": calculate_urban_heat_island(latitude, longitude).get("score", 0)
        }
        
    csv_str = generate_csv_report(latitude, longitude, metrics, radius_km)
    return Response(content=csv_str, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=NovaRisk_ESG_Report_{latitude}_{longitude}.csv"})

@router.get("/facility/history", response_model=HistoryResponse)
async def get_facility_history(latitude: float, longitude: float):
    """
    Returns historical satellite metrics for a facility.
    """
    # TODO: Fetch from database/time-series store
    return HistoryResponse(
        history=[
            {"year": 2021, "deforestation": 1.2, "water_stress": 3.4, "uhi": 1.1},
            {"year": 2022, "deforestation": 2.5, "water_stress": 4.1, "uhi": 1.5},
            {"year": 2023, "deforestation": 3.8, "water_stress": 4.8, "uhi": 2.0},
        ]
    )

from app.schemas.esg import DeforestationRiskResponse
@router.post("/analyze-deforestation", response_model=DeforestationRiskResponse)
async def analyze_deforestation_robust(request: AnalyzeRequest):
    import logging
    logger = logging.getLogger(__name__)
    cache_key = f"deforest_{request.latitude}_{request.longitude}_{request.radius_km}"
    cached_data = get_cache_db(cache_key)
    if cached_data:
        return DeforestationRiskResponse(**cached_data)
        
    try:
        import asyncio
        data = await asyncio.to_thread(calculate_deforestation_risk, request.latitude, request.longitude, request.radius_km)
        
        response = {
            "facility_id": str(uuid.uuid4()),
            "location": {"latitude": request.latitude, "longitude": request.longitude},
            "ndvi_current": data.get("ndvi_current"),
            "ndvi_past": data.get("ndvi_past"),
            "delta_ndvi": data.get("delta_ndvi"),
            "risk_score": data.get("risk_score", 0),
            "risk_category": data.get("risk_category", "Low"),
            "data_mode": data.get("data_mode", "satellite"),
            "confidence_score": data.get("confidence_score"),
            "timestamp": data.get("timestamp", ""),
            "visual_layers": data.get("visual_layers", {})
        }
        
        set_cache_db(cache_key, request.latitude, request.longitude, request.radius_km, response)
        
        # Erase heavy pipeline data variables to free memory immediately
        del data
        gc.collect()
        
        return DeforestationRiskResponse(**response)
    except Exception as e:
        logger.error(f"Deforestation pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/facility/{id}/risk-score")
async def get_facility_risk_score(id: str):
    return {"facility_id": id, "risk_score": 42.5, "status": "active"}

@router.get("/facility/{id}/history", response_model=HistoryResponse)
async def get_facility_specific_history(id: str):
    return HistoryResponse(
        history=[
            {"year": 2021, "deforestation": 1.1},
            {"year": 2022, "deforestation": 2.3},
            {"year": 2023, "deforestation": 3.4},
        ]
    )

