"""Offline tests. Run with: python -m pytest tests/   (or: python tests/test_synthetic_pipeline.py)"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analog_finder.descriptors import describe_tile, morphometric_descriptor, spectral_descriptor
from analog_finder.similarity import (composite, keyed_similarity,
                                      morphometric_similarity, best_reference)
from analog_finder.pipeline import make_grid, run_search
from analog_finder.synthetic import make_synthetic_provider, synthetic_reference_sites

CFG = {
    "weights": {"morphometric": 0.4, "spectral": 0.3, "climate": 0.3},
    "morph_scales": {"slope_w1_deg": 5.0},
    "spectral_scales": {"iron_oxide_ratio": 0.5, "clay_ratio": 0.1, "ndvi": 0.2},
    "climate_scales": {"temp_range_c": 30.0, "mean_temp_c": 20.0, "precip_mm_day": 2.0},
}
BBOX = [-70.0, -24.0, -69.4, -23.6]


def test_flat_dem_has_zero_slope_and_roughness():
    d = morphometric_descriptor(np.zeros((50, 50)), 30.0, 30.0)
    assert d["median_slope_deg"] == 0.0
    assert d["roughness_m"] == 0.0
    assert d["relief_m"] == 0.0


def test_tilted_plane_slope_is_correct():
    # z rises 1 m per 30 m pixel along x: slope = arctan(1/30) ~ 1.91 degrees everywhere
    x = np.arange(60) * 1.0
    dem = np.tile(x, (60, 1))
    d = morphometric_descriptor(dem, 30.0, 30.0)
    assert abs(d["median_slope_deg"] - math.degrees(math.atan(1 / 30))) < 0.05


def test_identical_descriptors_score_one():
    prov = make_synthetic_provider(seed=3)
    desc = describe_tile(prov(BBOX))
    scores = {
        "morphometric": morphometric_similarity(desc["morphometric"], desc["morphometric"],
                                                CFG["morph_scales"]),
        "spectral": keyed_similarity(desc["spectral"], desc["spectral"], CFG["spectral_scales"]),
        "climate": keyed_similarity(desc["climate"], desc["climate"], CFG["climate_scales"]),
    }
    for v in scores.values():
        assert abs(v - 1.0) < 1e-9


def test_composite_renormalises_missing_criteria():
    # Moon-style reference with no climate: weights of the others should sum to 1
    assert abs(composite({"morphometric": 0.8, "spectral": 0.6}, CFG["weights"]) -
               (0.4 * 0.8 + 0.3 * 0.6) / 0.7) < 1e-9
    assert composite({}, CFG["weights"]) is None


def test_spectral_descriptor_ratios():
    bands = {"B02": np.full((4, 4), 0.1), "B04": np.full((4, 4), 0.3),
             "B08": np.full((4, 4), 0.5), "B11": np.full((4, 4), 0.2),
             "B12": np.full((4, 4), 0.1)}
    d = spectral_descriptor(bands)
    assert abs(d["iron_oxide_ratio"] - 3.0) < 1e-4
    assert abs(d["clay_ratio"] - 2.0) < 1e-4
    assert abs(d["ndvi"] - 0.25) < 1e-4


def test_pipeline_matches_each_zone_to_its_own_reference():
    refs = synthetic_reference_sites()
    cfg = {**CFG, "region": {"bbox": [-70.0, -24.0, -69.4, -23.6]}, "tile_size_deg": 0.1}
    df, descs = run_search(cfg, refs, make_synthetic_provider(seed=7))
    assert len(df) == 6 * 4                      # 6 lon columns x 4 lat rows
    for rec in df.to_dict("records"):
        expected = "synthetic_arid_ref" if rec["center_lon"] < -69.9 else "synthetic_humid_ref"
        assert rec["best_reference"] == expected, (rec["tile_id"], rec["center_lon"])
    assert set(descs) == set(df["tile_id"])


def test_grid_covers_bbox_without_overlap():
    tiles = make_grid([0.0, 0.0, 0.25, 0.1], 0.1)
    assert len(tiles) == 3 * 1
    assert tiles[-1]["bbox"][2] == 0.25          # last tile clipped to the region edge


if __name__ == "__main__":
    import inspect
    names = [n for n, f in globals().items() if n.startswith("test_") and inspect.isfunction(f)]
    for n in names:
        globals()[n]()
        print(f"PASS {n}")
    print(f"\n{len(names)} tests passed")
