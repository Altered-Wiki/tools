# geojson-to-lua

Converts Natural Earth 1:110m country polygons (GeoJSON) into a Lua data
module suitable for use in MediaWiki choropleth maps.

## Requirements

Python 3.6+, no external dependencies.

## Usage

```sh
# 1. Download the source data (Natural Earth 1:110m admin-0 countries)
curl -L -o ne_110m_countries.geojson \
    https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson

# 2. Convert
python3 geojson_to_lua.py ne_110m_countries.geojson > module-country-geojson.lua

# 3. Paste the contents of module-country-geojson.lua into the desired module page on your wiki.
```

## Output format

Each country is stored as a single line keyed by ISO 3166-1 alpha-2 code:

```lua
d["DE"]={t="Polygon",c={{{13.82,47.87},...}}}
d["RU"]={t="MultiPolygon",c={{{{32.52,54.41},...}},...}}
```

Short key names (`t` = type, `c` = coordinates) keep file size down.
Coordinates are rounded to 2 decimal places (sufficient for 1:110m scale).

## Skipped features

Features with no resolvable ISO 3166-1 alpha-2 code (checked across
`ISO_A2`, `ISO_A2_EH`, `ISO3166-1-Alpha-2`, `iso_a2`, skipping `-99`
sentinel values) are skipped and reported to stderr. Typically: Northern
Cyprus, Somaliland, Kosovo.
