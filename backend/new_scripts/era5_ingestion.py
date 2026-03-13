from __future__ import annotations

from pathlib import Path

from ingestion.generate_dummy_inputs import generate_dummy_era5_netcdf


def prepare_era5_dataset(local_path: str = "data/dummy/era5/era5_land_t2m.nc") -> str:
    """
    MVP helper for Week 1:
    - If real ERA5 download pipeline is not configured, generate a local dummy NetCDF.
    """
    path = Path(local_path)
    if path.exists():
        return str(path)
    return generate_dummy_era5_netcdf(str(path))


if __name__ == "__main__":
    print(prepare_era5_dataset())
