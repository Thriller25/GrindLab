from fastapi import APIRouter

from .plants import router as plants_router
from .flowsheets import router as flowsheets_router
from .flowsheet_versions import router as flowsheet_versions_router
from .units import router as units_router
from . import calc
from . import calc_runs
from . import calc_scenarios
from . import calc_comparisons
from . import comments

api_router = APIRouter()
api_router.include_router(plants_router, prefix="/plants", tags=["plants"])
api_router.include_router(flowsheets_router, prefix="/flowsheets", tags=["flowsheets"])
api_router.include_router(flowsheet_versions_router, prefix="/flowsheet-versions", tags=["flowsheet_versions"])
api_router.include_router(units_router, prefix="/units", tags=["units"])

__all__ = [
    "api_router",
    "plants_router",
    "flowsheets_router",
    "flowsheet_versions_router",
    "units_router",
    "calc",
    "calc_runs",
    "calc_scenarios",
    "calc_comparisons",
    "comments",
]
