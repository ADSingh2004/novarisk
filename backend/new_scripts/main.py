from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from api.audit import log_event
from api.auth import authenticate_credentials, create_access_token, require_auth
from api.compliance import build_esrs_rows, create_compliance_zip, write_compliance_csv
from api.db import check_db_status
from api.reference_validation import validate_site_against_references
from api.reporting import generate_site_report_pdf
from api.s3_storage import s3_delivery_enabled, upload_compliance_pack
from api.site_reference_paths import assert_reference_paths_exist, resolve_site_reference_paths
from api.validation import compare_against_reference
from ingestion.analytics import calculate_deforestation_detail
from ingestion.era5_ingestion import prepare_era5_dataset
from ingestion.generate_dummy_inputs import generate_dummy_water_inputs
from ingestion.generate_dummy_references import generate_dummy_reference_layers
from ingestion.generate_dummy_tifs import generate_dummy_pair
from ingestion.uhi_analytics import calculate_uhi_intensity
from ingestion.water_analytics import calculate_water_body_change_detail


class AnalyzeSiteRequest(BaseModel):
    site_id: str | None = None
    region: str | None = None
    sector: str | None = None
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    date_range: str
    before_tif: str | None = None
    after_tif: str | None = None
    water_before_optical_tif: str | None = None
    water_after_optical_tif: str | None = None
    water_before_sar_tif: str | None = None
    water_after_sar_tif: str | None = None
    era5_netcdf_path: str | None = None


class ValidationRequest(BaseModel):
    predicted: list[float]
    reference: list[float]


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class ReferenceValidationRequest(BaseModel):
    site_id: str | None = None
    after_tif: str | None = None
    worldcover_tif: str | None = None
    water_after_optical_tif: str | None = None
    water_after_sar_tif: str | None = None
    jrc_water_tif: str | None = None
    ndvi_threshold: float = 0.4
    mndwi_threshold: float = 0.1
    sar_db_threshold: float = -17.0
    vegetation_classes: list[int] | None = None


class ReportRequest(BaseModel):
    site_id: str | None = None
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    date_range: str


class CompliancePackRequest(BaseModel):
    site_id: str
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    date_range: str
    region: str | None = None
    sector: str | None = None


class DashboardSummaryRequest(BaseModel):
    region: str | None = None
    sector: str | None = None
    period: str | None = None


class ProfileSettingsPayload(BaseModel):
    display_name: str = "Orbit Capital ESG Desk"
    email: str = "esgdesk@orbitcapital.example"
    notification_window: str = "Weekly summary"
    compliance_email: str = "compliance@orbitcapital.example"
    sector_focus: list[str] = Field(default_factory=lambda: ["Municipal", "Heavy Industry", "Supply Chain"])


app = FastAPI(title="NovaRisk ESG API", version="0.1.0")

_DASHBOARD_CACHE: dict[str, dict[str, object]] = {}
_DASHBOARD_CACHE_TTL_SECONDS = 60.0
_ANALYSIS_CACHE: dict[str, dict[str, Any]] = {}
_ANALYSIS_CACHE_TTL_SECONDS = 300.0
_CACHED_METRIC_LATENCY_MS: list[float] = []
_METRIC_COST_EUR: list[float] = []
_MAX_STATS_SAMPLES = 500
_RISK_SCORE_MIN = 0.0
_RISK_SCORE_MAX = 100.0

SHOWCASE_SITES = [
    {
        "site_id": "uk-urban",
        "name": "Manchester Civic Campus",
        "lat": 53.4808,
        "lon": -2.2426,
        "country": "UK",
        "site_radius_km": 8,
        "region": "emea",
        "sector_key": "municipal",
    },
    {
        "site_id": "ebro-basin",
        "name": "Ebro Basin - Zaragoza",
        "lat": 41.6488,
        "lon": -0.8891,
        "country": "ES",
        "site_radius_km": 10,
        "region": "emea",
        "sector_key": "industry",
    },
    {
        "site_id": "para-forest",
        "name": "Pará Supply Chain Concession",
        "lat": -5.5319,
        "lon": -52.6333,
        "country": "BR",
        "site_radius_km": 20,
        "region": "americas",
        "sector_key": "supply",
    },
]

_PROFILE_SETTINGS_PATH = Path("data/profile_settings.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _site_date_range(period: str | None) -> str:
    year = (period or "2025").strip()
    if not (year.isdigit() and len(year) == 4):
        year = "2025"
    return f"{year}-01-01/{year}-12-31"


def _normalize_period(period: str | None) -> str:
    value = (period or "2025-12").strip()
    if len(value) == 7 and value[4] == "-":
        year, month = value[:4], value[5:7]
        if year.isdigit() and month.isdigit() and 1 <= int(month) <= 12:
            return value
    if len(value) == 4 and value.isdigit():
        return f"{value}-12"
    return "2025-12"


def _period_year(period: str | None) -> str:
    normalized = _normalize_period(period)
    return normalized[:4]


def _previous_period(period: str) -> str:
    dt = datetime.strptime(period, "%Y-%m")
    if dt.month == 1:
        return f"{dt.year - 1}-12"
    return f"{dt.year}-{dt.month - 1:02d}"


def _month_periods(from_period: str, to_period: str, max_months: int = 24) -> list[str]:
    start = datetime.strptime(from_period, "%Y-%m")
    end = datetime.strptime(to_period, "%Y-%m")
    if start > end:
        raise ValueError("from must be less than or equal to to")

    periods: list[str] = []
    cursor = start
    while cursor <= end:
        periods.append(cursor.strftime("%Y-%m"))
        if len(periods) > max_months:
            raise ValueError(f"Requested range exceeds {max_months} months")
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return periods


def _reference_config_path() -> Path:
    return Path("data/reference/target_sites.json")


def _load_target_sites() -> list[dict[str, Any]]:
    path = _reference_config_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        sites = payload.get("sites", [])
        return [site for site in sites if isinstance(site, dict)]
    except Exception:
        return []


def _parse_date_range(date_range: str) -> tuple[datetime, datetime]:
    parts = date_range.split("/")
    if len(parts) != 2:
        raise ValueError("date_range must be in 'YYYY-MM-DD/YYYY-MM-DD' format")
    start = datetime.strptime(parts[0], "%Y-%m-%d")
    end = datetime.strptime(parts[1], "%Y-%m-%d")
    if start > end:
        raise ValueError("date_range start must be before end")
    if end > datetime.utcnow():
        raise ValueError("date_range cannot be in the future")
    return start, end


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _risk_band(score: float) -> str:
    bounded = _clamp(float(score), _RISK_SCORE_MIN, _RISK_SCORE_MAX)
    if bounded >= 80.0:
        return "critical"
    if bounded >= 50.0:
        return "high"
    if bounded >= 20.0:
        return "moderate"
    return "low"


def _risk_scale_definition() -> dict[str, object]:
    return {
        "range": "0-100",
        "bands": [
            {"label": "low", "min": 0, "max": 20},
            {"label": "moderate", "min": 20, "max": 50},
            {"label": "high", "min": 50, "max": 80},
            {"label": "critical", "min": 80, "max": 100},
        ],
    }


def _push_sample(samples: list[float], value: float) -> None:
    samples.append(value)
    if len(samples) > _MAX_STATS_SAMPLES:
        del samples[: len(samples) - _MAX_STATS_SAMPLES]


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * q))
    return float(ordered[idx])


def _estimate_run_cost_eur(used_dummy_assets: bool, runtime_seconds: float) -> float:
    base = 0.006 if used_dummy_assets else 0.018
    variable = 0.0015 * max(0.0, runtime_seconds)
    return round(base + variable, 5)


def _analysis_cache_key(site_id: str, period: str) -> str:
    return f"{site_id}|{period}"


def _site_from_target(site: dict[str, Any]) -> dict[str, object]:
    return {
        "site_id": site.get("site_id"),
        "name": site.get("name") or site.get("site_id"),
        "lat": float(site.get("lat", 0.0)),
        "lon": float(site.get("lon", 0.0)),
        "country": site.get("country"),
        "site_radius_km": float(site.get("site_radius_km", 10.0)),
        "region": (site.get("region") or "emea").lower(),
        "sector_key": (site.get("sector") or "general").lower().replace(" ", "-"),
    }


def _site_manifest(site_id: str, configured_site: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if configured_site and configured_site.get("ingestion_manifest"):
        manifest_path = Path(str(configured_site["ingestion_manifest"]))
    else:
        manifest_path = Path("data/working") / site_id / "ingestion_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data["_manifest_path"] = str(manifest_path)
        data["_manifest_mtime"] = datetime.utcfromtimestamp(manifest_path.stat().st_mtime).isoformat() + "Z"
        return data
    except Exception:
        return None


def _resolve_showcase_site(site_id: str) -> dict[str, object]:
    normalized = site_id.strip().lower()
    for site in SHOWCASE_SITES:
        if str(site["site_id"]).lower() == normalized:
            return site
    for target_site in _load_target_sites():
        if str(target_site.get("site_id", "")).strip().lower() == normalized:
            return _site_from_target(target_site)
    raise HTTPException(status_code=404, detail=f"Unknown site_id '{site_id}'")


def _normalize_metric(metric: str) -> str:
    key = metric.strip().lower()
    aliases = {
        "landuse": "landuse",
        "deforestation": "landuse",
        "forest": "landuse",
        "water": "water",
        "water_change": "water",
        "uhi": "uhi",
        "heat": "uhi",
    }
    normalized = aliases.get(key)
    if not normalized:
        raise HTTPException(status_code=400, detail="metric must be one of: landuse, water, uhi")
    return normalized


def _metric_snapshot(analysis: dict, metric: str) -> dict[str, object]:
    if metric == "landuse":
        data = analysis["metrics"]["deforestation"]
        score = float(data["risk_score"])
        return {
            "value": float(data["vegetation_change_pct"]),
            "unit": "pct_change",
            "score_0_100": score,
            "risk_band": _risk_band(score),
            "confidence": float(data.get("confidence", 0.84)),
            "method_version": str(data.get("method_version", "landuse-v0.1-rulebased")),
            "quality_flags": data.get("quality_flags", []),
        }
    if metric == "water":
        data = analysis["metrics"]["water_change"]
        score = float(data["risk_score"])
        return {
            "value": float(data["water_change_pct"]),
            "unit": "pct_change",
            "score_0_100": score,
            "risk_band": _risk_band(score),
            "confidence": float(data.get("confidence", 0.81)),
            "method_version": str(data.get("method_version", "water-v0.1-rulebased")),
            "quality_flags": data.get("quality_flags", []),
        }

    data = analysis["metrics"]["uhi"]
    score = float(data["risk_score"])
    return {
        "value": float(data["uhi_intensity_c"]),
        "unit": "degC",
        "score_0_100": score,
        "risk_band": _risk_band(score),
        "confidence": float(data.get("confidence", 0.78)),
        "method_version": str(data.get("method_version", "uhi-v0.1-proxy")),
        "quality_flags": data.get("quality_flags", []),
    }


def _analyze_showcase_site(site: dict[str, object], period: str) -> dict:
    analysis, _ = _get_analysis_for_period(site, period)
    return analysis


def _normalize_filter(value: str | None) -> str:
    if not value:
        return "all"
    value = value.strip().lower()
    return value or "all"


def _dashboard_cache_key(filters: DashboardSummaryRequest) -> str:
    return "|".join([
        _normalize_filter(filters.region),
        _normalize_filter(filters.sector),
        filters.period.strip() if isinstance(filters.period, str) and filters.period.strip() else "2025",
    ])


def _filter_showcase_sites(filters: DashboardSummaryRequest) -> list[dict[str, object]]:
    region = _normalize_filter(filters.region)
    sector = _normalize_filter(filters.sector)

    filtered = [
        site
        for site in SHOWCASE_SITES
        if (region == "all" or site["region"] == region) and (sector == "all" or site["sector_key"] == sector)
    ]
    return filtered


def _default_profile_settings() -> dict:
    return ProfileSettingsPayload().dict()


def _load_profile_settings() -> dict:
    if _PROFILE_SETTINGS_PATH.exists():
        try:
            data = json.loads(_PROFILE_SETTINGS_PATH.read_text(encoding="utf-8"))
            return ProfileSettingsPayload(**data).dict()
        except Exception:
            return _default_profile_settings()
    return _default_profile_settings()


def _save_profile_settings(data: dict) -> dict:
    payload = ProfileSettingsPayload(**data).dict()
    _PROFILE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PROFILE_SETTINGS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _get_analysis_for_period(site: dict[str, object], period: str) -> tuple[dict[str, Any], bool]:
    site_id = str(site["site_id"])
    cache_key = _analysis_cache_key(site_id, period)
    now = time.time()
    cache_entry = _ANALYSIS_CACHE.get(cache_key)
    if cache_entry and isinstance(cache_entry.get("timestamp"), float):
        if now - float(cache_entry["timestamp"]) < _ANALYSIS_CACHE_TTL_SECONDS:
            return cache_entry["payload"], True

    analysis = _run_site_analysis(
        AnalyzeSiteRequest(
            site_id=site_id,
            lat=float(site["lat"]),
            lon=float(site["lon"]),
            date_range=_site_date_range(_period_year(period)),
        )
    )
    _ANALYSIS_CACHE[cache_key] = {"timestamp": now, "payload": analysis}
    return analysis, False


@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


@app.get("/health")
@app.get("/api/v1/health")
def health() -> dict:
    db_status = check_db_status()
    overall_status = "ok" if db_status.get("connected") else "degraded"
    return {"status": overall_status, "api": "ok", "db": db_status}


@app.post("/api/v1/auth/login")
def login(payload: AuthLoginRequest) -> dict:
    if not authenticate_credentials(payload.username, payload.password):
        log_event("auth_failed", {"username": payload.username})
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(payload.username)
    log_event("auth_success", {"username": payload.username})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/v1/performance")
def performance_metrics(_auth: dict = Depends(require_auth)) -> dict:
    p80_cached_ms = round(_percentile(_CACHED_METRIC_LATENCY_MS, 0.8), 3) if _CACHED_METRIC_LATENCY_MS else 0.0
    avg_cost_eur = round(sum(_METRIC_COST_EUR) / len(_METRIC_COST_EUR), 5) if _METRIC_COST_EUR else 0.0
    return {
        "status": "ok",
        "cached_metrics_p80_ms": p80_cached_ms,
        "cached_read_target_ms": 500,
        "cached_read_slo_met": p80_cached_ms <= 500.0 if _CACHED_METRIC_LATENCY_MS else None,
        "avg_metric_run_cost_eur": avg_cost_eur,
        "cost_target_eur": 0.05,
        "cost_target_met": avg_cost_eur <= 0.05 if _METRIC_COST_EUR else None,
        "samples": {
            "cached_latency": len(_CACHED_METRIC_LATENCY_MS),
            "cost": len(_METRIC_COST_EUR),
        },
    }


@app.get("/sites")
@app.get("/api/v1/sites")
def list_sites(_auth: dict = Depends(require_auth)) -> dict:
    target_sites = _load_target_sites()
    source_sites = [_site_from_target(site) for site in target_sites] if target_sites else SHOWCASE_SITES
    sites = [
        {
            "site_id": site["site_id"],
            "name": site["name"],
            "lat": site["lat"],
            "lon": site["lon"],
            "country": site.get("country"),
            "region": site["region"],
            "sector": site["sector_key"],
            "site_radius_km": site.get("site_radius_km", 10),
        }
        for site in source_sites
    ]
    return {"status": "ok", "count": len(sites), "sites": sites}


@app.get("/metrics")
@app.get("/api/v1/metrics")
def get_metric(
    site_id: str,
    metric: str,
    period: str | None = None,
    _auth: dict = Depends(require_auth),
) -> dict:
    request_start = time.perf_counter()
    normalized_period = _normalize_period(period)
    metric_key = _normalize_metric(metric)
    site = _resolve_showcase_site(site_id)

    current_analysis, current_cache_hit = _get_analysis_for_period(site, normalized_period)
    previous_period = _previous_period(normalized_period)
    previous_analysis, _ = _get_analysis_for_period(site, previous_period)

    current = _metric_snapshot(current_analysis, metric_key)
    previous = _metric_snapshot(previous_analysis, metric_key)
    delta = float(current["value"]) - float(previous["value"])
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"

    metric_details = current_analysis["metrics"]["deforestation" if metric_key == "landuse" else "water_change" if metric_key == "water" else "uhi"]
    elapsed_ms = (time.perf_counter() - request_start) * 1000.0
    if current_cache_hit:
        _push_sample(_CACHED_METRIC_LATENCY_MS, elapsed_ms)

    estimated_cost_eur = float(current_analysis.get("meta", {}).get("estimated_cost_eur", 0.0))

    response = {
        "status": "ok",
        "site_id": str(site["site_id"]),
        "metric": metric_key,
        "period": normalized_period,
        **current,
        "risk_scale": _risk_scale_definition(),
        "trend": {
            "previous_period": previous_period,
            "delta": round(delta, 3),
            "direction": direction,
        },
        "lineage_ref": f"lineage:{site['site_id']}:{metric_key}:{normalized_period}",
        "quality_flags": current.get("quality_flags", []),
        "hotspots": metric_details.get("hotspots", []),
        "layers": metric_details.get("layers", {}),
        "cached": current_cache_hit,
        "cost_estimate_eur": estimated_cost_eur,
    }
    if estimated_cost_eur > 0:
        log_event(
            "metric_served",
            {
                "site_id": str(site["site_id"]),
                "metric": metric_key,
                "period": normalized_period,
                "cached": current_cache_hit,
                "latency_ms": round(elapsed_ms, 2),
                "estimated_cost_eur": estimated_cost_eur,
            },
        )
    return response


@app.get("/metrics/timeseries")
@app.get("/api/v1/metrics/timeseries")
def get_metric_timeseries(
    site_id: str,
    metric: str,
    from_period: str = Query(..., alias="from"),
    to_period: str = Query(..., alias="to"),
    _auth: dict = Depends(require_auth),
) -> dict:
    metric_key = _normalize_metric(metric)
    site = _resolve_showcase_site(site_id)

    try:
        periods = _month_periods(_normalize_period(from_period), _normalize_period(to_period))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    series = []
    for period_value in periods:
        analysis, _ = _get_analysis_for_period(site, period_value)
        snapshot = _metric_snapshot(analysis, metric_key)
        series.append(
            {
                "period": period_value,
                "value": snapshot["value"],
                "unit": snapshot["unit"],
                "score_0_100": snapshot["score_0_100"],
                "risk_band": snapshot.get("risk_band"),
                "confidence": snapshot["confidence"],
                "quality_flags": snapshot.get("quality_flags", []),
            }
        )

    temporal_warnings: list[str] = []
    deltas: list[float] = []
    for idx in range(1, len(series)):
        previous_value = float(series[idx - 1]["value"])
        current_value = float(series[idx]["value"])
        deltas.append(abs(current_value - previous_value))
    if deltas and max(deltas) > 60:
        temporal_warnings.append("large_monthly_jump_detected")

    return {
        "status": "ok",
        "site_id": str(site["site_id"]),
        "metric": metric_key,
        "from": periods[0],
        "to": periods[-1],
        "points": len(series),
        "series": series,
        "method_version": series and _metric_snapshot(_get_analysis_for_period(site, periods[-1])[0], metric_key)["method_version"],
        "lineage_ref": f"lineage:{site['site_id']}:{metric_key}:{periods[0]}:{periods[-1]}",
        "qa_warnings": temporal_warnings,
    }


@app.get("/compliance/report")
@app.get("/api/v1/compliance/report")
def compliance_report(
    site_id: str,
    period: str | None = None,
    _auth: dict = Depends(require_auth),
):
    normalized_period = _normalize_period(period)
    site = _resolve_showcase_site(site_id)
    payload = CompliancePackRequest(
        site_id=str(site["site_id"]),
        lat=float(site["lat"]),
        lon=float(site["lon"]),
        date_range=_site_date_range(_period_year(normalized_period)),
        region=str(site["region"]),
        sector=str(site["sector_key"]),
    )
    return compliance_pack_site(payload)


@app.get("/lineage")
@app.get("/api/v1/lineage")
def metric_lineage(
    site_id: str,
    metric: str,
    period: str | None = None,
    _auth: dict = Depends(require_auth),
) -> dict:
    normalized_period = _normalize_period(period)
    metric_key = _normalize_metric(metric)
    site = _resolve_showcase_site(site_id)
    configured_site = resolve_site_reference_paths(site_id, float(site["lat"]), float(site["lon"]))
    manifest = _site_manifest(site_id, configured_site)

    lineage_sources = {
        "landuse": ["Sentinel-2 L2A", "ESA WorldCover"],
        "water": ["Sentinel-2 L2A", "Sentinel-1 GRD", "JRC Global Surface Water"],
        "uhi": ["ERA5-Land", "Sentinel-2 built-up proxy/OSM urban mask"],
    }
    assumptions = {
        "landuse": [
            "Vegetation change is a proxy for land-use pressure.",
            "Cloud and seasonal effects are reduced via compositing.",
        ],
        "water": [
            "Water extent is derived from optical and SAR proxy masks.",
            "Indicator is a stress proxy and not direct consumption.",
        ],
        "uhi": [
            "UHI exposure uses ERA5-Land air temperature differentials.",
            "This is a proxy and not direct land-surface temperature.",
        ],
    }

    source_scene_ids = {
        "sentinel2_before": (manifest or {}).get("sentinel2", {}).get("before", {}).get("id"),
        "sentinel2_after": (manifest or {}).get("sentinel2", {}).get("after", {}).get("id"),
        "sentinel1_before": (manifest or {}).get("sentinel1", {}).get("before", {}).get("id"),
        "sentinel1_after": (manifest or {}).get("sentinel1", {}).get("after", {}).get("id"),
    }

    return {
        "status": "ok",
        "site_id": str(site["site_id"]),
        "metric": metric_key,
        "period": normalized_period,
        "lineage_ref": f"lineage:{site['site_id']}:{metric_key}:{normalized_period}",
        "sources": lineage_sources[metric_key],
        "processing_pipeline": [
            "acquisition",
            "preprocessing",
            "feature_extraction",
            "metric_computation",
            "scoring",
        ],
        "method_version": f"{metric_key}-v0.2",
        "assumptions": assumptions[metric_key],
        "source_scene_ids": source_scene_ids,
        "processing_timestamp": datetime.utcnow().isoformat() + "Z",
        "ingestion_manifest": manifest.get("_manifest_path") if manifest else None,
        "ingestion_manifest_updated_at": manifest.get("_manifest_mtime") if manifest else None,
    }


def _resolve_site_input_paths(payload: AnalyzeSiteRequest) -> dict[str, Any]:
    configured_site = resolve_site_reference_paths(payload.site_id, payload.lat, payload.lon)
    manifest = _site_manifest(payload.site_id or "", configured_site)

    if payload.before_tif and payload.after_tif:
        before_tif = payload.before_tif
        after_tif = payload.after_tif
    elif configured_site and configured_site.get("before_tif") and configured_site.get("after_tif"):
        before_tif = str(configured_site["before_tif"])
        after_tif = str(configured_site["after_tif"])
    elif manifest:
        composites = manifest.get("sentinel2_composites", {}).get("red_nir", {})
        before_tif = composites.get("before")
        after_tif = composites.get("after")
    else:
        before_tif, after_tif = generate_dummy_pair()

    used_dummy_deforestation = not (before_tif and after_tif and Path(str(before_tif)).exists() and Path(str(after_tif)).exists())
    if used_dummy_deforestation:
        before_tif, after_tif = generate_dummy_pair()

    if (
        payload.water_before_optical_tif
        and payload.water_after_optical_tif
        and payload.water_before_sar_tif
        and payload.water_after_sar_tif
    ):
        water_inputs = {
            "before_optical_tif": payload.water_before_optical_tif,
            "after_optical_tif": payload.water_after_optical_tif,
            "before_sar_tif": payload.water_before_sar_tif,
            "after_sar_tif": payload.water_after_sar_tif,
        }
    elif configured_site:
        water_inputs = {
            "before_optical_tif": configured_site.get("water_before_optical_tif"),
            "after_optical_tif": configured_site.get("water_after_optical_tif"),
            "before_sar_tif": configured_site.get("water_before_sar_tif"),
            "after_sar_tif": configured_site.get("water_after_sar_tif"),
        }
    elif manifest:
        optical = manifest.get("sentinel2_composites", {}).get("green_swir", {})
        sar = manifest.get("sentinel1_stacks", {}).get("vv_vh", {})
        water_inputs = {
            "before_optical_tif": optical.get("before"),
            "after_optical_tif": optical.get("after"),
            "before_sar_tif": sar.get("before"),
            "after_sar_tif": sar.get("after"),
        }
    else:
        water_inputs = generate_dummy_water_inputs()

    water_paths_exist = all(water_inputs.get(key) for key in ["before_optical_tif", "after_optical_tif", "before_sar_tif", "after_sar_tif"]) and all(
        Path(str(v)).exists() for v in water_inputs.values()
    )
    used_dummy_water = not water_paths_exist
    if used_dummy_water:
        water_inputs = generate_dummy_water_inputs()

    era5_path = payload.era5_netcdf_path
    if not era5_path and configured_site and configured_site.get("era5_netcdf"):
        era5_path = str(configured_site.get("era5_netcdf"))
    if not era5_path and manifest and manifest.get("era5"):
        era5_path = str(manifest.get("era5"))
    if not era5_path or not Path(era5_path).exists():
        era5_path = prepare_era5_dataset()
        used_dummy_uhi = True
    else:
        used_dummy_uhi = False

    return {
        "site_config": configured_site,
        "manifest": manifest,
        "before_tif": str(before_tif),
        "after_tif": str(after_tif),
        "water_inputs": {
            "before_optical_tif": str(water_inputs["before_optical_tif"]),
            "after_optical_tif": str(water_inputs["after_optical_tif"]),
            "before_sar_tif": str(water_inputs["before_sar_tif"]),
            "after_sar_tif": str(water_inputs["after_sar_tif"]),
        },
        "era5_path": str(era5_path),
        "used_dummy_assets": bool(used_dummy_deforestation or used_dummy_water or used_dummy_uhi),
    }


def _run_site_analysis(payload: AnalyzeSiteRequest) -> dict:
    start = time.perf_counter()
    _parse_date_range(payload.date_range)

    resolved = _resolve_site_input_paths(payload)
    configured_site = resolved.get("site_config")
    if configured_site and configured_site.get("lat") is not None and configured_site.get("lon") is not None:
        lat_delta = abs(float(configured_site.get("lat")) - payload.lat)
        lon_delta = abs(float(configured_site.get("lon")) - payload.lon)
        if lat_delta > 0.5 or lon_delta > 0.5:
            raise ValueError("Input coordinates are inconsistent with configured site geometry")

    deforestation_detail = calculate_deforestation_detail(resolved["before_tif"], resolved["after_tif"])
    water_results = calculate_water_body_change_detail(
        resolved["water_inputs"]["before_optical_tif"],
        resolved["water_inputs"]["after_optical_tif"],
        resolved["water_inputs"]["before_sar_tif"],
        resolved["water_inputs"]["after_sar_tif"],
    )
    uhi_results = calculate_uhi_intensity(resolved["era5_path"])

    deforestation_change_pct = float(deforestation_detail["vegetation_change_pct"])
    deforestation_risk_score = max(0.0, -deforestation_change_pct)
    water_risk_score = float(water_results["risk_score"])
    uhi_risk_score = float(uhi_results["risk_score"])

    water_consistency_gap = float(water_results.get("sensor_consistency_gap_pct", 0.0))
    deforestation_quality_flags: list[str] = []
    water_quality_flags: list[str] = []
    uhi_quality_flags: list[str] = []

    if resolved["used_dummy_assets"]:
        deforestation_quality_flags.append("dummy_asset_fallback")
        water_quality_flags.append("dummy_asset_fallback")
        uhi_quality_flags.append("dummy_asset_fallback")
    if water_consistency_gap > 35.0:
        water_quality_flags.append("cross_sensor_divergence")

    deforestation_confidence = _clamp(0.88 - (0.15 if resolved["used_dummy_assets"] else 0.0), 0.4, 0.99)
    water_confidence = _clamp(0.86 - min(water_consistency_gap / 100.0, 0.35) - (0.12 if resolved["used_dummy_assets"] else 0.0), 0.35, 0.99)
    uhi_confidence = _clamp(0.8 - (0.1 if resolved["used_dummy_assets"] else 0.0), 0.4, 0.99)

    runtime_seconds = time.perf_counter() - start
    run_cost_eur = _estimate_run_cost_eur(resolved["used_dummy_assets"], runtime_seconds)
    _push_sample(_METRIC_COST_EUR, run_cost_eur)

    manifest = resolved.get("manifest")
    return {
        "site": {
            "site_id": payload.site_id,
            "lat": payload.lat,
            "lon": payload.lon,
            "date_range": payload.date_range,
        },
        "inputs": {
            "deforestation_before_tif": resolved["before_tif"],
            "deforestation_after_tif": resolved["after_tif"],
            "water": resolved["water_inputs"],
            "era5_netcdf_path": resolved["era5_path"],
        },
        "lineage": {
            "manifest_path": manifest.get("_manifest_path") if manifest else None,
            "manifest_updated_at": manifest.get("_manifest_mtime") if manifest else None,
            "source_scene_ids": {
                "sentinel2_before": (manifest or {}).get("sentinel2", {}).get("before", {}).get("id"),
                "sentinel2_after": (manifest or {}).get("sentinel2", {}).get("after", {}).get("id"),
                "sentinel1_before": (manifest or {}).get("sentinel1", {}).get("before", {}).get("id"),
                "sentinel1_after": (manifest or {}).get("sentinel1", {}).get("after", {}).get("id"),
            },
        },
        "metrics": {
            "deforestation": {
                "vegetation_change_pct": round(deforestation_change_pct, 3),
                "vegetation_before_pct": round(float(deforestation_detail["vegetation_before_pct"]), 3),
                "vegetation_after_pct": round(float(deforestation_detail["vegetation_after_pct"]), 3),
                "hectares_lost_proxy": round(float(deforestation_detail["hectares_lost_proxy"]), 3),
                "risk_score": round(deforestation_risk_score, 3),
                "risk_band": _risk_band(deforestation_risk_score),
                "confidence": round(deforestation_confidence, 3),
                "quality_flags": deforestation_quality_flags,
                "hotspots": deforestation_detail.get("hotspots", []),
                "layers": deforestation_detail.get("layers", {}),
                "method_version": "landuse-v0.2-rulebased-hotspot",
            },
            "water_change": {
                "water_before_pct": round(float(water_results["water_before_pct"]), 3),
                "water_after_pct": round(float(water_results["water_after_pct"]), 3),
                "water_change_pct": round(float(water_results["water_change_pct"]), 3),
                "risk_score": round(water_risk_score, 3),
                "risk_band": _risk_band(water_risk_score),
                "sensor_consistency_gap_pct": round(water_consistency_gap, 3),
                "confidence": round(water_confidence, 3),
                "quality_flags": water_quality_flags,
                "hotspots": water_results.get("hotspots", []),
                "layers": water_results.get("layers", {}),
                "method_version": "water-v0.2-rulebased-hotspot",
            },
            "uhi": {
                "temperature_mean_c": round(float(uhi_results["temperature_mean_c"]), 3),
                "urban_proxy_c": round(float(uhi_results["urban_proxy_c"]), 3),
                "rural_proxy_c": round(float(uhi_results["rural_proxy_c"]), 3),
                "uhi_intensity_c": round(float(uhi_results["uhi_intensity_c"]), 3),
                "risk_score": round(uhi_risk_score, 3),
                "risk_band": _risk_band(uhi_risk_score),
                "confidence": round(uhi_confidence, 3),
                "quality_flags": uhi_quality_flags,
                "method_version": "uhi-v0.2-proxy-era5",
            },
        },
        "meta": {
            "used_dummy_assets": resolved["used_dummy_assets"],
            "estimated_cost_eur": run_cost_eur,
            "runtime_seconds": round(runtime_seconds, 4),
            "processing_timestamp": datetime.utcnow().isoformat() + "Z",
        },
        "status": "ok",
    }


@app.post("/analyze/site")
@app.post("/api/v1/analyze/site")
def analyze_site(payload: AnalyzeSiteRequest, _auth: dict = Depends(require_auth)) -> dict:
    try:
        result = _run_site_analysis(payload)
        log_event("analyze_site", {"lat": payload.lat, "lon": payload.lon, "date_range": payload.date_range})
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/validate/metrics")
@app.post("/api/v1/validate/metrics")
def validate_metrics(payload: ValidationRequest) -> dict:
    try:
        result = compare_against_reference(payload.predicted, payload.reference)
        return {"status": "ok", "validation": result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/validate/reference")
@app.post("/api/v1/validate/reference")
def validate_reference(payload: ReferenceValidationRequest, _auth: dict = Depends(require_auth)) -> dict:
    try:
        configured_site = resolve_site_reference_paths(payload.site_id)
        if configured_site:
            assert_reference_paths_exist(configured_site)

        if payload.after_tif:
            after_tif = payload.after_tif
        elif configured_site and configured_site.get("after_tif"):
            after_tif = str(configured_site["after_tif"])
        else:
            _, after_tif = generate_dummy_pair()

        if payload.water_after_optical_tif and payload.water_after_sar_tif:
            water_after_optical_tif = payload.water_after_optical_tif
            water_after_sar_tif = payload.water_after_sar_tif
        elif configured_site and configured_site.get("water_after_optical_tif") and configured_site.get("water_after_sar_tif"):
            water_after_optical_tif = str(configured_site["water_after_optical_tif"])
            water_after_sar_tif = str(configured_site["water_after_sar_tif"])
        else:
            water_dummy_inputs = generate_dummy_water_inputs()
            water_after_optical_tif = water_dummy_inputs["after_optical_tif"]
            water_after_sar_tif = water_dummy_inputs["after_sar_tif"]

        if payload.worldcover_tif and payload.jrc_water_tif:
            worldcover_tif = payload.worldcover_tif
            jrc_water_tif = payload.jrc_water_tif
        elif configured_site and configured_site.get("worldcover_tif") and configured_site.get("jrc_water_tif"):
            worldcover_tif = str(configured_site["worldcover_tif"])
            jrc_water_tif = str(configured_site["jrc_water_tif"])
        else:
            reference_paths = generate_dummy_reference_layers(
                after_tif=after_tif,
                water_after_optical_tif=water_after_optical_tif,
                water_after_sar_tif=water_after_sar_tif,
            )
            worldcover_tif = reference_paths["worldcover_tif"]
            jrc_water_tif = reference_paths["jrc_water_tif"]

        validation_result = validate_site_against_references(
            after_tif=after_tif,
            worldcover_tif=worldcover_tif,
            water_after_optical_tif=water_after_optical_tif,
            water_after_sar_tif=water_after_sar_tif,
            jrc_reference_tif=jrc_water_tif,
            ndvi_threshold=payload.ndvi_threshold,
            mndwi_threshold=payload.mndwi_threshold,
            sar_db_threshold=payload.sar_db_threshold,
            vegetation_classes=payload.vegetation_classes,
        )

        return {
            "status": "ok",
            "site_id": payload.site_id,
            "inputs": {
                "after_tif": after_tif,
                "worldcover_tif": worldcover_tif,
                "water_after_optical_tif": water_after_optical_tif,
                "water_after_sar_tif": water_after_sar_tif,
                "jrc_water_tif": jrc_water_tif,
            },
            "validation": validation_result,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/report/site")
@app.post("/api/v1/report/site")
def report_site(payload: ReportRequest, _auth: dict = Depends(require_auth)) -> dict:
    try:
        analysis = _run_site_analysis(
            AnalyzeSiteRequest(lat=payload.lat, lon=payload.lon, date_range=payload.date_range)
        )

        configured_site = resolve_site_reference_paths(payload.site_id, payload.lat, payload.lon)
        reference_validation: dict | None = None

        if configured_site:
            assert_reference_paths_exist(configured_site)
            reference_validation = validate_site_against_references(
                after_tif=str(configured_site["after_tif"]),
                worldcover_tif=str(configured_site["worldcover_tif"]),
                water_after_optical_tif=str(configured_site["water_after_optical_tif"]),
                water_after_sar_tif=str(configured_site["water_after_sar_tif"]),
                jrc_reference_tif=str(configured_site["jrc_water_tif"]),
            )
        else:
            reference_paths = generate_dummy_reference_layers(
                after_tif=analysis["inputs"]["deforestation_after_tif"],
                water_after_optical_tif=analysis["inputs"]["water"]["after_optical_tif"],
                water_after_sar_tif=analysis["inputs"]["water"]["after_sar_tif"],
            )
            reference_validation = validate_site_against_references(
                after_tif=analysis["inputs"]["deforestation_after_tif"],
                worldcover_tif=reference_paths["worldcover_tif"],
                water_after_optical_tif=analysis["inputs"]["water"]["after_optical_tif"],
                water_after_sar_tif=analysis["inputs"]["water"]["after_sar_tif"],
                jrc_reference_tif=reference_paths["jrc_water_tif"],
            )

        analysis["metrics"]["reference_validation"] = reference_validation
        pdf_path = generate_site_report_pdf(analysis)
        log_event("report_site", {"site_id": payload.site_id, "report_path": pdf_path})
        return {
            "status": "ok",
            "report_path": pdf_path,
            "site": analysis["site"],
            "site_id": payload.site_id,
            "metrics": analysis["metrics"],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/dashboard/summary")
def dashboard_summary(
    payload: DashboardSummaryRequest | None = None,
    _auth: dict = Depends(require_auth),
) -> dict:
    filters = payload or DashboardSummaryRequest()
    cache_key = _dashboard_cache_key(filters)
    entry = _DASHBOARD_CACHE.get(cache_key)
    now = time.time()
    if entry and isinstance(entry.get("timestamp"), float) and now - float(entry["timestamp"]) < _DASHBOARD_CACHE_TTL_SECONDS:
        return entry["payload"]  # type: ignore[return-value]

    showcase_sites = _filter_showcase_sites(filters)
    if not showcase_sites:
        response_payload = {"status": "ok", "filters": filters.dict(), "sites": []}
        _DASHBOARD_CACHE[cache_key] = {"timestamp": now, "payload": response_payload}
        log_event("dashboard_summary", {"sites": [], "filters": filters.dict()})
        return response_payload

    rows = []
    for site in showcase_sites:
        analysis = _run_site_analysis(
            AnalyzeSiteRequest(
                site_id=site["site_id"],
                lat=site["lat"],
                lon=site["lon"],
                date_range=_site_date_range(filters.period),
            )
        )
        site_meta = {
            **analysis["site"],
            "site_id": site["site_id"],
            "region": site["region"],
            "sector": site["sector_key"],
        }
        rows.append({"site_id": site["site_id"], "site": site_meta, "metrics": analysis["metrics"]})

    response_payload = {"status": "ok", "filters": filters.dict(), "sites": rows}
    _DASHBOARD_CACHE[cache_key] = {"timestamp": now, "payload": response_payload}

    log_event(
        "dashboard_summary",
        {"sites": [site["site_id"] for site in showcase_sites], "filters": filters.dict()},
    )
    return response_payload


@app.get("/api/v1/profile")
def get_profile_settings(_auth: dict = Depends(require_auth)) -> dict:
    profile = _load_profile_settings()
    log_event("profile_read", {"display_name": profile.get("display_name")})
    return {"status": "ok", "profile": profile}


@app.put("/api/v1/profile")
def update_profile_settings(payload: ProfileSettingsPayload, _auth: dict = Depends(require_auth)) -> dict:
    profile = _save_profile_settings(payload.dict())
    log_event("profile_updated", {"display_name": profile.get("display_name")})
    return {"status": "ok", "profile": profile}


@app.post("/api/v1/compliance-pack/site")
def compliance_pack_site(
    payload: CompliancePackRequest,
    _auth: dict = Depends(require_auth),
):
    try:
        report_payload = ReportRequest(
            site_id=payload.site_id,
            lat=payload.lat,
            lon=payload.lon,
            date_range=payload.date_range,
        )
        report_result = report_site(report_payload)

        site_obj = _resolve_showcase_site(payload.site_id)
        period_year = payload.date_range.split("/")[1][:4] if "/" in payload.date_range else payload.date_range[:4]
        current_period = _normalize_period(period_year)
        prior_period = _previous_period(current_period)
        current_analysis, _ = _get_analysis_for_period(site_obj, current_period)
        previous_analysis, _ = _get_analysis_for_period(site_obj, prior_period)

        trend_by_metric = {
            "deforestation": {
                "delta_12m": round(
                    float(current_analysis["metrics"]["deforestation"]["vegetation_change_pct"])
                    - float(previous_analysis["metrics"]["deforestation"]["vegetation_change_pct"]),
                    3,
                )
            },
            "water_change": {
                "delta_12m": round(
                    float(current_analysis["metrics"]["water_change"]["water_change_pct"])
                    - float(previous_analysis["metrics"]["water_change"]["water_change_pct"]),
                    3,
                )
            },
            "uhi": {
                "delta_12m": round(
                    float(current_analysis["metrics"]["uhi"]["uhi_intensity_c"])
                    - float(previous_analysis["metrics"]["uhi"]["uhi_intensity_c"]),
                    3,
                )
            },
        }

        rows = build_esrs_rows(
            site={"site_id": payload.site_id, "lat": payload.lat, "lon": payload.lon},
            metrics=report_result["metrics"],
            trend_by_metric=trend_by_metric,
        )
        csv_path = write_compliance_csv(rows)
        zip_path = create_compliance_zip(payload.site_id, report_result["report_path"], csv_path)

        log_event(
            "compliance_pack",
            {
                "site_id": payload.site_id,
                "zip_path": zip_path,
                "csv_path": csv_path,
                "pdf_path": report_result["report_path"],
            },
        )

        if s3_delivery_enabled():
            try:
                upload_result = upload_compliance_pack(zip_path, payload.site_id)
                log_event(
                    "compliance_pack_s3_uploaded",
                    {
                        "site_id": payload.site_id,
                        "bucket": upload_result["bucket"],
                        "object_key": upload_result["object_key"],
                        "expires_in_seconds": upload_result["expires_in_seconds"],
                    },
                )
                return {
                    "status": "ok",
                    "delivery": "s3",
                    "file_name": Path(zip_path).name,
                    **upload_result,
                }
            except Exception as exc:
                log_event(
                    "compliance_pack_s3_failed",
                    {"site_id": payload.site_id, "error": str(exc)},
                )

        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=Path(zip_path).name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
