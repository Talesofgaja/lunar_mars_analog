"""Turn raw tile data (DEM, surface bands, climate) into comparable descriptors.

Every descriptor is a plain dict. Reference sites (loaded from JSON) and
candidate Earth tiles (computed here) go through the same similarity code,
so a new data layer only needs a function here plus a scale in config.json.
"""
import numpy as np
from scipy import ndimage

SLOPE_EDGES_DEG = np.linspace(0.0, 45.0, 16)   # 15 bins, 3 degrees wide
SLOPE_BIN_WIDTH_DEG = 3.0
ROUGHNESS_WINDOW_PX = 5                         # size of the detrending window


def morphometric_descriptor(dem, dx_m, dy_m):
    """Slope distribution, roughness and relief from an elevation array (metres).

    dx_m, dy_m are the ground spacing of one pixel along x and y in metres.
    Returns None if the tile has too few valid pixels.
    """
    z = np.asarray(dem, dtype=float)
    valid = np.isfinite(z)
    if valid.sum() < 16:
        return None
    z = np.where(valid, z, np.nanmean(z[valid]))   # fill gaps so gradients exist

    dz_dy, dz_dx = np.gradient(z, dy_m, dx_m)
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
    slope = np.clip(slope[valid], 0.0, SLOPE_EDGES_DEG[-1] - 1e-9)

    hist, _ = np.histogram(slope, bins=SLOPE_EDGES_DEG)
    probs = hist / hist.sum()

    # Roughness: standard deviation of the residual after removing a local mean.
    residual = z - ndimage.uniform_filter(z, size=ROUGHNESS_WINDOW_PX)

    return {
        "slope_hist": probs.tolist(),
        "median_slope_deg": float(np.median(slope)),
        "roughness_m": float(np.std(residual[valid])),
        "relief_m": float(z[valid].max() - z[valid].min()),
    }


def spectral_descriptor(bands):
    """Median band-ratio indices from Sentinel-2 style reflectance arrays.

    bands: dict with keys B02 (blue), B04 (red), B08 (NIR), B11 and B12 (SWIR).
    Indices are scalars, so they can be compared across instruments
    once reference values are calibrated to the same definitions.
    """
    eps = 1e-6

    def median_valid(arr):
        arr = np.asarray(arr, dtype=float)
        v = arr[np.isfinite(arr)]
        return float(np.median(v)) if v.size else None

    b02, b04, b08, b11, b12 = (np.asarray(bands[k], dtype=float)
                               for k in ("B02", "B04", "B08", "B11", "B12"))
    desc = {
        "iron_oxide_ratio": median_valid(b04 / (b02 + eps)),     # red/blue, Fe-oxide proxy
        "clay_ratio": median_valid(b11 / (b12 + eps)),           # SWIR1/SWIR2, clay/hydroxyl proxy
        "ndvi": median_valid((b08 - b04) / (b08 + b04 + eps)),   # vegetation cover (low = bare)
    }
    return {k: v for k, v in desc.items() if v is not None}


def climate_descriptor(temp_max_c=None, temp_min_c=None, precip_mm_day=None):
    """Summary climate values. Any input may be None (e.g. no atmosphere on the Moon)."""
    desc = {}
    if temp_max_c is not None and temp_min_c is not None:
        desc["temp_range_c"] = float(temp_max_c - temp_min_c)
        desc["mean_temp_c"] = float((temp_max_c + temp_min_c) / 2.0)
    if precip_mm_day is not None:
        desc["precip_mm_day"] = float(precip_mm_day)   # aridity proxy
    return desc


def describe_tile(tile):
    """Build a descriptor dict from a tile dict.

    Expected optional keys: dem, dx_m, dy_m, bands, climate (a climate descriptor).
    Only the sections that have data are returned.
    """
    out = {}
    if tile.get("dem") is not None:
        out["morphometric"] = morphometric_descriptor(tile["dem"], tile["dx_m"], tile["dy_m"])
    if tile.get("bands") is not None:
        out["spectral"] = spectral_descriptor(tile["bands"])
    if tile.get("climate"):
        out["climate"] = dict(tile["climate"])
    return {k: v for k, v in out.items() if v}
