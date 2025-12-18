from typing import Optional, List
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class GrindMvpFeed(BaseModel):
    tonnage_tph: float
    p80_mm: float
    density_t_per_m3: float

    @model_validator(mode="after")
    def validate_positive(self):
        if self.tonnage_tph <= 0:
            raise ValueError("feed.tonnage_tph must be positive")
        if self.p80_mm <= 0:
            raise ValueError("feed.p80_mm must be positive")
        return self


class GrindMvpMill(BaseModel):
    type: str
    power_installed_kw: float
    power_draw_kw: float
    ball_charge_percent: float
    speed_percent_critical: float

    @model_validator(mode="after")
    def validate_positive(self):
        if self.power_installed_kw <= 0:
            raise ValueError("mill.power_installed_kw must be positive")
        return self


class GrindMvpClassifier(BaseModel):
    type: str
    cut_size_p80_mm: float
    circulating_load_percent: float


class GrindMvpOptions(BaseModel):
    use_baseline_run_id: Optional[UUID] = None


class GrindMvpInput(BaseModel):
    model_version: str = Field(default="grind_mvp_v1")
    plant_id: str | int
    flowsheet_version_id: str | int
    project_id: Optional[int] = None
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    feed: GrindMvpFeed
    mill: GrindMvpMill
    classifier: GrindMvpClassifier
    options: GrindMvpOptions = Field(default_factory=GrindMvpOptions)


class GrindMvpKPI(BaseModel):
    throughput_tph: float
    product_p80_mm: float
    specific_energy_kwh_per_t: float
    circulating_load_percent: float
    mill_utilization_percent: float


class GrindMvpSizePoint(BaseModel):
    size_mm: float
    cum_percent: float


class GrindMvpSizeDistribution(BaseModel):
    feed: List[GrindMvpSizePoint]
    product: List[GrindMvpSizePoint]


class GrindMvpBaselineComparison(BaseModel):
    baseline_run_id: UUID
    throughput_delta_tph: Optional[float] = None
    product_p80_delta_mm: Optional[float] = None
    specific_energy_delta_kwhpt: Optional[float] = None
    throughput_delta_percent: Optional[float] = None
    specific_energy_delta_percent: Optional[float] = None


class GrindMvpResult(BaseModel):
    model_version: str = Field(default="grind_mvp_v1")
    kpi: GrindMvpKPI
    size_distribution: GrindMvpSizeDistribution
    baseline_comparison: Optional[GrindMvpBaselineComparison] = None


class GrindMvpRunResponse(BaseModel):
    calc_run_id: UUID
    result: GrindMvpResult


class GrindMvpRunSummary(BaseModel):
    id: UUID
    created_at: datetime
    model_version: str
    plant_id: Optional[str] = None
    project_id: Optional[int] = None
    flowsheet_version_id: Optional[str] = None
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    comment: Optional[str] = None

    throughput_tph: Optional[float] = None
    product_p80_mm: Optional[float] = None
    specific_energy_kwhpt: Optional[float] = None

    model_config = {"from_attributes": True}


class GrindMvpRunDetail(BaseModel):
    id: UUID
    created_at: datetime
    model_version: str
    plant_id: Optional[str] = None
    project_id: Optional[int] = None
    flowsheet_version_id: Optional[str] = None
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    comment: Optional[str] = None
    input: GrindMvpInput
    result: GrindMvpResult
