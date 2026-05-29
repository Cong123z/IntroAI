"""Vienna U-Bahn Navigator — FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api import network, path, scenarios, weather
from backend.app.dependencies.services import get_pathfinder, get_scenario_service

logger = logging.getLogger(__name__)
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    required = [
        "platforms.json", "walk_nodes.json", "ride_edges.json",
        "transfer_edges.json", "entrance_edges.json", "walk_edges.json",
    ]
    missing = [f for f in required if not (DATA_DIR / f).exists()]
    if missing:
        logger.error("Data directory: %s", DATA_DIR)
        logger.error("Missing data files: %s — run scripts/build_graph.py first.", missing)
    else:
        svc = get_pathfinder()
        logger.info("PathfindingService ready: %d nodes loaded.", len(svc._nodes))
        get_scenario_service()
    yield


app = FastAPI(title="Vienna U-Bahn Navigator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(path.router)
app.include_router(network.router)
app.include_router(scenarios.router)
app.include_router(weather.router)

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
