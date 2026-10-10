"""Offline synthetic terrain for testing and demos. No network or data downloads needed.

The region is split at lon -69.9: the west half is rugged and arid, the east
half is smooth and humid. A correct pipeline should match each tile to the
reference from its own zone.
"""
import numpy as np
from scipy import ndimage
from .descriptors import climate_descriptor, describe_tile

SPLIT_LON = -69.9


def _terrain(rng, shape, amplitude_m, smooth_sigma_px):
    noise = ndimage.gaussian_filter(rng.standard_normal(shape), smooth_sigma_px)
    noise = (noise - noise.mean()) / (noise.std() + 1e-9)
    return noise * amplitude_m


def make_synthetic_provider(seed=0, shape=(120, 120), pixel_m=30.0):
    rng = np.random.default_rng(seed)

    def provider(bbox):
        lon_mid = (bbox[0] + bbox[2]) / 2.0
        rugged = lon_mid < SPLIT_LON
        dem = _terrain(rng, shape,
                       amplitude_m=60.0 if rugged else 8.0,
                       smooth_sigma_px=2.0 if rugged else 6.0)

        def band(mean):
            return np.clip(mean * (1 + 0.05 * rng.standard_normal(shape)), 1e-4, None)

        bands = {
            "B02": band(0.08 if rugged else 0.05),
            "B04": band(0.24 if rugged else 0.06),
            "B08": band(0.30 if rugged else 0.35),
            "B11": band(0.24 if rugged else 0.20),
            "B12": band(0.20),
        }
        climate = climate_descriptor(temp_max_c=35.0 if rugged else 25.0,
                                     temp_min_c=-5.0 if rugged else 12.0,
                                     precip_mm_day=0.05 if rugged else 2.5)
        return {"dem": dem, "dx_m": pixel_m, "dy_m": pixel_m,
                "bands": bands, "climate": climate}
    return provider


def synthetic_reference_sites(seed=1):
    """Two in-memory references: one rugged/arid, one smooth/humid."""
    prov = make_synthetic_provider(seed=seed)
    arid = describe_tile(prov([-70.0, -24.0, -69.9, -23.9]))
    humid = describe_tile(prov([-69.8, -24.0, -69.7, -23.9]))
    return [
        {"name": "synthetic_arid_ref", "body": "earth", "lon": -69.95, "lat": -23.95, "descriptor": arid},
        {"name": "synthetic_humid_ref", "body": "earth", "lon": -69.75, "lat": -23.95, "descriptor": humid},
    ]
