"""Download walkable OSM ways for Vienna via Overpass API."""
import json
from pathlib import Path

import requests

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "vienna-ubahn-navigator/1.0 (+https://github.com/yourname/vienna-ubahn-navigator)",
}
VIENNA_BBOX = (48.10, 16.20, 48.32, 16.58)   # south, west, north, east
OUT_FILE = (
    Path(__file__).resolve().parent.parent / "backend" / "data" / "raw" / "walk.osm.json"
)

HIGHWAY_TYPES = "|".join([
    "footway", "path", "pedestrian", "residential",
    "living_street", "unclassified", "tertiary", "secondary", "primary",
])

QUERY = f"""
[out:json][timeout:180];
(
  way[highway~"^({HIGHWAY_TYPES})$"]
      ({VIENNA_BBOX[0]},{VIENNA_BBOX[1]},{VIENNA_BBOX[2]},{VIENNA_BBOX[3]});
  >;
);
out body;
"""


def fetch_overpass_json():
    for url in OVERPASS_URLS:
        print(f"Querying {url} for Vienna walking graph…")
        try:
            resp = requests.post(url, data={"data": QUERY}, timeout=300, headers=HEADERS)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            print(f"  → failed: {exc}")
    raise RuntimeError("All Overpass endpoints failed. Check your network and try again.")


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_overpass_json()
    OUT_FILE.write_text(json.dumps(data))
    elements = len(data.get("elements", []))
    size_mb = OUT_FILE.stat().st_size / 1_048_576
    print(f"Done — {elements:,} elements, {size_mb:.1f} MB → {OUT_FILE}")


if __name__ == "__main__":
    main()
