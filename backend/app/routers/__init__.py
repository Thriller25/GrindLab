from fastapi import APIRouter

from . import (
    auth,
    calc,
    calc_comparisons,
    calc_runs,
    calc_scenarios,
    comments,
    favorites,
    me,
    projects,
)
from .flowsheet_versions import router as flowsheet_versions_router
from .flowsheets import router as flowsheets_router
from .materials import router as materials_router
from .materials_library import router as materials_library_router
from .plants import router as plants_router
from .units import router as units_router

api_router = APIRouter()
api_router.include_router(plants_router, prefix="/plants", tags=["plants"])
api_router.include_router(flowsheets_router, prefix="/flowsheets", tags=["flowsheets"])
api_router.include_router(
    flowsheet_versions_router, prefix="/flowsheet-versions", tags=["flowsheet_versions"]
)
api_router.include_router(units_router, prefix="/units", tags=["units"])
api_router.include_router(materials_router)
api_router.include_router(materials_library_router)

__all__ = [
    "api_router",
    "plants_router",
    "flowsheets_router",
    "flowsheet_versions_router",
    "units_router",
    "materials_router",
    "materials_library_router",
    "calc",
    "calc_runs",
    "calc_scenarios",
    "calc_comparisons",
    "comments",
    "me",
    "projects",
    "auth",
    "favorites",
]
