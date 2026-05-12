#!/usr/bin/env python3
"""
Convert Natural Earth 1:110m country polygons (GeoJSON) into a Lua data
module suitable for use in MediaWiki choropleth maps.

Usage:
    # 1. Download the source file (Natural Earth 1:110m):
    curl -L -o ne_110m_countries.geojson \
        https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson

    # 2. Convert:
    python3 geojson_to_lua.py ne_110m_countries.geojson > module-country-geojson.lua

    # 3. Paste the contents of module-country-geojson.lua into the desired module page on your wiki.
"""

import json
import sys


def num(n):
    """Format a coordinate number at 2 decimal places — sufficient for 1:110m scale maps."""
    r = round(n, 2)
    if r == int(r):
        return str(int(r))
    return f"{r:.2f}".rstrip("0")


def coords_to_lua(obj):
    """Recursively convert GeoJSON coordinate arrays to Lua table literals."""
    if isinstance(obj[0], (int, float)):
        return "{" + "," .join(num(c) for c in obj) + "}"
    return "{" + ",".join(coords_to_lua(c) for c in obj) + "}"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "countries.geojson"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: file not found: {path}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    out = [
        "-- Auto-generated from the geo-countries dataset (Natural Earth 1:110m).",
        "-- Do not edit manually. Re-run geojson_to_lua.py to regenerate.",
        "-- Source: https://github.com/nvkelso/natural-earth-vector (1:110m)",
        "local d = {}",
    ]

    skipped = []
    for feature in data["features"]:
        props = feature.get("properties", {})
        iso = ""
        for key in ("ISO3166-1-Alpha-2", "ISO_A2", "ISO_A2_EH", "iso_a2"):
            val = (props.get(key) or "").strip()
            if val and val not in ("-99", "-1"):
                iso = val
                break
        if not iso:
            name = props.get("ADMIN") or props.get("name") or "unknown"
            skipped.append(name)
            continue
        geo = feature["geometry"]
        geo_type = geo["type"]
        coords_lua = coords_to_lua(geo["coordinates"])
        # t = type, c = coordinates  (short keys keep file size down)
        out.append(f'd["{iso}"]={{t="{geo_type}",c={coords_lua}}}')

    out.append("return d")
    print("\n".join(out))

    if skipped:
        print(f"Skipped {len(skipped)} features with no valid ISO_A2: {', '.join(skipped)}", file=sys.stderr)


if __name__ == "__main__":
    main()
