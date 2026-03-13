from __future__ import annotations

import csv
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


def _display_risk_band(metric_payload: dict[str, Any]) -> str:
    band = str(metric_payload.get("risk_band", "")).strip().lower()
    if band == "critical":
        return "Critical"
    if band == "high":
        return "High"
    if band == "moderate":
        return "Moderate"
    if band == "low":
        return "Low"

    score = float(metric_payload.get("risk_score", 0.0) or 0.0)
    if score >= 80:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 20:
        return "Moderate"
    return "Low"


def build_esrs_rows(
    site: dict[str, Any],
    metrics: dict[str, Any],
    trend_by_metric: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    trend_by_metric = trend_by_metric or {}

    def _row(
        metric_key: str,
        metric_label: str,
        value: Any,
        unit: str,
        esrs_mapping: str,
        notes: str,
        caveat: str,
    ) -> dict[str, str]:
        trend = trend_by_metric.get(metric_key, {}) if isinstance(trend_by_metric, dict) else {}
        metric_payload = metrics.get(metric_key, {})
        confidence = metric_payload.get("confidence", "")
        quality_flags = metric_payload.get("quality_flags", [])
        return {
            "site_id": str(site.get("site_id", "")),
            "metric": metric_label,
            "value": str(value),
            "unit": unit,
            "risk_band": _display_risk_band(metric_payload),
            "trend_delta_12m": str(trend.get("delta_12m", "")),
            "confidence": str(confidence),
            "quality_flags": "; ".join([str(flag) for flag in quality_flags]) if quality_flags else "none",
            "esrs_mapping": esrs_mapping,
            "notes": notes,
            "caveat": caveat,
        }

    return [
        _row(
            metric_key="deforestation",
            metric_label="Deforestation / Land-use",
            value=metrics.get("deforestation", {}).get("vegetation_change_pct", ""),
            unit="pct_change",
            esrs_mapping="ESRS E4 Biodiversity and ecosystems",
            notes="NDVI vegetation delta aligned to land-use impact signal",
            caveat="Proxy for land-use pressure; cloud/seasonal effects may influence monthly certainty.",
        ),
        _row(
            metric_key="water_change",
            metric_label="Water Body Change",
            value=metrics.get("water_change", {}).get("water_change_pct", ""),
            unit="pct_change",
            esrs_mapping="ESRS E3 Water and marine resources",
            notes="MNDWI + SAR combined water mask change",
            caveat="Stress proxy indicator, not direct water consumption measurement.",
        ),
        _row(
            metric_key="uhi",
            metric_label="Urban Heat Island Intensity",
            value=metrics.get("uhi", {}).get("uhi_intensity_c", ""),
            unit="degC",
            esrs_mapping="ESRS E1 Climate change",
            notes="ERA5-Land percentile proxy urban-rural thermal gap",
            caveat="UHI exposure proxy from air temperature; not direct LST unless thermal satellites are used.",
        ),
    ]


def write_compliance_csv(rows: list[dict[str, str]], output_dir: str = "data/compliance") -> str:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / f"compliance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    fieldnames = [
        "site_id",
        "metric",
        "value",
        "unit",
        "risk_band",
        "trend_delta_12m",
        "confidence",
        "quality_flags",
        "esrs_mapping",
        "notes",
        "caveat",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return str(csv_path)


def create_compliance_zip(site_id: str, pdf_path: str, csv_path: str, output_dir: str = "data/compliance") -> str:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = out_dir / f"compliance_pack_{site_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(pdf_path, arcname=Path(pdf_path).name)
        archive.write(csv_path, arcname=Path(csv_path).name)

    return str(zip_path)
