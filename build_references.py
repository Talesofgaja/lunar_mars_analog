"""Compute reference descriptors from DEM GeoTIFFs listed in reference_sites.json.

  python build_references.py reference_sites.json
Writes the file in place. Sites without a dem_path keep their existing descriptor.
"""
import sys
from analog_finder.references import build_reference_file

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "reference_sites.json"
    out = build_reference_file(path)
    print(f"Updated descriptors in {out}")
