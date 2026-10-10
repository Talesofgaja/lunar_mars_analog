# Lunar and Martian Analog Site Finder (prototype)

Screens a region of Earth for terrestrial analogs of lunar and Martian landing sites. It scores each tile on morphometry, surface spectra and climate against reference sites on the Moon and Mars, then ranks the tiles and exports the results.

## Status: what has been tested

| Component | Status |
|---|---|
| Morphometry, spectral and climate descriptors, similarity, composite ranking | **Tested offline** (7 unit and integration tests pass) |
| Tiling, pipeline, CSV / GeoJSON / JSON export, CLI, notebook code | **Tested offline** on synthetic terrain |
| Live Planetary Computer and NASA POWER ingestion (`ingest.py`) | **Written but not run.** The build environment had no network access. Expect to fix small API details on first run. |
| Lunar and Martian reference descriptors | **Not built.** The coordinates are approximate, and the DEM crops must be downloaded from PDS / Moon Trek / Mars Trek. Spectral and climate fields are placeholders. |

Treat the first live run as a shakedown, not a validated result.

## Project layout

```
lunar_mars_analog_finder/
├── analog_search.ipynb        # main notebook (offline by default)
├── run_analog_search.py       # command-line entry point
├── build_references.py        # computes reference descriptors from DEM GeoTIFFs
├── config.json                # region, weights, similarity scales, output settings
├── reference_sites.json       # lunar and Martian reference sites
├── requirements.txt
├── analog_finder/
│   ├── descriptors.py         # tile data -> morphometric / spectral / climate descriptors
│   ├── similarity.py          # per-criterion scores in [0,1] and the composite score
│   ├── pipeline.py            # tiling, scoring loop, ranked table
│   ├── references.py          # reference loading and DEM-based descriptor building
│   ├── ingest.py              # live Planetary Computer and NASA POWER access
│   ├── synthetic.py           # offline test terrain
│   └── outputs.py             # CSV, GeoJSON, JSON summary, Folium map
├── tests/test_synthetic_pipeline.py
└── outputs/                   # example run on synthetic terrain (not real data)
```

## 1. Environment setup

Python 3.10 or later is recommended.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

The offline path needs only `numpy`, `scipy` and `pandas`. The live path also needs `requests`, `pystac-client`, `planetary-computer` and `odc-stac`. `rasterio` is needed to build references from GeoTIFFs. `folium` adds the interactive map.

## 2. Data authentication

- **Microsoft Planetary Computer** (Copernicus DEM GLO-30, Sentinel-2 L2A): no account or API key. `planetary_computer.sign_inplace` attaches the access tokens automatically.
- **NASA POWER**: no key. Requests are cached per 0.1° cell.
- **Planetary bodies (LOLA, MOLA, Diviner, CRISM, THEMIS)**: not on Planetary Computer. Download DEM GeoTIFFs from [Moon Trek](https://trek.nasa.gov/moon/) or [Mars Trek](https://trek.nasa.gov/mars/) and crop them to about 10–20 km around each site, e.g. with `gdal_translate -projwin`. Put the crops in `data/refs/`, matching the `dem_path` values in `reference_sites.json`.

Google Earth Engine was considered and deliberately not used. Planetary Computer needs no registration for these collections, so it is the lower-friction starting point. Porting the ingest layer to Earth Engine would only touch `ingest.py`.

## 3. Quick start

Offline check (no network, a few seconds):

```bash
python tests/test_synthetic_pipeline.py
python run_analog_search.py --synthetic
```

Live run:

```bash
python build_references.py reference_sites.json   # after the DEM crops are in place
python run_analog_search.py                        # uses config.json region and date range
```

Notebook: open `analog_search.ipynb` from the project root. Keep `USE_SYNTHETIC = True` for the offline demo, or set it to `False` for live data.

Outputs are written to `outputs/`:
- `ranked_candidates.csv`: every tile with per-criterion scores, composite score, best-matching reference and key statistics
- `candidates.geojson`: one polygon per tile, with all columns as properties
- `top_candidates_summary.json`: full descriptors (including slope histograms) for the top N tiles
- `candidates_map.html`: interactive map (if `folium` is installed)

## 4. Changing the region, weights or references

- **Region**: edit `region.bbox` (`[lon_min, lat_min, lon_max, lat_max]`) and `tile_size_deg` in `config.json`.
- **Weights**: edit `weights`. They are renormalised over the criteria that a reference supports, so a lunar reference with no climate data is scored on morphometry and spectra only.
- **Reference sites**: add or edit entries in `reference_sites.json`. Each entry needs `name`, `body`, `lon`, `lat` and `dem_path`. Optional `spectral` and `climate` objects supply values from other instruments. Then run `python build_references.py reference_sites.json`.
- **Similarity scales**: `morph_scales`, `spectral_scales` and `climate_scales` set the sensitivity of each metric. A scale is the difference at which similarity falls to about 37% (1/e).

## 5. Adding a new criterion or data layer

1. **Descriptor**: write a function in `analog_finder/descriptors.py` that turns raw arrays into a dict of scalars or arrays. Add it to `describe_tile()`.
2. **Ingest**: have the tile provider in `ingest.py` (or your own provider) return the new raw data under a key.
3. **Similarity**: write a scoring function in `similarity.py` that returns a value in [0, 1] or `None`. Register it in `score_against_reference()`.
4. **Config and ranking**: add the criterion to `weights` and `CRITERIA` in `pipeline.py`, and give it a scale in `config.json` if it uses `keyed_similarity`.

Nothing else changes. The ranking, export and map code handle any criterion that appears in `CRITERIA`.

## 6. Limitations

- **Spectral comparison is weak across instruments.** Sentinel-2 band ratios are compared with indices computed from CRISM, THEMIS or Clementine data. These differ in band centres and calibration, so Mars and Moon spectral values must be computed with matching definitions before the scores mean much. The current reference spectral values are null placeholders.
- **Climate is approximate.** NASA POWER annual means are at about 0.5° resolution, and the temperature range is derived from annual means of daily maxima and minima. Mars and Moon climate values are placeholders. The Moon has no atmosphere, so the climate criterion does not apply there.
- **Sentinel-2 reflectance** uses DN/10000 and ignores the post-2022 baseline offset (−1000). The effect on the ratios is small, but it is not zero.
- **Morphometry depends on DEM resolution.** Copernicus DEM (30 m) and LOLA or MOLA (about 60 m to 200 m) do not measure the same roughness. A candidate tile at 30 m will look rougher than a reference at 200 m. Compare at a common scale, or treat the roughness term as relative.
- **Composite scores are not comparable across references** when they support different criteria, because the weights are renormalised. Check `score_*` columns before ranking across bodies.
- **No accessibility filter, resource layer or machine-learning ranking yet.** The architecture below is set up for these.
- **Synthetic demo outputs in `outputs/` are not real results.** They come from the offline generator and only show the file formats.

## 7. Architecture and path to a full system

```
 reference DEMs (PDS / Trek) ──► build_references ──► reference descriptors (JSON)
                                                             │
 Planetary Computer / POWER ──► ingest (tile provider) ──► describe_tile ──► similarity ──► ranking ──► outputs
                                                                                 ▲
                                                              config.json (weights, scales)
```

Each stage is a separate function with a plain-dict interface, so stages can be swapped independently:

- **Higher-resolution analysis**: swap the tile provider for an HR DEM source or a stereo-derived DSM, and add a tile-level crater-count or boulder-density descriptor.
- **Resource layer**: add a permanently-shadowed-region descriptor from DEM illumination modelling, and a surface moisture or permafrost descriptor on Earth from ERA5 and permafrost maps.
- **Accessibility filter**: a hard constraint applied after scoring, using slope limits and distance to roads or airports from OpenStreetMap.
- **Machine-learning ranking**: store the per-criterion scores as features, label known good analogs, and train a random forest or gradient-boosted model. The current composite weights become the prior.
- **Field campaign planning**: export the top-ranked tiles as a GeoPackage with waypoint and logistics attributes, and add a travel-cost layer.

Two parts would need engineering work for a production system: caching tiles to disk (the live path re-downloads on each run) and parallel tile processing (the loop is sequential).
#   l u n a r _ m a r s _ a n a l o g  
 