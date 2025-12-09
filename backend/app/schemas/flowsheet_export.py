from typing import List

from pydantic import BaseModel

from app.schemas.calc_comparison import CalcComparisonRead
from app.schemas.calc_run import CalcRunRead
from app.schemas.calc_scenario import CalcScenarioRead
from app.schemas.comment import CommentRead
from app.schemas.flowsheet import FlowsheetRead
from app.schemas.flowsheet_version import FlowsheetVersionRead
from app.schemas.plant import PlantRead
from app.schemas.unit import UnitRead


class FlowsheetVersionExportBundle(BaseModel):
    plant: PlantRead
    flowsheet: FlowsheetRead
    flowsheet_version: FlowsheetVersionRead
    units: List[UnitRead] = []
    scenarios: List[CalcScenarioRead] = []
    runs: List[CalcRunRead] = []
    comparisons: List[CalcComparisonRead] = []
    comments: List[CommentRead] = []
