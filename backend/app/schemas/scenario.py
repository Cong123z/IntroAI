from __future__ import annotations
from pydantic import BaseModel


class ScenarioCreate(BaseModel):
    type: str     # "station" | "segment" | "line"
    payload: dict


class ScenarioResponse(BaseModel):
    id: int
    type: str
    payload: dict
