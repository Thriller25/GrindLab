from typing import Optional

from pydantic import BaseModel

from app.schemas.calc_run import CalcRunRead
from app.schemas.calc_scenario import CalcScenarioListItem
from app.schemas.flowsheet_version import FlowsheetVersionRead


class ScenarioWithLatestRun(BaseModel):
    scenario: CalcScenarioListItem
    latest_run: Optional[CalcRunRead] = None


class FlowsheetVersionOverviewResponse(BaseModel):
    flowsheet_version: FlowsheetVersionRead
    scenarios: list[ScenarioWithLatestRun]
