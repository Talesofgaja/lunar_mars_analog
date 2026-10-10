"""Tiling, scoring and ranking for a region of interest."""
import numpy as np
import pandas as pd
from .descriptors import describe_tile
from .similarity import best_reference

CRITERIA = ("morphometric", "spectral", "climate")


def make_grid(bbox, tile_size_deg):
    """Split bbox = [lon_min, lat_min, lon_max, lat_max] into square tiles."""
    lon0, lat0, lon1, lat1 = bbox
    tiles = []
    for i, lat in enumerate(np.arange(lat0, lat1, tile_size_deg)):
        for j, lon in enumerate(np.arange(lon0, lon1, tile_size_deg)):
            tiles.append({
                "tile_id": f"r{i:03d}c{j:03d}",
                "bbox": [round(lon, 6), round(lat, 6),
                         round(min(lon + tile_size_deg, lon1), 6),
                         round(min(lat + tile_size_deg, lat1), 6)],
            })
    return tiles


def _characterization(desc):
    """Flatten a descriptor into the key statistics reported in the ranked table."""
    m = desc.get("morphometric", {})
    row = {
        "median_slope_deg": m.get("median_slope_deg"),
        "roughness_m": m.get("roughness_m"),
        "relief_m": m.get("relief_m"),
    }
    row.update(desc.get("spectral", {}))
    row.update(desc.get("climate", {}))
    return row


def run_search(cfg, refs, tile_provider):
    """Score every tile in the region against every reference.

    tile_provider(bbox) -> dict with optional keys dem, dx_m, dy_m, bands, climate,
    or None if no data exists for that tile. Swap providers to go from offline
    synthetic data to live Planetary Computer data.

    Returns (ranked DataFrame, {tile_id: descriptor}).
    """
    rows, descriptors = [], {}
    for tile in make_grid(cfg["region"]["bbox"], cfg["tile_size_deg"]):
        data = tile_provider(tile["bbox"])
        if data is None:
            continue
        desc = describe_tile(data)
        if not desc:
            continue
        match = best_reference(desc, refs, cfg)
        if match is None:
            continue

        lon0, lat0, lon1, lat1 = tile["bbox"]
        descriptors[tile["tile_id"]] = desc
        row = {
            "tile_id": tile["tile_id"],
            "lon_min": lon0, "lat_min": lat0, "lon_max": lon1, "lat_max": lat1,
            "center_lon": round((lon0 + lon1) / 2, 5),
            "center_lat": round((lat0 + lat1) / 2, 5),
            "best_reference": match["reference"],
            "best_reference_body": match["body"],
            "composite_score": round(match["composite"], 4),
        }
        for c in CRITERIA:
            row[f"score_{c}"] = round(match["scores"][c], 4) if c in match["scores"] else None
        row.update(_characterization(desc))
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("composite_score", ascending=False).reset_index(drop=True)
    return df, descriptors
