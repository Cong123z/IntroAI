"""
Build the Vienna U-Bahn navigation graph from GTFS + OSM data.

Outputs 6 JSON files to backend/data/:
  platforms.json, walk_nodes.json, ride_edges.json,
  transfer_edges.json, entrance_edges.json, walk_edges.json
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

WALK_SPEED_MPS  = 1.4          # m/s at baseline
ENTRANCE_K      = 3            # walk nodes to connect per platform
ENTRANCE_R_MAX  = 150.0        # metres — max snap distance
TRANSFER_TIME_S = 180          # flat 3-min transfer between lines at same station

# ─────────────────────────── helpers ────────────────────────────────────────

EARTH_R = 6_371_000.0

def haversine(lat1, lng1, lat2, lng2) -> float:
    """Great-circle distance in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


# ─────────────────────────── GTFS loading ───────────────────────────────────

def load_gtfs():
    routes     = pd.read_csv(GTFS_DIR / "routes.txt",     dtype=str).fillna("")
    trips      = pd.read_csv(GTFS_DIR / "trips.txt",      dtype=str).fillna("")
    stop_times = pd.read_csv(GTFS_DIR / "stop_times.txt", dtype=str).fillna("")
    stops      = pd.read_csv(GTFS_DIR / "stops.txt",      dtype=str).fillna("")

    # Filter subway routes only (route_type == "1")
    subway_routes = routes[routes["route_type"] == "1"][["route_id", "route_short_name"]]
    subway_trips  = trips[trips["route_id"].isin(subway_routes["route_id"])][
        ["trip_id", "route_id", "shape_id"]
    ]
    subway_times  = stop_times[stop_times["trip_id"].isin(subway_trips["trip_id"])]

    # Join everything
    merged = (
        subway_times
        .merge(subway_trips, on="trip_id")
        .merge(subway_routes, on="route_id")
        .merge(stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]], on="stop_id")
    )
    merged["stop_lat"] = merged["stop_lat"].astype(float)
    merged["stop_lon"] = merged["stop_lon"].astype(float)
    merged["stop_sequence"] = merged["stop_sequence"].astype(int)
    return merged


def parse_time_s(t: str) -> int:
    """HH:MM:SS → seconds (handles hours ≥24 for overnight trips)."""
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


# ─────────────────────────── platform building ──────────────────────────────

def build_platforms(merged: pd.DataFrame):
    """
    One platform per (stop_id, line) pair.
    Returns list of dicts: {id, station_id, station_name, line_id, lat, lng}
    """
    seen  : dict[tuple[str, str], int] = {}
    plats : list[dict] = []
    pid = 0

    for _, row in merged.drop_duplicates(["stop_id", "route_short_name"]).iterrows():
        key = (row["stop_id"], row["route_short_name"])
        if key not in seen:
            seen[key] = pid
            plats.append({
                "id":           pid,
                "station_id":   row["stop_id"],
                "station_name": row["stop_name"],
                "line_id":      row["route_short_name"],
                "lat":          row["stop_lat"],
                "lng":          row["stop_lon"],
            })
            pid += 1

    return plats, seen


# ─────────────────────────── ride edges ─────────────────────────────────────

def build_ride_edges(merged: pd.DataFrame, seen: dict[tuple[str, str], int]):
    """
    For each trip, consecutive stops → ride edge with travel_time_s.
    Uses median departure times across all trips on the same (from, to, line).
    """
    by_trip: dict[str, list] = defaultdict(list)
    for _, row in merged.iterrows():
        by_trip[row["trip_id"]].append(row)

    accum: dict[tuple[int, int, str], list[int]] = defaultdict(list)

    for rows in by_trip.values():
        rows_sorted = sorted(rows, key=lambda r: r["stop_sequence"])
        line = rows_sorted[0]["route_short_name"]
        for a, b in zip(rows_sorted, rows_sorted[1:]):
            key_a = (a["stop_id"], line)
            key_b = (b["stop_id"], line)
            if key_a not in seen or key_b not in seen:
                continue
            pid_a = seen[key_a]
            pid_b = seen[key_b]

            try:
                dt = parse_time_s(b["departure_time"]) - parse_time_s(a["departure_time"])
            except Exception:
                continue

            if dt <= 0 or dt > 600:   # sanity: 0–10 min
                continue
            accum[(pid_a, pid_b, line)].append(dt)

    edges = []
    for (fp, tp, line), times in accum.items():
        median_t = int(sorted(times)[len(times) // 2])
        edges.append({
            "from_platform": fp,
            "to_platform":   tp,
            "travel_time_s": median_t,
            "line_id":       line,
        })
    return edges


# ─────────────────────────── transfer edges ─────────────────────────────────

def build_transfer_edges(platforms: list[dict]):
    """Flat 3-min transfer between different lines at the same station."""
    by_station: dict[str, list[int]] = defaultdict(list)
    for p in platforms:
        by_station[p["station_id"]].append(p["id"])

    edges = []
    for pids in by_station.values():
        if len(pids) < 2:
            continue
        for i, a in enumerate(pids):
            for b in pids[i + 1:]:
                edges.append({
                    "from_platform":  a,
                    "to_platform":    b,
                    "transfer_time_s": TRANSFER_TIME_S,
                })
                edges.append({
                    "from_platform":  b,
                    "to_platform":    a,
                    "transfer_time_s": TRANSFER_TIME_S,
                })
    return edges


# ─────────────────────────── OSM walk graph ─────────────────────────────────

def build_walk_graph(osm_path: Path):
    """Parse Overpass JSON → walk nodes + walk edges."""
    raw   = json.loads(osm_path.read_text())
    elems = raw.get("elements", [])

    node_by_id: dict[int, dict] = {}
    for e in elems:
        if e["type"] == "node" and "lat" in e:
            node_by_id[e["id"]] = {"lat": e["lat"], "lng": e["lon"]}

    # Assign sequential IDs starting from 1_000_000 (to avoid collision with platform IDs)
    osm_to_idx: dict[int, int] = {}
    walk_nodes: list[dict] = []
    idx = 1_000_000
    for osm_id, coord in node_by_id.items():
        osm_to_idx[osm_id] = idx
        walk_nodes.append({"id": idx, "lat": coord["lat"], "lng": coord["lng"]})
        idx += 1

    walk_edges: list[dict] = []
    for e in elems:
        if e["type"] != "way":
            continue
        ns = e.get("nodes", [])
        for a_osm, b_osm in zip(ns, ns[1:]):
            if a_osm not in osm_to_idx or b_osm not in osm_to_idx:
                continue
            a_node = node_by_id[a_osm]
            b_node = node_by_id[b_osm]
            dist   = haversine(a_node["lat"], a_node["lng"], b_node["lat"], b_node["lng"])
            t      = dist / WALK_SPEED_MPS
            a_idx  = osm_to_idx[a_osm]
            b_idx  = osm_to_idx[b_osm]
            walk_edges.append({"from_node": a_idx, "to_node": b_idx, "travel_time_s": t})
            walk_edges.append({"from_node": b_idx, "to_node": a_idx, "travel_time_s": t})

    return walk_nodes, walk_edges, osm_to_idx


# ─────────────────────────── entrance edges ─────────────────────────────────

def build_entrance_edges(platforms, walk_nodes):
    """Connect each platform to the K nearest walk nodes within ENTRANCE_R_MAX."""
    if not walk_nodes:
        return []

    coords  = [(n["lat"], n["lng"]) for n in walk_nodes]
    ids     = [n["id"] for n in walk_nodes]
    tree    = KDTree(coords)

    # approximate: 1 degree lat ≈ 111 km → convert metres to degrees for radius
    r_deg = ENTRANCE_R_MAX / 111_000

    edges = []
    for p in platforms:
        dists, idxs = tree.query(
            [p["lat"], p["lng"]],
            k=min(ENTRANCE_K, len(walk_nodes)),
            distance_upper_bound=r_deg,
        )
        for dist_deg, wid in zip(
            (dists if hasattr(dists, "__iter__") else [dists]),
            (idxs  if hasattr(idxs,  "__iter__") else [idxs]),
        ):
            if wid >= len(ids):
                continue
            walk_node_id = ids[wid]
            # Real distance in metres
            wn = walk_nodes[wid]
            real_dist = haversine(p["lat"], p["lng"], wn["lat"], wn["lng"])
            if real_dist > ENTRANCE_R_MAX:
                continue
            t = real_dist / WALK_SPEED_MPS
            edges.append({
                "platform_id":  p["id"],
                "walk_node_id": walk_node_id,
                "travel_time_s": t,
            })
    return edges


# ─────────────────────────── main ────────────────────────────────────────────

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading GTFS …")
    merged = load_gtfs()
    print(f"  {len(merged):,} stop-time rows across {merged['route_short_name'].nunique()} lines")

    print("Building platforms …")
    platforms, seen = build_platforms(merged)
    print(f"  {len(platforms)} platform nodes")

    print("Building ride edges …")
    ride_edges = build_ride_edges(merged, seen)
    print(f"  {len(ride_edges)} ride edges")

    print("Building transfer edges …")
    transfer_edges = build_transfer_edges(platforms)
    print(f"  {len(transfer_edges)} transfer edges")

    print("Building walk graph from OSM …")
    walk_nodes, walk_edges, _ = build_walk_graph(OSM_FILE)
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
        with open(dest, "w") as f:
            json.dump(data, f)
        size_mb = dest.stat().st_size / 1_048_576
        print(f"  Wrote {fname} ({size_mb:.1f} MB, {len(data):,} rows)")

    print("\nBuild complete — 6 JSON files in", DATA_DIR)


if __name__ == "__main__":
    main()
