from typing import Optional

from app.schemas.calc_run import CalcRunRead
from app.schemas.calc_scenario import CalcScenarioListItem
from app.schemas.flowsheet_version import FlowsheetVersionRead
from pydantic import BaseModel


class ScenarioWithLatestRun(BaseModel):
    scenario: CalcScenarioListItem
    latest_run: Optional[CalcRunRead] = None


class FlowsheetVersionOverviewResponse(BaseModel):
    flowsheet_version: FlowsheetVersionRead
    scenarios: list[ScenarioWithLatestRun]
