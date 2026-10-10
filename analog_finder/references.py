"""Load reference-site descriptors and build them from planetary DEMs."""
import json
from pathlib import Path
import numpy as np
from .descriptors import describe_tile, climate_descriptor


def load_reference_sites(path):
    """Read reference_sites.json. Every entry must already have a descriptor."""
    sites = json.loads(Path(path).read_text())
    refs = []
    for s in sites:
        if not s.get("descriptor"):
            raise ValueError(
                f"Reference '{s['name']}' has no descriptor yet. "
                f"Run: python build_references.py reference_sites.json")
        refs.append({"name": s["name"], "body": s["body"],
                     "lon": s["lon"], "lat": s["lat"], "descriptor": s["descriptor"]})
    return refs


def _pixel_size_m(src):
    """Ground pixel size in metres for a rasterio dataset (geographic or projected CRS)."""
    a, e = abs(src.transform.a), abs(src.transform.e)
    if src.crs is not None and src.crs.is_geographic:
        lat = (src.bounds.bottom + src.bounds.top) / 2.0
        return a * 111320.0 * np.cos(np.radians(lat)), e * 110574.0
    return a, e          # projected CRS (e.g. polar stereographic) already in metres


def build_descriptor_from_geotiff(path):
    """Morphometric descriptor from a DEM GeoTIFF (LOLA, MOLA, Copernicus, etc.)."""
    import rasterio
    with rasterio.open(path) as src:
        elev = src.read(1).astype(float)
        if src.nodata is not None:
            elev[elev == src.nodata] = np.nan
        dx_m, dy_m = _pixel_size_m(src)
    return describe_tile({"dem": elev, "dx_m": dx_m, "dy_m": dy_m})


def build_reference_file(in_path, out_path=None):
    """Fill in descriptors for every site that has a dem_path.

    Spectral and climate values come from the optional 'spectral' and
    'climate' fields of each entry. Those come from other instruments
    (CRISM, THEMIS, Diviner), so they are entered by hand after calibration.
    """
    in_path = Path(in_path)
    sites = json.loads(in_path.read_text())
    for s in sites:
        desc = {}
        if s.get("dem_path"):
            desc.update(build_descriptor_from_geotiff(s["dem_path"]))
        if s.get("spectral"):
            desc["spectral"] = s["spectral"]
        if s.get("climate"):
            desc["climate"] = climate_descriptor(**s["climate"])
        s["descriptor"] = desc or None
    out_path = Path(out_path or in_path)
    out_path.write_text(json.dumps(sites, indent=2))
    return out_path
