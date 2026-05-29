"""POST /api/path — find optimal route between two lat/lng points."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.app.schemas.path import PathRequest, PathResponse, PathStepOut
from backend.app.services.pathfinding import PathfindingService, PathNotFoundError
from backend.app.services.scenario import ScenarioService
from backend.app.dependencies.services import get_pathfinder, get_scenario_service

router = APIRouter(prefix="/api", tags=["path"])


@router.post("/path", response_model=PathResponse)
def find_path(
    req: PathRequest,
    pathfinder: PathfindingService = Depends(get_pathfinder),
    scenarios:  ScenarioService   = Depends(get_scenario_service),
):
    try:
        result = pathfinder.find_path(
            lat_start=req.lat_start,
            lng_start=req.lng_start,
            lat_end=req.lat_end,
            lng_end=req.lng_end,
            closures=scenarios.get_mask(),
        )
    except PathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    steps_out = [
        PathStepOut(
            kind=s.kind,
            description=s.description,
            duration_s=s.duration_s,
            distance_m=s.distance_m,
            line_id=s.line_id,
        )
        for s in result.steps
    ]
    return PathResponse(
        total_time_s=result.total_time_s,
        steps=steps_out,
        coords=[[lat, lng] for lat, lng in result.coords],
    )
