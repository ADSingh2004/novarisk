from __future__ import annotations

import numpy as np
import rasterio
from rasterio.transform import Affine


def _safe_ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    denominator = np.where(denominator == 0, np.nan, denominator)
    return numerator / denominator


def _read_green_swir(path: str) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(path) as src:
        if src.count >= 11:
            green = src.read(3).astype("float32")
            swir = src.read(11).astype("float32")
        elif src.count >= 2:
            green = src.read(1).astype("float32")
            swir = src.read(2).astype("float32")
        else:
            raise ValueError(
                f"{path} must contain at least 2 bands (green, swir) or Sentinel-2 style 11+ bands."
            )
    return green, swir


def _read_sar(path: str) -> np.ndarray:
    with rasterio.open(path) as src:
        sar = src.read(1).astype("float32")
    return sar


def calculate_water_body_change(
    before_optical_tif: str,
    after_optical_tif: str,
    before_sar_tif: str,
    after_sar_tif: str,
    mndwi_threshold: float = 0.1,
    sar_db_threshold: float = -17.0,
) -> dict[str, float]:
    """
    Rule-based water-body change using Sentinel-2 MNDWI + Sentinel-1 SAR backscatter.

    Water mask rule:
        (MNDWI > mndwi_threshold) AND (SAR_dB < sar_db_threshold)

    Returns percent-point change in water coverage and derived risk score.
    """
    before_green, before_swir = _read_green_swir(before_optical_tif)
    after_green, after_swir = _read_green_swir(after_optical_tif)

    before_sar = _read_sar(before_sar_tif)
    after_sar = _read_sar(after_sar_tif)

    before_mndwi = _safe_ratio(before_green - before_swir, before_green + before_swir)
    after_mndwi = _safe_ratio(after_green - after_swir, after_green + after_swir)

    before_water = (before_mndwi > mndwi_threshold) & (before_sar < sar_db_threshold)
    after_water = (after_mndwi > mndwi_threshold) & (after_sar < sar_db_threshold)

    valid = (
        np.isfinite(before_mndwi)
        & np.isfinite(after_mndwi)
        & np.isfinite(before_sar)
        & np.isfinite(after_sar)
    )
    valid_pixels = np.count_nonzero(valid)
    if valid_pixels == 0:
        raise ValueError("No valid pixels available to compare water masks.")

    before_pct = (np.count_nonzero(before_water & valid) / valid_pixels) * 100.0
    after_pct = (np.count_nonzero(after_water & valid) / valid_pixels) * 100.0
    water_change_pct = float(after_pct - before_pct)

    return {
        "water_before_pct": float(before_pct),
        "water_after_pct": float(after_pct),
        "water_change_pct": water_change_pct,
        "risk_score": float(abs(water_change_pct)),
    }


def _cell_bbox(transform: Affine, row: int, col: int) -> list[float]:
    x_min, y_max = transform * (col, row)
    x_max, y_min = transform * (col + 1, row + 1)
    return [float(x_min), float(y_min), float(x_max), float(y_max)]


def _hotspot_cells(
    mask: np.ndarray,
    valid_mask: np.ndarray,
    transform: Affine,
    crs_wkt: str,
    max_cells: int = 50,
) -> list[dict[str, object]]:
    rows, cols = np.where(mask & valid_mask)
    hotspots: list[dict[str, object]] = []
    for idx in range(min(len(rows), max_cells)):
        row = int(rows[idx])
        col = int(cols[idx])
        hotspots.append({"row": row, "col": col, "bbox": _cell_bbox(transform, row, col), "crs": crs_wkt})
    return hotspots


def calculate_water_body_change_detail(
    before_optical_tif: str,
    after_optical_tif: str,
    before_sar_tif: str,
    after_sar_tif: str,
    mndwi_threshold: float = 0.1,
    sar_db_threshold: float = -17.0,
) -> dict[str, object]:
    with rasterio.open(after_optical_tif) as src:
        transform = src.transform
        crs_wkt = src.crs.to_wkt() if src.crs else "EPSG:4326"

    before_green, before_swir = _read_green_swir(before_optical_tif)
    after_green, after_swir = _read_green_swir(after_optical_tif)
    before_sar = _read_sar(before_sar_tif)
    after_sar = _read_sar(after_sar_tif)

    before_mndwi = _safe_ratio(before_green - before_swir, before_green + before_swir)
    after_mndwi = _safe_ratio(after_green - after_swir, after_green + after_swir)

    before_optical_water = before_mndwi > mndwi_threshold
    after_optical_water = after_mndwi > mndwi_threshold
    before_sar_water = before_sar < sar_db_threshold
    after_sar_water = after_sar < sar_db_threshold

    before_water = before_optical_water & before_sar_water
    after_water = after_optical_water & after_sar_water

    valid = np.isfinite(before_mndwi) & np.isfinite(after_mndwi) & np.isfinite(before_sar) & np.isfinite(after_sar)
    valid_pixels = np.count_nonzero(valid)
    if valid_pixels == 0:
        raise ValueError("No valid pixels available to compare water masks.")

    before_pct = (np.count_nonzero(before_water & valid) / valid_pixels) * 100.0
    after_pct = (np.count_nonzero(after_water & valid) / valid_pixels) * 100.0
    optical_after_pct = (np.count_nonzero(after_optical_water & valid) / valid_pixels) * 100.0
    sar_after_pct = (np.count_nonzero(after_sar_water & valid) / valid_pixels) * 100.0
    consistency_gap = float(abs(optical_after_pct - sar_after_pct))

    shrink_mask = before_water & (~after_water)
    change_pct = float(after_pct - before_pct)

    return {
        "water_before_pct": float(before_pct),
        "water_after_pct": float(after_pct),
        "water_change_pct": change_pct,
        "risk_score": float(abs(change_pct)),
        "sensor_consistency_gap_pct": consistency_gap,
        "hotspots": _hotspot_cells(shrink_mask, valid, transform, crs_wkt),
        "layers": {
            "water_shrink_mask_source": after_optical_tif,
            "summary": "Dual-sensor water shrink hotspots",
        },
    }
