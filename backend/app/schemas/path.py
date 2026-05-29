from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class PathRequest(BaseModel):
    lat_start: float
    lng_start: float
    lat_end:   float
    lng_end:   float


class PathStepOut(BaseModel):
    kind:        str
    description: str
    duration_s:  float
    distance_m:  float = 0.0
    line_id:     Optional[str] = None


class PathResponse(BaseModel):
    total_time_s: float
    steps:        list[PathStepOut]
    coords:       list[list[float]]   # [[lat, lng], …]
