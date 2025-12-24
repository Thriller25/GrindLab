"""
Node Library — Библиотека расчётных узлов для симуляции (F4.2).

Архитектура:
- BaseNode — абстрактный базовый класс для всех узлов
- UnitModel — модели единичного оборудования (Crusher, Mill, Screen, Cyclone)
- NodePort — точки входа/выхода для соединений
- NodeRegistry — реестр доступных типов узлов

Версия: 1.0
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, Type
from uuid import UUID, uuid4

from ..stream import Stream

# ============================================================
# Port Types
# ============================================================


class PortDirection(str, Enum):
    """Направление порта."""

    INPUT = "input"
    OUTPUT = "output"


class PortType(str, Enum):
    """Тип потока через порт."""

    FEED = "feed"  # Питание
    PRODUCT = "product"  # Продукт
    OVERFLOW = "overflow"  # Слив (классификатор)
    UNDERFLOW = "underflow"  # Пески (классификатор)
    OVERSIZE = "oversize"  # Надрешётный (грохот)
    UNDERSIZE = "undersize"  # Подрешётный (грохот)
    WATER = "water"  # Вода (добавка)
    RECYCLE = "recycle"  # Рецикл


@dataclass
class NodePort:
    """Порт узла для соединения с другими узлами."""

    name: str
    direction: PortDirection
    port_type: PortType
    required: bool = True
    description: str = ""

    # Подключенный поток (заполняется при симуляции)
    stream: Optional[Stream] = None

    def to_dict(self) -> dict:
        """Сериализация."""
        return {
            "name": self.name,
            "direction": self.direction.value,
            "port_type": self.port_type.value,
            "required": self.required,
            "description": self.description,
            "connected": self.stream is not None,
        }


# ============================================================
# Node Categories
# ============================================================


class NodeCategory(str, Enum):
    """Категория узла."""

    CRUSHER = "crusher"  # Дробилки
    MILL = "mill"  # Мельницы
    CLASSIFIER = "classifier"  # Классификаторы (циклоны)
    SCREEN = "screen"  # Грохоты
    CONVEYOR = "conveyor"  # Конвейеры
    SPLITTER = "splitter"  # Делители потока
    MIXER = "mixer"  # Смесители
    SOURCE = "source"  # Источники (питание)
    SINK = "sink"  # Стоки (продукт)


# ============================================================
# Node Parameters
# ============================================================


class ParameterType(str, Enum):
    """Тип параметра."""

    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    STRING = "string"
    ENUM = "enum"
    PSD = "psd"


@dataclass
class NodeParameter:
    """Параметр узла."""

    name: str
    display_name: str
    param_type: ParameterType
    default: Any
    unit: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""
    enum_values: Optional[List[str]] = None
    required: bool = True
    group: str = "general"  # Группа параметров для UI

    def to_dict(self) -> dict:
        """Сериализация."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "type": self.param_type.value,
            "default": self.default,
            "unit": self.unit,
            "min": self.min_value,
            "max": self.max_value,
            "description": self.description,
            "enum_values": self.enum_values,
            "required": self.required,
            "group": self.group,
        }


# ============================================================
# Calculation Result
# ============================================================


@dataclass
class NodeResult:
    """Результат расчёта узла."""

    success: bool
    outputs: Dict[str, Stream] = field(default_factory=dict)  # port_name -> Stream
    kpis: Dict[str, float] = field(default_factory=dict)  # key -> value
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # Дополнительные метрики
    power_kw: Optional[float] = None
    efficiency: Optional[float] = None
    throughput_tph: Optional[float] = None

    def to_dict(self) -> dict:
        """Сериализация."""
        return {
            "success": self.success,
            "outputs": {k: v.model_dump() for k, v in self.outputs.items()},
            "kpis": self.kpis,
            "warnings": self.warnings,
            "errors": self.errors,
            "power_kw": self.power_kw,
            "efficiency": self.efficiency,
            "throughput_tph": self.throughput_tph,
        }


# ============================================================
# Base Node
# ============================================================


class BaseNode(ABC):
    """
    Абстрактный базовый класс для всех расчётных узлов.

    Каждый узел:
    - Имеет уникальный ID и имя
    - Имеет входные и выходные порты
    - Имеет параметры (паспорт оборудования)
    - Может рассчитать выходные потоки по входным

    Subclasses должны реализовать:
    - _define_ports() — определить порты
    - _define_parameters() — определить параметры
    - calculate() — выполнить расчёт
    """

    # Метаданные класса (переопределяются в подклассах)
    node_type: ClassVar[str] = "base"
    display_name: ClassVar[str] = "Base Node"
    category: ClassVar[NodeCategory] = NodeCategory.MIXER
    description: ClassVar[str] = "Base node class"
    icon: ClassVar[str] = "⚙️"

    def __init__(
        self,
        node_id: Optional[UUID] = None,
        name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        self.id = node_id or uuid4()
        self.name = name or f"{self.display_name} {str(self.id)[:4]}"

        # Порты
        self._ports: Dict[str, NodePort] = {}
        self._define_ports()

        # Параметры
        self._parameter_defs: Dict[str, NodeParameter] = {}
        self._define_parameters()

        # Значения параметров
        self._params: Dict[str, Any] = {}
        self._init_default_params()
        if params:
            self.set_params(params)

    @abstractmethod
    def _define_ports(self) -> None:
        """Определить порты узла. Вызывается в __init__."""
        pass

    @abstractmethod
    def _define_parameters(self) -> None:
        """Определить параметры узла. Вызывается в __init__."""
        pass

    @abstractmethod
    def calculate(self, inputs: Dict[str, Stream]) -> NodeResult:
        """
        Выполнить расчёт узла.

        Args:
            inputs: Словарь входных потоков {port_name: Stream}

        Returns:
            NodeResult с выходными потоками и метриками
        """
        pass

    def _init_default_params(self) -> None:
        """Инициализировать параметры значениями по умолчанию."""
        for name, param in self._parameter_defs.items():
            self._params[name] = param.default

    def _add_port(self, port: NodePort) -> None:
        """Добавить порт."""
        self._ports[port.name] = port

    def _add_parameter(self, param: NodeParameter) -> None:
        """Добавить параметр."""
        self._parameter_defs[param.name] = param

    # === Public API ===

    @property
    def ports(self) -> Dict[str, NodePort]:
        """Все порты."""
        return self._ports.copy()

    @property
    def input_ports(self) -> Dict[str, NodePort]:
        """Входные порты."""
        return {k: v for k, v in self._ports.items() if v.direction == PortDirection.INPUT}

    @property
    def output_ports(self) -> Dict[str, NodePort]:
        """Выходные порты."""
        return {k: v for k, v in self._ports.items() if v.direction == PortDirection.OUTPUT}

    @property
    def parameters(self) -> Dict[str, NodeParameter]:
        """Определения параметров."""
        return self._parameter_defs.copy()

    @property
    def params(self) -> Dict[str, Any]:
        """Текущие значения параметров."""
        return self._params.copy()

    def get_port(self, name: str) -> Optional[NodePort]:
        """Получить порт по имени."""
        return self._ports.get(name)

    def get_param(self, name: str) -> Any:
        """Получить значение параметра."""
        return self._params.get(name)

    def set_param(self, name: str, value: Any) -> None:
        """Установить значение параметра."""
        if name not in self._parameter_defs:
            raise ValueError(f"Unknown parameter: {name}")
        # TODO: валидация типа и диапазона
        self._params[name] = value

    def set_params(self, params: Dict[str, Any]) -> None:
        """Установить несколько параметров."""
        for name, value in params.items():
            self.set_param(name, value)

    def validate_inputs(self, inputs: Dict[str, Stream]) -> List[str]:
        """
        Проверить наличие обязательных входов.

        Returns:
            Список ошибок (пустой если всё OK)
        """
        errors = []
        for port_name, port in self.input_ports.items():
            if port.required and port_name not in inputs:
                errors.append(f"Missing required input: {port_name}")
        return errors

    def get_metadata(self) -> dict:
        """Получить метаданные узла для UI."""
        return {
            "node_type": self.node_type,
            "display_name": self.display_name,
            "category": self.category.value,
            "description": self.description,
            "icon": self.icon,
            "ports": [p.to_dict() for p in self._ports.values()],
            "parameters": [p.to_dict() for p in self._parameter_defs.values()],
        }

    def to_dict(self) -> dict:
        """Сериализация узла."""
        return {
            "id": str(self.id),
            "name": self.name,
            "node_type": self.node_type,
            "category": self.category.value,
            "params": self._params,
            "ports": {k: v.to_dict() for k, v in self._ports.items()},
        }


# ============================================================
# Node Registry
# ============================================================


class NodeRegistry:
    """
    Реестр доступных типов узлов.

    Позволяет:
    - Регистрировать новые типы узлов
    - Создавать экземпляры узлов по типу
    - Получать метаданные для UI
    """

    _instance: Optional["NodeRegistry"] = None
    _nodes: Dict[str, Type[BaseNode]] = {}

    def __new__(cls) -> "NodeRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, node_class: Type[BaseNode]) -> Type[BaseNode]:
        """
        Декоратор для регистрации класса узла.

        Usage:
            @NodeRegistry.register
            class MyNode(BaseNode):
                node_type = "my_node"
                ...
        """
        cls._nodes[node_class.node_type] = node_class
        return node_class

    @classmethod
    def get(cls, node_type: str) -> Optional[Type[BaseNode]]:
        """Получить класс узла по типу."""
        return cls._nodes.get(node_type)

    @classmethod
    def create(
        cls,
        node_type: str,
        node_id: Optional[UUID] = None,
        name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[BaseNode]:
        """Создать экземпляр узла по типу."""
        node_class = cls.get(node_type)
        if node_class:
            return node_class(node_id=node_id, name=name, params=params)
        return None

    @classmethod
    def list_types(cls) -> List[str]:
        """Список всех зарегистрированных типов."""
        return list(cls._nodes.keys())

    @classmethod
    def get_all(cls) -> Dict[str, Type[BaseNode]]:
        """Получить все зарегистрированные типы узлов."""
        return dict(cls._nodes)

    @classmethod
    def list_by_category(cls, category: NodeCategory) -> List[Type[BaseNode]]:
        """Список узлов по категории."""
        return [n for n in cls._nodes.values() if n.category == category]

    @classmethod
    def get_catalog(cls) -> List[dict]:
        """Получить каталог всех узлов для UI."""
        catalog = []
        for node_class in cls._nodes.values():
            # Создаём временный экземпляр для получения метаданных
            temp = node_class()
            catalog.append(temp.get_metadata())
        return catalog


# ============================================================
# Export
# ============================================================

__all__ = [
    "PortDirection",
    "PortType",
    "NodePort",
    "NodeCategory",
    "ParameterType",
    "NodeParameter",
    "NodeResult",
    "BaseNode",
    "NodeRegistry",
]
