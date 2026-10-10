"""Export ranked results as CSV, GeoJSON, a JSON characterization summary, and an optional map."""
import json
from pathlib import Path
import pandas as pd

BBOX_COLS = ("lon_min", "lat_min", "lon_max", "lat_max")


def _json_default(o):
    return o.item() if hasattr(o, "item") else str(o)


def export_results(df, descriptors, out_dir, top_n=10):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    df.to_csv(out / "ranked_candidates.csv", index=False)

    # GeoJSON: one polygon per candidate tile, with scores as properties.
    features = []
    for rec in df.to_dict("records"):
        x0, y0, x1, y1 = rec["lon_min"], rec["lat_min"], rec["lon_max"], rec["lat_max"]
        props = {k: (None if pd.isna(v) else v) for k, v in rec.items() if k not in BBOX_COLS}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]},
            "properties": props,
        })
    (out / "candidates.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": features}, default=_json_default, indent=2))

    # Characterization summary for the top candidates (full descriptors, including histograms).
    top = df.head(top_n)
    summary = [{"tile_id": rec["tile_id"], "composite_score": rec["composite_score"],
                "best_reference": rec["best_reference"],
                "characterization": descriptors.get(rec["tile_id"], {})}
               for rec in top.to_dict("records")]
    (out / "top_candidates_summary.json").write_text(
        json.dumps(summary, default=_json_default, indent=2))
    return out


def write_map(df, out_path):
    """Interactive Folium map of candidate tiles. Skipped if folium is not installed."""
    try:
        import folium
    except ImportError:
        return None
    if df.empty:
        return None
    m = folium.Map(location=[df["center_lat"].mean(), df["center_lon"].mean()], zoom_start=9)
    lo, hi = df["composite_score"].min(), df["composite_score"].max()
    for rec in df.to_dict("records"):
        frac = 0.5 if hi == lo else (rec["composite_score"] - lo) / (hi - lo)
        colour = "#2b8cbe" if frac > 0.5 else "#fdae61"
        folium.Rectangle(
            bounds=[[rec["lat_min"], rec["lon_min"]], [rec["lat_max"], rec["lon_max"]]],
            color=colour, fill=True, fill_opacity=0.35,
            tooltip=f"{rec['tile_id']} | score {rec['composite_score']} | "
                    f"best match: {rec['best_reference']}",
        ).add_to(m)
    m.save(str(out_path))
    return out_path
