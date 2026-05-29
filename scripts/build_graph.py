"""
Build the Vienna U-Bahn navigation graph from GTFS + OSM data.

Outputs 6 JSON files to backend/data/:
  platforms.json, walk_nodes.json, ride_edges.json,
  transfer_edges.json, entrance_edges.json, walk_edges.json

Run after:
  python scripts/download_gtfs.py
  python scripts/download_walk_osm.py
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd
from scipy.spatial import KDTree

ROOT     = Path(__file__).resolve().parent.parent
GTFS_DIR = ROOT / "backend" / "data" / "raw" / "gtfs"
OSM_FILE = ROOT / "backend" / "data" / "raw" / "walk.osm.json"
DATA_DIR = ROOT / "backend" / "data"

WALK_SPEED_MPS  = 1.4
ENTRANCE_K      = 3
ENTRANCE_R_MAX  = 150.0   # metres
TRANSFER_TIME_S = 180     # flat 3-min transfer between lines at same station
EARTH_R         = 6_371_000.0


# ── helpers ──────────────────────────────────────────────────────────────────

def haversine(lat1, lng1, lat2, lng2) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def parse_time_s(t: str) -> int:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


# ── GTFS ─────────────────────────────────────────────────────────────────────

def load_gtfs():
    routes     = pd.read_csv(GTFS_DIR / "routes.txt",     dtype=str).fillna("")
    trips      = pd.read_csv(GTFS_DIR / "trips.txt",      dtype=str).fillna("")
    stop_times = pd.read_csv(GTFS_DIR / "stop_times.txt", dtype=str).fillna("")
    stops      = pd.read_csv(GTFS_DIR / "stops.txt",      dtype=str).fillna("")

    subway  = routes[routes["route_type"] == "1"][["route_id", "route_short_name"]]
    s_trips = trips[trips["route_id"].isin(subway["route_id"])][["trip_id", "route_id"]]
    s_times = stop_times[stop_times["trip_id"].isin(s_trips["trip_id"])]

    merged = (
        s_times
        .merge(s_trips, on="trip_id")
        .merge(subway, on="route_id")
        .merge(stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]], on="stop_id")
    )
    merged["stop_lat"]      = merged["stop_lat"].astype(float)
    merged["stop_lon"]      = merged["stop_lon"].astype(float)
    merged["stop_sequence"] = merged["stop_sequence"].astype(int)
    return merged


# ── platforms ────────────────────────────────────────────────────────────────

def build_platforms(merged):
    seen: dict[tuple[str, str], int] = {}
    platforms: list[dict] = []
    pid = 1

    for _, row in merged.drop_duplicates(["stop_id", "route_short_name"]).iterrows():
        key = (row["stop_id"], row["route_short_name"])
        if key not in seen:
            seen[key] = pid
            platforms.append({
                "id":           pid,
                "station_id":   row["stop_id"],
                "station_name": row["stop_name"],
                "line_id":      row["route_short_name"],
                "lat":          row["stop_lat"],
                "lng":          row["stop_lon"],
            })
            pid += 1

    return platforms, seen


# ── ride edges ───────────────────────────────────────────────────────────────

def build_ride_edges(merged, seen):
    by_trip: dict[str, list] = defaultdict(list)
    for _, row in merged.iterrows():
        by_trip[row["trip_id"]].append(row)

    accum: dict[tuple[int, int, str], list[int]] = defaultdict(list)
    for rows in by_trip.values():
        rows_s = sorted(rows, key=lambda r: r["stop_sequence"])
        line   = rows_s[0]["route_short_name"]
        for a, b in zip(rows_s, rows_s[1:]):
            ka = (a["stop_id"], line)
            kb = (b["stop_id"], line)
            if ka not in seen or kb not in seen:
                continue
            try:
                dt = parse_time_s(b["departure_time"]) - parse_time_s(a["departure_time"])
            except Exception:
                continue
            if dt <= 0 or dt > 600:
                continue
            accum[(seen[ka], seen[kb], line)].append(dt)

    return [
        {
            "from_platform": fp,
            "to_platform":   tp,
            "travel_time_s": int(sorted(times)[len(times) // 2]),
            "line_id":       line,
        }
        for (fp, tp, line), times in accum.items()
    ]


# ── transfer edges ────────────────────────────────────────────────────────────

def build_transfer_edges(platforms):
    by_station: dict[str, list[int]] = defaultdict(list)
    for p in platforms:
        by_station[p["station_id"]].append(p["id"])

    edges = []
    for pids in by_station.values():
        if len(pids) < 2:
            continue
        for i, a in enumerate(pids):
            for b in pids[i + 1:]:
                edges.append({"from_platform": a, "to_platform": b, "transfer_time_s": TRANSFER_TIME_S})
                edges.append({"from_platform": b, "to_platform": a, "transfer_time_s": TRANSFER_TIME_S})
    return edges


# ── OSM walk graph ────────────────────────────────────────────────────────────

def build_walk_graph():
    raw   = json.loads(OSM_FILE.read_text(encoding="utf-8"))
    elems = raw.get("elements", [])

    node_by_id: dict[int, tuple[float, float]] = {}
    for e in elems:
        if e["type"] == "node" and "lat" in e:
            node_by_id[e["id"]] = (e["lat"], e["lon"])

    # Sequential IDs starting from 1_000_000 to avoid collision with platform IDs
    osm_to_wid: dict[int, int] = {}
    wid = 1_000_000
    walk_nodes: list[dict] = []
    for osm_id, (lat, lng) in node_by_id.items():
        osm_to_wid[osm_id] = wid
        walk_nodes.append({"id": wid, "lat": lat, "lng": lng})
        wid += 1

    walk_edges: list[dict] = []
    for e in elems:
        if e["type"] != "way":
            continue
        ns = e.get("nodes", [])
        for a_osm, b_osm in zip(ns, ns[1:]):
            if a_osm not in osm_to_wid or b_osm not in osm_to_wid:
                continue
            a_coord = node_by_id[a_osm]
            b_coord = node_by_id[b_osm]
            dist = haversine(a_coord[0], a_coord[1], b_coord[0], b_coord[1])
            t    = dist / WALK_SPEED_MPS
            wa   = osm_to_wid[a_osm]
            wb   = osm_to_wid[b_osm]
            walk_edges.append({"from_node": wa, "to_node": wb, "travel_time_s": t})
            walk_edges.append({"from_node": wb, "to_node": wa, "travel_time_s": t})

    return walk_nodes, walk_edges


# ── entrance edges ────────────────────────────────────────────────────────────

def build_entrance_edges(platforms, walk_nodes):
    if not walk_nodes:
        return []

    coords = [(n["lat"], n["lng"]) for n in walk_nodes]
    wids   = [n["id"] for n in walk_nodes]
    tree   = KDTree(coords)

    r_deg = ENTRANCE_R_MAX / 111_000  # approximate degree radius

    edges = []
    for p in platforms:
        dists, idxs = tree.query(
            [p["lat"], p["lng"]],
            k=min(ENTRANCE_K, len(walk_nodes)),
            distance_upper_bound=r_deg,
        )
        if not hasattr(dists, "__iter__"):
            dists, idxs = [dists], [idxs]
        for dist_deg, ki in zip(dists, idxs):
            if ki >= len(wids):
                continue
            wlat, wlng = coords[ki]
            real_dist = haversine(p["lat"], p["lng"], wlat, wlng)
            if real_dist > ENTRANCE_R_MAX:
                continue
            t = real_dist / WALK_SPEED_MPS
            edges.append({"platform_id": p["id"], "walk_node_id": wids[ki], "travel_time_s": t})

    return edges


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading GTFS …")
    merged = load_gtfs()
    print(f"  {len(merged):,} stop-time rows, {merged['route_short_name'].nunique()} lines")

    print("Building platforms …")
    platforms, seen = build_platforms(merged)
    print(f"  {len(platforms)} platforms")

    print("Building ride edges …")
    ride_edges = build_ride_edges(merged, seen)
    print(f"  {len(ride_edges)} ride edges")

    print("Building transfer edges …")
    transfer_edges = build_transfer_edges(platforms)
    print(f"  {len(transfer_edges)} transfer edges")

    print("Building walk graph from OSM …")
    walk_nodes, walk_edges = build_walk_graph()
    print(f"  {len(walk_nodes):,} walk nodes, {len(walk_edges):,} walk edges")

    print("Building entrance edges …")
    entrance_edges = build_entrance_edges(platforms, walk_nodes)
    print(f"  {len(entrance_edges)} entrance edges")

    files = {
        "platforms.json":      platforms,
        "walk_nodes.json":     walk_nodes,
        "ride_edges.json":     ride_edges,
        "transfer_edges.json": transfer_edges,
        "entrance_edges.json": entrance_edges,
        "walk_edges.json":     walk_edges,
    }
    for fname, data in files.items():
        dest = DATA_DIR / fname
        dest.write_text(json.dumps(data), encoding="utf-8")
        print(f"  Wrote {fname}  ({dest.stat().st_size / 1_048_576:.1f} MB, {len(data):,} rows)")

    print("\nBuild complete →", DATA_DIR)


if __name__ == "__main__":
    main()
