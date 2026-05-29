"""GET/POST/DELETE /api/scenarios — closure management (no auth required)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.app.schemas.scenario import ScenarioCreate, ScenarioResponse
from backend.app.services.scenario import ScenarioService
from backend.app.dependencies.services import get_scenario_service

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioResponse])
def list_scenarios(service: ScenarioService = Depends(get_scenario_service)):
    return [
        ScenarioResponse(id=s.id, type=s.type, payload=s.payload)
        for s in service.list_scenarios()
    ]


@router.post("", status_code=201, response_model=ScenarioResponse)
def create_scenario(
    body: ScenarioCreate,
    service: ScenarioService = Depends(get_scenario_service),
):
    s = service.create_scenario(body.type, body.payload)
    return ScenarioResponse(id=s.id, type=s.type, payload=s.payload)


@router.delete("/{sid}", status_code=204)
def delete_scenario(sid: int, service: ScenarioService = Depends(get_scenario_service)):
    if not service.delete_scenario(sid):
        raise HTTPException(status_code=404, detail="Scenario not found")


@router.delete("", status_code=200)
def clear_scenarios(service: ScenarioService = Depends(get_scenario_service)):
    deleted = service.clear_all()
    return {"deleted": deleted}
