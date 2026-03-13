from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
import rasterio
from rasterio.windows import from_bounds


def clip_cog_to_bbox(
    cog_href: str,
    bbox: Tuple[float, float, float, float],
    destination: str,
    bands: Iterable[int] | None = None,
) -> Path:
    """Clip a remote COG (or local path) to the provided bbox."""
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.Env(AWS_NO_SIGN_REQUEST="YES"):
        with rasterio.open(cog_href) as src:
            window = from_bounds(*bbox, transform=src.transform)
            window = window.round_lengths().round_offsets()
            data = src.read(window=window, indexes=bands)
            profile = src.profile
            profile.update(
                height=data.shape[1],
                width=data.shape[2],
                transform=src.window_transform(window),
            )
            with rasterio.open(dest, "w", **profile) as dst:
                dst.write(data)
    return dest


def save_array_as_cog(array: np.ndarray, reference: rasterio.io.DatasetReader, destination: str) -> Path:
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    profile = reference.profile
    profile.update(count=array.shape[0], dtype=array.dtype)
    with rasterio.open(dest, "w", **profile) as dst:
        dst.write(array)
    return dest
