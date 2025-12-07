from fastapi import APIRouter

from .plants import router as plants_router
from .flowsheets import router as flowsheets_router
from .flowsheet_versions import router as flowsheet_versions_router
from .units import router as units_router

api_router = APIRouter()
api_router.include_router(plants_router, prefix="/plants", tags=["plants"])
api_router.include_router(flowsheets_router, prefix="/flowsheets", tags=["flowsheets"])
api_router.include_router(flowsheet_versions_router, prefix="/flowsheet-versions", tags=["flowsheet_versions"])
api_router.include_router(units_router, prefix="/units", tags=["units"])
