"""
Simulation Router — API для запуска расчётов схем.

F5.1: Execution Engine API
"""

from typing import Any

from app.core.engine import FlowsheetExecutor, FlowsheetGraph
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/simulation", tags=["simulation"])


class FlowsheetNodeInput(BaseModel):
    """Узел схемы для расчёта."""

    id: str
    type: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class FlowsheetEdgeInput(BaseModel):
    """Связь схемы для расчёта."""

    id: str
    source: str
    target: str
    sourceHandle: str | None = "out"
    targetHandle: str | None = "in"


class SimulationRequest(BaseModel):
    """Запрос на расчёт схемы."""

    nodes: list[FlowsheetNodeInput]
    edges: list[FlowsheetEdgeInput]
    max_iterations: int = Field(default=50, ge=1, le=500)
    convergence_tolerance: float = Field(default=0.01, ge=0.0001, le=0.1)


class StreamOutput(BaseModel):
    """Поток в результате расчёта."""

    id: str
    mass_tph: float
    solids_pct: float
    water_tph: float
    total_flow_tph: float
    p80_mm: float | None = None
    psd: dict[str, Any] | None = None


class SimulationResponse(BaseModel):
    """Результат расчёта схемы."""

    success: bool
    streams: dict[str, StreamOutput] = Field(default_factory=dict)
    node_kpi: dict[str, dict[str, float]] = Field(default_factory=dict)
    global_kpi: dict[str, float] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    iterations: int = 0
    converged: bool = True
    execution_time_ms: float = 0.0


@router.post("/run", response_model=SimulationResponse)
def run_simulation(request: SimulationRequest) -> SimulationResponse:
    """
    Запустить расчёт технологической схемы.

    Принимает граф узлов и связей в формате React Flow,
    выполняет расчёт и возвращает потоки и KPI.

    ## Типы узлов

    - **feed** — узел питания (генерирует поток)
    - **product** — узел продукта (принимает поток)
    - **jaw_crusher** — щековая дробилка
    - **cone_crusher** — конусная дробилка
    - **sag_mill** — SAG мельница
    - **ball_mill** — шаровая мельница
    - **hydrocyclone** — гидроциклон
    - **vib_screen** — вибрационный грохот
    - **banana_screen** — банановый грохот

    ## Параметры узлов

    Параметры передаются в `data.parameters`. Пример для feed:
    ```json
    {
      "id": "feed-1",
      "data": {
        "type": "feed",
        "parameters": {
          "tph": 1000,
          "f80_mm": 150,
          "solids_pct": 100
        }
      }
    }
    ```

    ## Рециклы

    Схемы с рециклами (обратные потоки) решаются итеративно
    до достижения конвергенции.
    """
    if not request.nodes:
        raise HTTPException(status_code=400, detail="No nodes provided")

    # Преобразуем в формат для движка
    nodes_data = [
        {
            "id": n.id,
            "type": n.type,
            "data": n.data,
        }
        for n in request.nodes
    ]

    edges_data = [
        {
            "id": e.id,
            "source": e.source,
            "target": e.target,
            "sourceHandle": e.sourceHandle,
            "targetHandle": e.targetHandle,
        }
        for e in request.edges
    ]

    # Создаём граф и исполнитель
    try:
        graph = FlowsheetGraph.from_flowsheet_data(nodes_data, edges_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid flowsheet: {str(e)}")

    executor = FlowsheetExecutor(
        graph=graph,
        max_iterations=request.max_iterations,
        convergence_tolerance=request.convergence_tolerance,
    )

    # Выполняем расчёт
    result = executor.execute()

    # Преобразуем потоки в output модель
    streams_output = {}
    for edge_id, stream_dict in result.to_dict()["streams"].items():
        streams_output[edge_id] = StreamOutput(**stream_dict)

    return SimulationResponse(
        success=result.success,
        streams=streams_output,
        node_kpi=result.node_kpi,
        global_kpi=result.global_kpi,
        errors=result.errors,
        warnings=result.warnings,
        iterations=result.iterations,
        converged=result.converged,
        execution_time_ms=result.execution_time_ms,
    )


@router.post("/validate")
def validate_flowsheet(request: SimulationRequest) -> dict[str, Any]:
    """
    Валидировать схему без расчёта.

    Проверяет:
    - Наличие узлов питания и продукта
    - Связность графа
    - Корректность связей
    - Наличие рециклов
    """
    nodes_data = [{"id": n.id, "type": n.type, "data": n.data} for n in request.nodes]
    edges_data = [
        {
            "id": e.id,
            "source": e.source,
            "target": e.target,
            "sourceHandle": e.sourceHandle,
            "targetHandle": e.targetHandle,
        }
        for e in request.edges
    ]

    try:
        graph = FlowsheetGraph.from_flowsheet_data(nodes_data, edges_data)
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Invalid flowsheet structure: {str(e)}"],
        }

    errors = graph.validate()
    recycle_edges = graph.find_recycle_streams()

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "has_recycles": len(recycle_edges) > 0,
        "recycle_count": len(recycle_edges),
        "feed_nodes": [n.id for n in graph.get_feed_nodes()],
        "product_nodes": [n.id for n in graph.get_product_nodes()],
    }
