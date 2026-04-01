from fastapi import APIRouter, HTTPException
import sys
import os

# Add app parent to path so we can import from app package
_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from schemas.esg import AnalyzeRequest, ESGMetricsResponse, ReportResponse, HistoryResponse, FacilityRegisterRequest, FacilityRegisterResponse, ExplainResponse
from core.cache import get_cache, set_cache
import uuid
import asyncio
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import functools

logger = logging.getLogger(__name__)

# Timing decorator for profiling
def _timer(name: str):
    """Decorator to time function execution."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000  # ms
            logger.debug(f"[TIMER] {name}: {elapsed:.1f}ms")
            return result
        return wrapper
    return decorator

# Add satellite processing to path so imports work from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from satellite_processing.metrics.deforestation_risk import calculate_deforestation_risk
from satellite_processing.metrics.water_stress_fusion import calculate_fused_water_stress_proxy
from satellite_processing.metrics.urban_heat_island import calculate_urban_heat_island
from satellite_processing.client import search_sentinel2
from satellite_processing.ai.land_cover_classifier import calculate_land_cover_from_stac_items
from satellite_processing.indices.multi_index import calculate_ndvi_from_stac_items_optimized, calculate_ndwi_from_stac_items_optimized, compute_optical_indices_from_items
from utils.spatial import generate_bbox

router = APIRouter()

# Shared thread pool for parallel metric computation
_executor = ThreadPoolExecutor(max_workers=4)

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


def _calc_deforestation(latitude, longitude, radius_km, reference_time):
    """Wrapper for thread-safe deforestation calculation."""
    try:
        result = calculate_deforestation_risk(latitude, longitude, radius_km, reference_time=reference_time)
        logger.info(f"Deforestation result: {result}")
        return result
    except Exception as e:
        logger.error(f"Deforestation calculation failed: {type(e).__name__}: {e}", exc_info=True)
        return {"score": 0.0}

def _calc_water_stress(latitude, longitude, radius_km, reference_time):
    """Wrapper for thread-safe water stress calculation."""
    try:
        result = calculate_fused_water_stress_proxy(latitude, longitude, radius_km, reference_time=reference_time)
        logger.info(f"Water stress result: {result}")
        return result
    except Exception as e:
        logger.error(f"Water stress calculation failed: {type(e).__name__}: {e}", exc_info=True)
        return {"score": 0.0, "sar_water_area": 0.0, "sar_water_change": 0.0}

def _calc_uhi(latitude, longitude, reference_time):
    """Wrapper for thread-safe UHI calculation."""
    try:
        result = calculate_urban_heat_island(latitude, longitude, facility_radius_km=1.0, rural_radius_km=10.0, reference_time=reference_time)
        logger.info(f"UHI result: {result}")
        return result
    except Exception as e:
        logger.error(f"UHI calculation failed: {type(e).__name__}: {e}", exc_info=True)
        return {"score": 0.0}

def _calc_land_cover_and_explain(latitude, longitude, radius_km, reference_time):
    """
    OPTIMIZED: Combined land cover + explainability in a single thread.
    Computes NDVI and NDWI from a SINGLE stacked cube to avoid redundant tile downloads.
    """
    try:
        bbox = generate_bbox(latitude, longitude, radius_km)
        items = search_sentinel2(latitude, longitude, radius_km, days_back=30, reference_time=reference_time, max_items=5)
        
        # Land cover classification
        land_cover_res = {"status": "failed"}
        try:
            land_cover_res = calculate_land_cover_from_stac_items(items, bbox)
        except Exception as e:
            logger.error(f"Land cover classifier failed: {e}")
        
        # OPTIMIZED: Explainability - compute BOTH NDVI and NDWI from single composite
        explain_data = None
        try:
            optical_indices_result = compute_optical_indices_from_items(items, bbox, satellite="sentinel2", return_arrays=True)
            
            if optical_indices_result.get("status") == "success":
                # Store only JSON-serializable values (numpy arrays excluded from cache)
                explain_data = {
                    "classification_map": land_cover_res.get("classification_map"),
                    "mean_ndvi": float(optical_indices_result.get("ndvi", {}).get("mean", 0.0)),
                    "mean_ndwi": float(optical_indices_result.get("ndwi", {}).get("mean", 0.0)),
                }
        except Exception as e:
            logger.error(f"Explainability computation failed: {e}")
        
        return land_cover_res, explain_data
    except Exception as e:
        logger.error(f"Land cover + explain pipeline failed: {e}")
        return {"status": "failed"}, None


@router.get("/facility/analyze", response_model=ESGMetricsResponse)
async def analyze_facility(latitude: float, longitude: float, radius_km: float = 5.0, recalculate: bool = False):
    """
    Analyzes a facility location and returns ESG risk indicators.
    Uses Redis caching to avoid redundant satellite processing unless recalculate is True.
    Pins a single reference_time per request to ensure deterministic metric calculations.
    
    OPTIMIZED: 
    - All metrics run in PARALLEL via thread pool
    - STAC searches are cached in Redis (24-hour TTL)
    - Multiple indices computed from single stacked cube
    - Detailed timing instrumentation for bottleneck identification
    """
    cache_key = f"esg_metrics:{latitude}:{longitude}:{radius_km}"
    
    # 1. Check Redis Cache
    if not recalculate:
        cached_data = get_cache(cache_key)
        if cached_data:
            logger.info(f"Cache HIT for {latitude}, {longitude}")
            return ESGMetricsResponse(**cached_data)
    
    logger.info(f"Cache MISS for {latitude}, {longitude} - computing metrics")
    
    # 2. If not cached, calculate ALL metrics in parallel
    reference_time = datetime.utcnow()
    start_time = time.time()
    start_log = {}
    
    loop = asyncio.get_event_loop()
    
    # Launch all 4 tasks concurrently in thread pool
    logger.info(f"Starting parallel metric computation ({recalculate=})")
    
    deforestation_future = loop.run_in_executor(
        _executor, _calc_deforestation, latitude, longitude, radius_km, reference_time
    )
    water_future = loop.run_in_executor(
        _executor, _calc_water_stress, latitude, longitude, radius_km, reference_time
    )
    uhi_future = loop.run_in_executor(
        _executor, _calc_uhi, latitude, longitude, reference_time
    )
    landcover_future = loop.run_in_executor(
        _executor, _calc_land_cover_and_explain, latitude, longitude, radius_km, reference_time
    )
    
    # Wait for all to complete concurrently
    def_risk, water_risk, uhi_risk, (land_cover_res, explain_data) = await asyncio.gather(
        deforestation_future, water_future, uhi_future, landcover_future
    )
    
    total_elapsed = time.time() - start_time
    logger.info(f"All metrics computed in {total_elapsed:.2f}s (PARALLEL)")
    logger.info(f"  Deforestation: {def_risk.get('score', 0.0)}")
    logger.info(f"  Water Stress: {water_risk.get('score', 0.0)}")
    logger.info(f"  UHI: {uhi_risk.get('score', 0.0)}")
    logger.info(f"  Land Cover: {land_cover_res.get('status', 'failed')}")
    
    # 3. Build response
    response_data = {
        "deforestation_risk": def_risk.get("score", 0.0),
        "water_stress_proxy": water_risk.get("score", 0.0),
        "heat_island_index": uhi_risk.get("score", 0.0),
        "sar_water_area": water_risk.get("sar_water_area", 0.0),
        "sar_water_change": water_risk.get("sar_water_change", 0.0),
    }
    
    # Add land cover percentages if available
    if land_cover_res and land_cover_res.get("status") == "success":
        response_data.update(land_cover_res.get("percentages", {}))
    
    # 4. Store in cache (expire in 24 hours = 86400 seconds)
    set_cache(cache_key, response_data, 86400)
    
    # 5. Store explainability cache (already computed in parallel, no extra cost)
    if explain_data:
        explain_cache_key = f"esg_explain:{latitude}:{longitude}:{radius_km}"
        set_cache(explain_cache_key, explain_data, 86400)
        
    return ESGMetricsResponse(**response_data)

@router.get("/facility/explain", response_model=ExplainResponse)
async def explain_facility(latitude: float, longitude: float, radius_km: float = 5.0):
    """
    Returns formatted explainability data for the metrics of a facility.
    Requires /facility/analyze to have been called recently to populate the cache.
    """
    explain_cache_key = f"esg_explain:{latitude}:{longitude}:{radius_km}"
    explain_data = get_cache(explain_cache_key)
    
    if not explain_data:
        raise HTTPException(status_code=404, detail="Explainability data not found. Please call /facility/analyze first.")
        
    return ExplainResponse(
        formulas_used=[
            "NDVI = (NIR - Red) / (NIR + Red)",
            "NDWI = (Green - NIR) / (Green + NIR)",
            "AI Land Cover = U-Net Segmentation with MobileNetV3 Encoder"
        ],
        input_band_values={
            "mean_ndvi": explain_data.get("mean_ndvi"),
            "mean_ndwi": explain_data.get("mean_ndwi"),
            "ndvi_array": explain_data.get("ndvi_array"),
            "ndwi_array": explain_data.get("ndwi_array")
        },
        step_by_step_calculations=[
            "1. Fetched Sentinel-2 STAC items for the bounding box.",
            "2. Computed median composite over the time dimension to remove clouds.",
            "3. Calculated NDVI using B04 (Red) and B08 (NIR).",
            "4. Calculated NDWI using B03 (Green) and B08 (NIR).",
            "5. Passed RGB bands (B04, B03, B02) into the lightweight AI classifier.",
            "6. Extracted raw 2D classification map and aggregated class percentages."
        ],
        interpretation_logic="The raw NDVI/NDWI arrays represent the respective indices at each pixel. The classification map represents the land cover class for each pixel (0: Forest, 1: Water, 2: Urban, 3: Agriculture, 4: Barren).",
        classification_map=explain_data.get("classification_map")
    )

from fastapi.responses import Response

# Add reporting to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from reporting.generator import generate_pdf_report, generate_csv_report, generate_ai_land_features_pdf

@router.get("/facility/report/pdf")
async def get_report_pdf(latitude: float, longitude: float, radius_km: float = 5.0):
    """Generates and returns a PDF compliance report."""
    # Run analysis first to get the data
    cache_key = f"esg_metrics:{latitude}:{longitude}:{radius_km}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        metrics = cached_data
    else:
        # In a real app we'd await the actual process or separate out logic
        water_risk = calculate_fused_water_stress_proxy(latitude, longitude, radius_km)
        metrics = {
            "deforestation_risk": calculate_deforestation_risk(latitude, longitude, radius_km).get("score", 0),
            "water_stress_proxy": water_risk.get("score", 0),
            "heat_island_index": calculate_urban_heat_island(latitude, longitude).get("score", 0),
            "sar_water_area": water_risk.get("sar_water_area", 0.0),
            "sar_water_change": water_risk.get("sar_water_change", 0.0),
        }
    
    pdf_bytes = generate_pdf_report(latitude, longitude, metrics)
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=NovaRisk_ESG_Report_{latitude}_{longitude}.pdf"})

@router.get("/facility/report/csv")
async def get_report_csv(latitude: float, longitude: float, radius_km: float = 5.0):
    """Generates and returns a CSV compliance report."""
    cache_key = f"esg_metrics:{latitude}:{longitude}:{radius_km}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        metrics = cached_data
    else:
        water_risk = calculate_fused_water_stress_proxy(latitude, longitude, radius_km)
        metrics = {
            "deforestation_risk": calculate_deforestation_risk(latitude, longitude, radius_km).get("score", 0),
            "water_stress_proxy": water_risk.get("score", 0),
            "heat_island_index": calculate_urban_heat_island(latitude, longitude).get("score", 0),
            "sar_water_area": water_risk.get("sar_water_area", 0.0),
            "sar_water_change": water_risk.get("sar_water_change", 0.0),
        }
        
    csv_str = generate_csv_report(latitude, longitude, metrics)
    return Response(content=csv_str, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=NovaRisk_ESG_Report_{latitude}_{longitude}.csv"})

@router.get("/facility/report/ai-land-features-pdf")
async def get_ai_land_features_pdf(latitude: float, longitude: float, radius_km: float = 5.0):
    """
    Generates and returns a detailed PDF report for AI-predicted land cover features.
    Includes classification breakdown, class descriptions, and methodology.
    
    This endpoint requires analysis to have been run previously (cache hit).
    If no cached analysis exists, it will trigger a new analysis first.
    """
    # Try to get cached metrics first
    cache_key = f"esg_metrics:{latitude}:{longitude}:{radius_km}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        # Use cached land cover percentages
        land_cover_data = {
            "forest_percentage": cached_data.get("forest_percentage", 0.0),
            "water_percentage": cached_data.get("water_percentage", 0.0),
            "urban_percentage": cached_data.get("urban_percentage", 0.0),
            "agriculture_percentage": cached_data.get("agriculture_percentage", 0.0),
            "barren_percentage": cached_data.get("barren_percentage", 0.0),
        }
    else:
        # Trigger analysis first
        logger.info(f"No cached data for AI land feature PDF - triggering analysis")
        analysis_result = await analyze_facility(latitude, longitude, radius_km, recalculate=False)
        land_cover_data = {
            "forest_percentage": analysis_result.forest_percentage,
            "water_percentage": analysis_result.water_percentage,
            "urban_percentage": analysis_result.urban_percentage,
            "agriculture_percentage": analysis_result.agriculture_percentage,
            "barren_percentage": analysis_result.barren_percentage,
        }
    
    pdf_bytes = generate_ai_land_features_pdf(latitude, longitude, land_cover_data)
    return Response(
        content=pdf_bytes, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename=NovaRisk_AI_LandCover_{latitude}_{longitude}.pdf"}
    )


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
