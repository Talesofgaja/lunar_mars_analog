"""Command-line entry point.

  python run_analog_search.py                       # live data (needs network + built references)
  python run_analog_search.py --synthetic           # offline demo with synthetic terrain
"""
import argparse
import json
from pathlib import Path

from analog_finder.pipeline import run_search
from analog_finder.outputs import export_results, write_map


def main():
    ap = argparse.ArgumentParser(description="Rank Earth analog sites for lunar/Martian landing studies.")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--refs", default="reference_sites.json")
    ap.add_argument("--synthetic", action="store_true",
                    help="use offline synthetic terrain and in-memory references")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    if args.synthetic:
        from analog_finder.synthetic import make_synthetic_provider, synthetic_reference_sites
        refs = synthetic_reference_sites()
        provider = make_synthetic_provider()
    else:
        from analog_finder.references import load_reference_sites
        from analog_finder.ingest import make_live_provider
        refs = load_reference_sites(args.refs)
        provider = make_live_provider(cfg["date_range"], cfg.get("max_cloud_cover", 20))

    df, descriptors = run_search(cfg, refs, provider)
    out = Path(cfg["output_dir"])
    export_results(df, descriptors, out, cfg["top_n"])
    write_map(df, out / "candidates_map.html")

    if df.empty:
        print("No candidate tiles produced results. Check the bbox and data availability.")
    else:
        cols = ["tile_id", "center_lat", "center_lon", "composite_score",
                "score_morphometric", "score_spectral", "score_climate", "best_reference"]
        print(df[cols].head(cfg["top_n"]).to_string(index=False))
        print(f"\nWrote results to {out.resolve()}")


if __name__ == "__main__":
    main()
