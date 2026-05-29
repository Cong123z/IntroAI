"""Download Wiener Linien GTFS feed and extract relevant files."""
import io
import zipfile
from pathlib import Path

import requests

GTFS_URL = "https://www.wienerlinien.at/ogd_realtime/doku/ogd/gtfs/gtfs.zip"
OUT_DIR = Path(__file__).resolve().parent.parent / "backend" / "data" / "raw" / "gtfs"
KEEP_FILES = {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading GTFS from {GTFS_URL} …")
    resp = requests.get(GTFS_URL, timeout=120)
    resp.raise_for_status()
    print(f"Downloaded {len(resp.content) / 1_048_576:.1f} MB")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in zf.namelist():
            if name in KEEP_FILES:
                dest = OUT_DIR / name
                dest.write_bytes(zf.read(name))
                print(f"  Extracted {name} ({dest.stat().st_size:,} bytes)")

    print("Done — GTFS files in", OUT_DIR)


if __name__ == "__main__":
    main()
