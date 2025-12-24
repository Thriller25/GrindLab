# F0.2 — Data Contracts (материал, PSD, KPI, поток)
# F3.3 — PSD Core (bins, rebin, операции)
# Версионируемые JSON-схемы для обмена данными между модулями

from .blast import Blast, BlastBlock, BlastSource, BlastStatus, GeoLocation
from .kpi import (
    KPI,
    KPICollection,
    KPIStatus,
    KPIType,
    circulating_load_kpi,
    mill_utilization_kpi,
    p80_kpi,
    specific_energy_kpi,
    throughput_kpi,
)
from .material import Material, MaterialComponent, MaterialPhase, MaterialQuality
from .psd import PSD, PSDInterpolation, PSDPoint, PSDQuantiles, PSDStats
from .psd_ops import (
    FLOTATION_FINE_SERIES,
    GRINDING_COARSE_SERIES,
    ISO_R20_SERIES,
    SIEVE_SERIES_REGISTRY,
    TYLER_SERIES,
    SieveSeries,
    SieveStandard,
    blend_psds,
    compute_psd_stats,
    compute_retained,
    create_custom_series,
    get_sieve_series,
    psd_to_histogram,
    rebin_psd,
    scale_psd,
    truncate_psd,
)
from .stream import Stream, StreamPort, StreamType

__all__ = [
    # PSD
    "PSD",
    "PSDPoint",
    "PSDQuantiles",
    "PSDStats",
    "PSDInterpolation",
    # PSD Operations (F3.3)
    "SieveStandard",
    "SieveSeries",
    "TYLER_SERIES",
    "ISO_R20_SERIES",
    "GRINDING_COARSE_SERIES",
    "FLOTATION_FINE_SERIES",
    "SIEVE_SERIES_REGISTRY",
    "get_sieve_series",
    "create_custom_series",
    "rebin_psd",
    "blend_psds",
    "compute_psd_stats",
    "compute_retained",
    "psd_to_histogram",
    "truncate_psd",
    "scale_psd",
    # Material
    "Material",
    "MaterialComponent",
    "MaterialQuality",
    "MaterialPhase",
    # Stream
    "Stream",
    "StreamType",
    "StreamPort",
    # KPI
    "KPI",
    "KPIType",
    "KPIStatus",
    "KPICollection",
    "throughput_kpi",
    "specific_energy_kpi",
    "p80_kpi",
    "circulating_load_kpi",
    "mill_utilization_kpi",
    # Blast
    "Blast",
    "BlastBlock",
    "BlastSource",
    "BlastStatus",
    "GeoLocation",
]
