"""GET /api/network — stations and segments for map rendering (reads JSON)."""
from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

DATA_DIR = Path(__file__).resolve().parents[3] / "backend" / "data"
router   = APIRouter(prefix="/api", tags=["network"])


@router.get("/network")
def get_network():
    platforms  = json.loads((DATA_DIR / "platforms.json").read_text())
    ride_edges = json.loads((DATA_DIR / "ride_edges.json").read_text())

    stations_map: dict[str, dict] = {}
    for p in platforms:
        sid = p["station_id"]
        if sid not in stations_map:
            stations_map[sid] = {
                "id":    sid,
                "name":  p["station_name"],
                "lat":   p["lat"],
                "lng":   p["lng"],
                "lines": [],
            }
        if p["line_id"] not in stations_map[sid]["lines"]:
            stations_map[sid]["lines"].append(p["line_id"])

    plat_by_id = {p["id"]: p for p in platforms}
    seen_segs: set[tuple[str, str, str]] = set()
    segments = []
    for e in ride_edges:
        fp = plat_by_id.get(e["from_platform"])
        tp = plat_by_id.get(e["to_platform"])
        if not fp or not tp:
            continue
        key  = (e["line_id"], fp["station_id"], tp["station_id"])
        rkey = (e["line_id"], tp["station_id"], fp["station_id"])
        if key in seen_segs or rkey in seen_segs:
            continue
        seen_segs.add(key)
        segments.append({
            "line_id":      e["line_id"],
            "from_lat":     fp["lat"],
            "from_lng":     fp["lng"],
            "to_lat":       tp["lat"],
            "to_lng":       tp["lng"],
            "from_station": fp["station_name"],
            "to_station":   tp["station_name"],
        })

    return {"stations": list(stations_map.values()), "segments": segments}


@router.get("/network/walk-bounds")
def get_walk_bounds():
    walk_nodes = json.loads((DATA_DIR / "walk_nodes.json").read_text())
    if not walk_nodes:
        raise HTTPException(status_code=404, detail="No walk nodes found")

    lats = [node["lat"] for node in walk_nodes]
    lngs = [node["lng"] for node in walk_nodes]
    return {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lng": min(lngs),
        "max_lng": max(lngs),
    }
