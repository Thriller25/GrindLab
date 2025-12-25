from typing import Any, Optional, Union

from pydantic import BaseModel


class PSDPoint(BaseModel):
    """PSD point: size (µm) and cumulative passing (%)."""

    size_um: float
    pass_pct: float


class FactPSD(BaseModel):
    """Measured/fact PSD data for comparison with model."""

    points: list[PSDPoint] = []
    p80_um: Optional[float] = None
    p50_um: Optional[float] = None


class CalcInput(BaseModel):
    feed_tph: Optional[float] = None
    target_p80_microns: Optional[float] = None
    ore_hardness_ab: Optional[float] = None
    ore_hardness_ta: Optional[float] = None
    water_fraction: Optional[float] = None
    fact_psd: Optional[FactPSD] = None  # Measured PSD for fact vs model comparison


class CalcResultSummary(BaseModel):
    throughput_tph: Optional[float] = None
    specific_energy_kwh_per_t: Optional[float] = None
    p80_out_microns: Optional[float] = None
    circuit_efficiency_index: Optional[float] = None
    model_version: Optional[str] = None
    kpi: Optional[dict[str, Any]] = None
    global_kpi: Optional[dict[str, Any]] = None
    node_kpi: Optional[dict[str, Any]] = None
    streams: Optional[Union[dict[str, Any], list[dict[str, Any]]]] = None
    warnings: Optional[list[str]] = None
    errors: Optional[list[str]] = None

    model_config = {"extra": "allow"}  # Allow additional fields
