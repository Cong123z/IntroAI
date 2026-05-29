"""GET/PUT /api/weather — weather condition endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.services.scenario import ScenarioService, Weather
from backend.app.dependencies.services import get_scenario_service

router = APIRouter(prefix="/api/weather", tags=["weather"])


class WeatherRequest(BaseModel):
    condition: str   # "clear" | "rain" | "snow"


@router.get("")
def get_weather(service: ScenarioService = Depends(get_scenario_service)):
    return {"condition": service.get_weather().value}


@router.put("")
def set_weather(
    body: WeatherRequest,
    service: ScenarioService = Depends(get_scenario_service),
):
    try:
        w = Weather(body.condition)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown condition '{body.condition}'. Use: clear, rain, snow",
        )
    service.set_weather(w)
    return {"condition": w.value}
