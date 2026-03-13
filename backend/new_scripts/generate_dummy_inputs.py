from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
import xarray as xr
from rasterio.transform import from_origin


def _write_tif(
    path: Path,
    bands: list[np.ndarray],
    crs: str = "EPSG:4326",
    dtype: str = "float32",
) -> None:
    h, w = bands[0].shape
    transform = from_origin(0.0, 0.0, 10.0, 10.0)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=w,
        height=h,
        count=len(bands),
        dtype=dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        for idx, band in enumerate(bands, start=1):
            dst.write(band.astype(dtype), idx)


def generate_dummy_optical_band(
    output_path: str,
    low: float = 0.02,
    high: float = 0.35,
    shape: tuple[int, int] = (512, 512),
    seed: int | None = None,
) -> str:
    rng = np.random.default_rng(seed)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = rng.uniform(low, high, shape).astype("float32")
    _write_tif(out, [data])
    return str(out)


def generate_dummy_sar_band(
    output_path: str,
    low: float = -25.0,
    high: float = -5.0,
    shape: tuple[int, int] = (512, 512),
    seed: int | None = None,
) -> str:
    rng = np.random.default_rng(seed)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = rng.uniform(low, high, shape).astype("float32")
    _write_tif(out, [data])
    return str(out)


def generate_dummy_water_inputs(output_dir: str = "data/dummy/water", seed: int = 11) -> dict[str, str]:
    rng = np.random.default_rng(seed)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    h, w = 256, 256

    before_green = rng.uniform(0.06, 0.35, (h, w))
    before_swir = rng.uniform(0.08, 0.40, (h, w))
    after_green = before_green.copy()
    after_swir = before_swir.copy()

    before_sar = rng.uniform(-14, -8, (h, w))
    after_sar = before_sar.copy()

    y1, y2, x1, x2 = 90, 200, 90, 220
    after_green[y1:y2, x1:x2] = rng.uniform(0.12, 0.28, (y2 - y1, x2 - x1))
    after_swir[y1:y2, x1:x2] = rng.uniform(0.02, 0.12, (y2 - y1, x2 - x1))
    after_sar[y1:y2, x1:x2] = rng.uniform(-23, -18, (y2 - y1, x2 - x1))

    before_optical = out / "water_before_optical.tif"
    after_optical = out / "water_after_optical.tif"
    before_sar_tif = out / "water_before_sar.tif"
    after_sar_tif = out / "water_after_sar.tif"

    _write_tif(before_optical, [before_green.astype("float32"), before_swir.astype("float32")])
    _write_tif(after_optical, [after_green.astype("float32"), after_swir.astype("float32")])
    _write_tif(before_sar_tif, [before_sar.astype("float32")])
    _write_tif(after_sar_tif, [after_sar.astype("float32")])

    return {
        "before_optical_tif": str(before_optical),
        "after_optical_tif": str(after_optical),
        "before_sar_tif": str(before_sar_tif),
        "after_sar_tif": str(after_sar_tif),
    }


def generate_dummy_worldcover_raster(
    output_path: str = "data/dummy/reference/worldcover_reference.tif",
    seed: int = 21,
) -> str:
    rng = np.random.default_rng(seed)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    h, w = 512, 512
    classes = np.array([10, 20, 30, 40, 50, 60, 80, 90, 95, 100, 200, 255], dtype="uint8")
    weights = np.array([0.05, 0.08, 0.12, 0.1, 0.04, 0.04, 0.12, 0.1, 0.05, 0.05, 0.15, 0.1])
    weights = weights / weights.sum()
    data = rng.choice(classes, size=(h, w), p=weights)

    _write_tif(out, [data], dtype="uint8")
    return str(out)


def generate_dummy_jrc_water_occurrence(
    output_path: str = "data/dummy/reference/jrc_water_reference.tif",
    seed: int = 31,
) -> str:
    rng = np.random.default_rng(seed)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    h, w = 512, 512
    grad = np.linspace(0, 1, w)
    occurrence = np.tile(grad, (h, 1)) * 100.0
    noise = rng.normal(0, 8.0, size=(h, w))
    data = np.clip(occurrence + noise, 0, 100).astype("float32")

    _write_tif(out, [data])
    return str(out)


def generate_dummy_era5_netcdf(output_path: str = "data/dummy/era5/era5_land_t2m.nc", seed: int = 15) -> str:
    rng = np.random.default_rng(seed)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    time = np.arange(0, 24)
    lat = np.linspace(10.0, 10.5, 25)
    lon = np.linspace(76.8, 77.3, 25)

    base = 303.0
    noise = rng.normal(0, 1.8, size=(len(time), len(lat), len(lon)))
    t2m = base + noise

    ds = xr.Dataset(
        data_vars={"t2m": (("time", "lat", "lon"), t2m.astype("float32"))},
        coords={"time": time, "lat": lat, "lon": lon},
    )
    ds.to_netcdf(out)
    ds.close()

    return str(out)


if __name__ == "__main__":
    print(generate_dummy_water_inputs())
    print(generate_dummy_era5_netcdf())
    print(generate_dummy_worldcover_raster())
    print(generate_dummy_jrc_water_occurrence())
