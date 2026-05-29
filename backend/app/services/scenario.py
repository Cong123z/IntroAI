"""
ScenarioService — in-memory closure store + weather condition.

ClosureMask (from pathfinding.py) tracks blocked items and the current walk speed.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import Enum

from backend.app.services.pathfinding import ClosureMask

_counter = itertools.count(1)

WALK_SPEED_CLEAR = 1.4
WALK_SPEED_RAIN  = 1.1
WALK_SPEED_SNOW  = 0.8  # Đã sửa lỗi: Giảm từ 100.0 về 0.8 để phản ánh đúng thực tế trời tuyết đi bộ chậm đi


class Weather(str, Enum):
    CLEAR = "clear"
    RAIN  = "rain"
    SNOW  = "snow"


WEATHER_SPEEDS: dict[Weather, float] = {
    Weather.CLEAR: WALK_SPEED_CLEAR,
    Weather.RAIN:  WALK_SPEED_RAIN,
    Weather.SNOW:  WALK_SPEED_SNOW,
}


@dataclass
class Scenario:
    id: int
    type: str   # "station" | "segment" | "line"
    payload: dict


class ScenarioService:

    def __init__(self):
        self._store:   dict[int, Scenario] = {}
        self._weather: Weather = Weather.CLEAR
        self._mask:    ClosureMask = ClosureMask.empty()
        self._recompile()  # Khởi tạo mask ban đầu tích hợp sẵn tốc độ CLEAR mặc định

    def list_scenarios(self) -> list[Scenario]:
        return list(self._store.values())

    def create_scenario(self, s_type: str, payload: dict) -> Scenario:
        sid = next(_counter)
        s = Scenario(id=sid, type=s_type, payload=payload)
        self._store[sid] = s
        self._recompile()
        return s

    def delete_scenario(self, sid: int) -> bool:
        if sid not in self._store:
            return False
        del self._store[sid]
        self._recompile()
        return True

    def clear_all(self) -> int:
        count = len(self._store)
        self._store.clear()
        self._recompile()
        return count

    def set_weather(self, w: Weather) -> None:
        self._weather = w
        self._recompile()  # QUAN TRỌNG: Ép hệ thống phải tạo lại mặt nạ với tốc độ thời tiết mới ngay lập tức

    def get_weather(self) -> Weather:
        return self._weather

    def get_walk_speed(self) -> float:
        return WEATHER_SPEEDS[self._weather]

    def get_mask(self) -> ClosureMask:
        return self._mask

    def _recompile(self) -> None:
        blocked_stations: set[str] = set()
        blocked_lines:    set[str] = set()
        blocked_segments: set[tuple[int, int]] = set()

        for s in self._store.values():
            if s.type == "station":
                sid = s.payload.get("station_id") or s.payload.get("id")
                if sid:
                    blocked_stations.add(str(sid))
            elif s.type == "line":
                lid = s.payload.get("line_id") or s.payload.get("id")
                if lid:
                    blocked_lines.add(str(lid))
            elif s.type == "segment":
                fp = s.payload.get("from_platform")
                tp = s.payload.get("to_platform")
                if fp is not None and tp is not None:
                    blocked_segments.add((int(fp), int(tp)))

        # Đóng gói toàn bộ thông tin chặn đường và tốc độ đi bộ động mới 
        # rồi chuyền thẳng qua cấu trúc dữ liệu của file pathfinding
        self._mask = ClosureMask(
            blocked_stations=frozenset(blocked_stations),
            blocked_lines=frozenset(blocked_lines),
            blocked_segments=frozenset(blocked_segments),
            walk_speed_mps=self.get_walk_speed(),  # ĐÃ THÊM: Đồng bộ tốc độ đi bộ theo thời tiết vào đồ thị
        )
