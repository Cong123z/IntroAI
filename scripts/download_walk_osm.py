"""Download walkable OSM ways for Vienna via Overpass API."""
import json
import time
from pathlib import Path

import requests

# Try multiple mirrors in order
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

HEADERS = {
    "User-Agent": "ViennaUbahnNavigator/1.0 (educational routing project)",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
}

VIENNA_BBOX = (48.10, 16.20, 48.32, 16.58)   # south, west, north, east
OUT_FILE = (
    Path(__file__).resolve().parent.parent / "backend" / "data" / "raw" / "walk.osm.json"
)

HIGHWAY_TYPES = "|".join([
    "footway", "path", "pedestrian", "residential",
    "living_street", "unclassified", "tertiary", "secondary", "primary",
])

QUERY = (
    f'[out:json][timeout:180];'
    f'('
    f'way[highway~"^({HIGHWAY_TYPES})$"]'
    f'({VIENNA_BBOX[0]},{VIENNA_BBOX[1]},{VIENNA_BBOX[2]},{VIENNA_BBOX[3]});'
    f'>;'
    f');'
    f'out body;'
)


def try_mirror(url: str) -> requests.Response:
    print(f"  Trying {url} …")
    resp = requests.post(
        url,
        data={"data": QUERY},
        headers=HEADERS,
        timeout=300,
    )
    resp.raise_for_status()
    return resp


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    print("Querying Overpass for Vienna walking graph…")

    last_err = None
    for url in OVERPASS_MIRRORS:
        try:
            resp = try_mirror(url)
            break
        except requests.HTTPError as e:
            print(f"  ✗ HTTP {e.response.status_code} — trying next mirror")
            last_err = e
            time.sleep(2)
        except requests.RequestException as e:
            print(f"  ✗ Connection error: {e} — trying next mirror")
            last_err = e
            time.sleep(2)
    else:
        raise RuntimeError(
            f"All Overpass mirrors failed. Last error: {last_err}\n"
            "Try again in a few minutes, or see README for manual download."
        ) from last_err

    data = resp.json()
    OUT_FILE.write_text(json.dumps(data), encoding="utf-8")
    elements = len(data.get("elements", []))
    size_mb = OUT_FILE.stat().st_size / 1_048_576
    print(f"Done — {elements:,} elements, {size_mb:.1f} MB → {OUT_FILE}")


if __name__ == "__main__":
    main()
