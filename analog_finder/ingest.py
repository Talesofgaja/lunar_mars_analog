"""Live data access (needs network):
  - Copernicus DEM GLO-30 and Sentinel-2 L2A via Microsoft Planetary Computer (no API key)
  - NASA POWER climatology API (no API key)

Install: pip install pystac-client planetary-computer odc-stac requests
"""
import math
import requests
from .descriptors import climate_descriptor

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
POWER_CLIM_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
DEG_TO_M = 111320.0
RES_DEG = 0.00027                  # about 30 m at the equator
S2_BANDS = ["B02", "B04", "B08", "B11", "B12"]
_power_cache = {}


def _catalog():
    import pystac_client
    import planetary_computer
    return pystac_client.Client.open(PC_STAC_URL, modifier=planetary_computer.sign_inplace)


def fetch_dem(bbox, catalog):
    """Copernicus DEM GLO-30 over bbox. Returns dict with dem, dx_m, dy_m, or None."""
    import odc.stac
    items = list(catalog.search(collections=["cop-dem-glo-30"], bbox=bbox).items())
    if not items:
        return None
    ds = odc.stac.load(items, bands=["data"], bbox=bbox, crs="EPSG:4326",
                       resolution=(-RES_DEG, RES_DEG))
    da = ds["data"]
    if "time" in da.dims:
        da = da.isel(time=0)
    dy_m = RES_DEG * DEG_TO_M
    dx_m = dy_m * math.cos(math.radians((bbox[1] + bbox[3]) / 2))
    return {"dem": da.values.astype(float), "dx_m": dx_m, "dy_m": dy_m}


def fetch_sentinel2_median(bbox, date_range, max_cloud, catalog):
    """Per-band median reflectance over low-cloud scenes. Returns dict of arrays, or None."""
    import odc.stac
    items = list(catalog.search(
        collections=["sentinel-2-l2a"], bbox=bbox, datetime=date_range,
        query={"eo:cloud_cover": {"lt": max_cloud}}).items())
    if not items:
        return None
    ds = odc.stac.load(items, bands=S2_BANDS, bbox=bbox, crs="EPSG:4326",
                       resolution=(-RES_DEG, RES_DEG))
    med = ds.median("time", skipna=True).compute()
    # DN to reflectance. Baseline offsets (-1000 after 2022) are ignored: small effect on ratios.
    return {b: med[b].values.astype(float) / 10000.0 for b in S2_BANDS}


def fetch_power_climate(lon, lat):
    """Annual climatology from NASA POWER at a point, as a climate descriptor. Cached per 0.1 deg."""
    key = (round(lon, 1), round(lat, 1))
    if key not in _power_cache:
        r = requests.get(POWER_CLIM_URL, timeout=60, params={
            "parameters": "T2M_MAX,T2M_MIN,PRECTOTCORR",
            "community": "RE", "longitude": lon, "latitude": lat, "format": "JSON"})
        r.raise_for_status()
        p = r.json()["properties"]["parameter"]
        _power_cache[key] = climate_descriptor(
            temp_max_c=float(p["T2M_MAX"]["ANN"]),
            temp_min_c=float(p["T2M_MIN"]["ANN"]),
            precip_mm_day=float(p["PRECTOTCORR"]["ANN"]))
    return _power_cache[key]


def make_live_provider(date_range, max_cloud=20):
    """Return tile_provider(bbox) that pulls DEM, Sentinel-2 and climate for each tile."""
    catalog = _catalog()

    def provider(bbox):
        lon_c, lat_c = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        data = {}
        dem = fetch_dem(bbox, catalog)
        if dem:
            data.update(dem)
        bands = fetch_sentinel2_median(bbox, date_range, max_cloud, catalog)
        if bands:
            data["bands"] = bands
        data["climate"] = fetch_power_climate(lon_c, lat_c)
        return data if ("dem" in data or "bands" in data) else None
    return provider
