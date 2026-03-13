from __future__ import annotations

import numpy as np
import rasterio
from rasterio.transform import Affine


def _read_red_nir(path: str) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(path) as src:
        if src.count >= 8:
            red = src.read(4).astype("float32")
            nir = src.read(8).astype("float32")
        elif src.count >= 2:
            red = src.read(1).astype("float32")
            nir = src.read(2).astype("float32")
        else:
            raise ValueError(
                f"{path} must contain at least 2 bands (red, nir) or Sentinel-2 style 8+ bands."
            )

    return red, nir


def _calculate_ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    denominator = nir + red
    denominator = np.where(denominator == 0, np.nan, denominator)
    return (nir - red) / denominator


def calculate_deforestation_risk(before_tif: str, after_tif: str) -> float:
    """
    Reads two Sentinel-2 images, computes NDVI, thresholds vegetation (NDVI > 0.4),
    and returns the percentage-point difference in vegetation coverage:

        vegetation_after_pct - vegetation_before_pct

    A negative value indicates vegetation loss.
    """
    before_red, before_nir = _read_red_nir(before_tif)
    after_red, after_nir = _read_red_nir(after_tif)

    before_ndvi = _calculate_ndvi(before_red, before_nir)
    after_ndvi = _calculate_ndvi(after_red, after_nir)

    before_veg = before_ndvi > 0.4
    after_veg = after_ndvi > 0.4

    valid_mask = np.isfinite(before_ndvi) & np.isfinite(after_ndvi)
    valid_pixels = np.count_nonzero(valid_mask)
    if valid_pixels == 0:
        raise ValueError("No valid pixels available to compare NDVI vegetation masks.")

    before_veg_pct = (np.count_nonzero(before_veg & valid_mask) / valid_pixels) * 100.0
    after_veg_pct = (np.count_nonzero(after_veg & valid_mask) / valid_pixels) * 100.0

    return float(after_veg_pct - before_veg_pct)


def _cell_bbox(transform: Affine, row: int, col: int) -> list[float]:
    x_min, y_max = transform * (col, row)
    x_max, y_min = transform * (col + 1, row + 1)
    return [float(x_min), float(y_min), float(x_max), float(y_max)]


def _hotspot_cells(
    delta_mask: np.ndarray,
    valid_mask: np.ndarray,
    transform: Affine,
    crs_wkt: str,
    max_cells: int = 50,
) -> list[dict[str, object]]:
    rows, cols = np.where(delta_mask & valid_mask)
    limit = min(len(rows), max_cells)
    hotspots: list[dict[str, object]] = []
    for idx in range(limit):
        row = int(rows[idx])
        col = int(cols[idx])
        hotspots.append(
            {
                "row": row,
                "col": col,
                "bbox": _cell_bbox(transform, row, col),
                "crs": crs_wkt,
            }
        )
    return hotspots


def calculate_deforestation_detail(before_tif: str, after_tif: str) -> dict[str, object]:
    with rasterio.open(before_tif) as before_src:
        if before_src.count >= 8:
            before_red = before_src.read(4).astype("float32")
            before_nir = before_src.read(8).astype("float32")
        elif before_src.count >= 2:
            before_red = before_src.read(1).astype("float32")
            before_nir = before_src.read(2).astype("float32")
        else:
            raise ValueError("before_tif must contain red/nir bands")
        transform = before_src.transform
        crs_wkt = before_src.crs.to_wkt() if before_src.crs else "EPSG:4326"

    with rasterio.open(after_tif) as after_src:
        if after_src.count >= 8:
            after_red = after_src.read(4).astype("float32")
            after_nir = after_src.read(8).astype("float32")
        elif after_src.count >= 2:
            after_red = after_src.read(1).astype("float32")
            after_nir = after_src.read(2).astype("float32")
        else:
            raise ValueError("after_tif must contain red/nir bands")

    before_ndvi = _calculate_ndvi(before_red, before_nir)
    after_ndvi = _calculate_ndvi(after_red, after_nir)

    before_veg = before_ndvi > 0.4
    after_veg = after_ndvi > 0.4
    valid_mask = np.isfinite(before_ndvi) & np.isfinite(after_ndvi)
    valid_pixels = np.count_nonzero(valid_mask)
    if valid_pixels == 0:
        raise ValueError("No valid pixels available to compare NDVI vegetation masks.")

    loss_mask = before_veg & (~after_veg)
    gain_mask = (~before_veg) & after_veg

    before_veg_pct = (np.count_nonzero(before_veg & valid_mask) / valid_pixels) * 100.0
    after_veg_pct = (np.count_nonzero(after_veg & valid_mask) / valid_pixels) * 100.0
    change_pct = float(after_veg_pct - before_veg_pct)

    return {
        "vegetation_before_pct": float(before_veg_pct),
        "vegetation_after_pct": float(after_veg_pct),
        "vegetation_change_pct": change_pct,
        "hectares_lost_proxy": float(np.count_nonzero(loss_mask & valid_mask) * 0.01),
        "hotspots": _hotspot_cells(loss_mask, valid_mask, transform, crs_wkt),
        "layers": {
            "loss_mask_source": after_tif,
            "summary": "Rule-based NDVI loss mask cells",
        },
    }
