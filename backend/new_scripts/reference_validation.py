from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

from ingestion.analytics import _calculate_ndvi, _read_red_nir
from ingestion.water_analytics import _read_green_swir, _read_sar, _safe_ratio

DEFAULT_WORLDCOVER_VEGETATION_CLASSES = [10, 20, 30, 40, 90, 95]


def _reproject_reference_to_target(reference_path: str, target_path: str) -> np.ndarray:
    with rasterio.open(target_path) as target_src:
        dst_height = target_src.height
        dst_width = target_src.width
        dst_transform = target_src.transform
        dst_crs = target_src.crs

    with rasterio.open(reference_path) as reference_src:
        source_array = reference_src.read(1).astype("float32")
        destination = np.full((dst_height, dst_width), np.nan, dtype="float32")

        reproject(
            source=source_array,
            destination=destination,
            src_transform=reference_src.transform,
            src_crs=reference_src.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            src_nodata=reference_src.nodata,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )

    return destination


def _binary_classification_metrics(
    predicted_positive: np.ndarray,
    reference_positive: np.ndarray,
    valid_mask: np.ndarray,
) -> dict[str, float]:
    predicted = predicted_positive.astype(bool)
    reference = reference_positive.astype(bool)
    valid = valid_mask.astype(bool)

    tp = int(np.count_nonzero(predicted & reference & valid))
    tn = int(np.count_nonzero(~predicted & ~reference & valid))
    fp = int(np.count_nonzero(predicted & ~reference & valid))
    fn = int(np.count_nonzero(~predicted & reference & valid))

    total = tp + tn + fp + fn
    if total == 0:
        raise ValueError("No valid pixels available for reference validation.")

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0
    accuracy = (tp + tn) / total

    return {
        "tp": float(tp),
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
        "valid_pixels": float(total),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "iou": float(iou),
        "accuracy": float(accuracy),
    }


def _reference_water_mask(reference_array: np.ndarray) -> np.ndarray:
    finite = reference_array[np.isfinite(reference_array)]
    if finite.size == 0:
        return np.zeros_like(reference_array, dtype=bool)

    max_value = float(np.nanmax(finite))
    if max_value <= 1.0:
        return reference_array >= 0.5
    if max_value <= 100.0:
        return reference_array >= 50.0
    return reference_array == 1.0


def validate_deforestation_against_worldcover(
    after_tif: str,
    worldcover_tif: str,
    ndvi_threshold: float = 0.4,
    vegetation_classes: Sequence[int] | None = None,
) -> dict[str, float]:
    vegetation_class_values = list(vegetation_classes or DEFAULT_WORLDCOVER_VEGETATION_CLASSES)

    red, nir = _read_red_nir(after_tif)
    ndvi = _calculate_ndvi(red, nir)
    predicted_vegetation = ndvi > ndvi_threshold

    worldcover_resampled = _reproject_reference_to_target(worldcover_tif, after_tif)
    reference_vegetation = np.isin(worldcover_resampled, vegetation_class_values)

    valid_mask = np.isfinite(ndvi) & np.isfinite(worldcover_resampled)

    metrics = _binary_classification_metrics(predicted_vegetation, reference_vegetation, valid_mask)
    metrics["ndvi_threshold"] = float(ndvi_threshold)
    return metrics


def validate_water_against_jrc(
    after_optical_tif: str,
    after_sar_tif: str,
    jrc_reference_tif: str,
    mndwi_threshold: float = 0.1,
    sar_db_threshold: float = -17.0,
) -> dict[str, float]:
    green, swir = _read_green_swir(after_optical_tif)
    sar = _read_sar(after_sar_tif)

    mndwi = _safe_ratio(green - swir, green + swir)
    predicted_water = (mndwi > mndwi_threshold) & (sar < sar_db_threshold)

    jrc_resampled = _reproject_reference_to_target(jrc_reference_tif, after_optical_tif)
    reference_water = _reference_water_mask(jrc_resampled)

    valid_mask = np.isfinite(mndwi) & np.isfinite(sar) & np.isfinite(jrc_resampled)

    metrics = _binary_classification_metrics(predicted_water, reference_water, valid_mask)
    metrics["mndwi_threshold"] = float(mndwi_threshold)
    metrics["sar_db_threshold"] = float(sar_db_threshold)
    return metrics


def validate_site_against_references(
    after_tif: str,
    worldcover_tif: str,
    water_after_optical_tif: str,
    water_after_sar_tif: str,
    jrc_reference_tif: str,
    ndvi_threshold: float = 0.4,
    mndwi_threshold: float = 0.1,
    sar_db_threshold: float = -17.0,
    vegetation_classes: Sequence[int] | None = None,
) -> dict[str, dict[str, float]]:
    deforestation_validation = validate_deforestation_against_worldcover(
        after_tif=after_tif,
        worldcover_tif=worldcover_tif,
        ndvi_threshold=ndvi_threshold,
        vegetation_classes=vegetation_classes,
    )

    water_validation = validate_water_against_jrc(
        after_optical_tif=water_after_optical_tif,
        after_sar_tif=water_after_sar_tif,
        jrc_reference_tif=jrc_reference_tif,
        mndwi_threshold=mndwi_threshold,
        sar_db_threshold=sar_db_threshold,
    )

    return {
        "deforestation_validation": deforestation_validation,
        "water_validation": water_validation,
    }
