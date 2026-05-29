from functools import lru_cache
from backend.app.services.pathfinding import PathfindingService
from backend.app.services.scenario import ScenarioService


@lru_cache
def get_pathfinder() -> PathfindingService:
    return PathfindingService()


@lru_cache
def get_scenario_service() -> ScenarioService:
    return ScenarioService()
