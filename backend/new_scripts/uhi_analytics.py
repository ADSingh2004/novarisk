from __future__ import annotations

import xarray as xr


def calculate_uhi_intensity(era5_netcdf_path: str, urban_quantile: float = 0.9, rural_quantile: float = 0.2) -> dict[str, float]:
    """
    Rule-based UHI intensity from ERA5-Land temperature using percentile split.

    - Urban proxy temperature = high-temperature quantile (default 90th)
    - Rural proxy temperature = low-temperature quantile (default 20th)
    - UHI intensity = urban_proxy - rural_proxy
    """
    ds = xr.open_dataset(era5_netcdf_path)

    var_name = None
    for candidate in ["t2m", "temperature_2m", "tas"]:
        if candidate in ds.data_vars:
            var_name = candidate
            break

    if var_name is None:
        raise ValueError("No supported temperature variable found. Expected one of: t2m, temperature_2m, tas")

    arr = ds[var_name]
    temp_c = arr - 273.15 if float(arr.mean()) > 200 else arr

    temp_mean = float(temp_c.mean().values)
    urban_proxy = float(temp_c.quantile(urban_quantile).values)
    rural_proxy = float(temp_c.quantile(rural_quantile).values)
    uhi_intensity = float(urban_proxy - rural_proxy)

    ds.close()

    return {
        "temperature_mean_c": temp_mean,
        "urban_proxy_c": urban_proxy,
        "rural_proxy_c": rural_proxy,
        "uhi_intensity_c": uhi_intensity,
        "risk_score": max(0.0, uhi_intensity),
    }
