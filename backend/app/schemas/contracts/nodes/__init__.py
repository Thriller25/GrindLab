"""
Node Library — Библиотека расчётных узлов для Flowsheet Designer.

Модуль предоставляет базовые классы и готовые модели оборудования
для симуляции технологических схем обогащения.

Содержит:
- base: Базовые классы (BaseNode, NodePort, NodeRegistry, etc.)
- crusher: Модели дробилок (JawCrusher, ConeCrusher)
- mill: Модели мельниц (SAGMill, BallMill)
- classifier: Модели классификаторов (Hydrocyclone)
- screen: Модели грохотов (VibScreen, BananaScreen)

Использование:
    from app.schemas.contracts.nodes import NodeRegistry, JawCrusher, SAGMill

    # Создание узла через реестр
    crusher = NodeRegistry.create("jaw_crusher", name="Primary Crusher")

    # Или напрямую
    crusher = JawCrusher(name="Primary Crusher")

Версия: 1.0
"""

from __future__ import annotations

# Base classes and registry
from .base import (
    BaseNode,
    NodeCategory,
    NodeParameter,
    NodePort,
    NodeRegistry,
    NodeResult,
    ParameterType,
    PortDirection,
    PortType,
)

# Classifier models
from .classifier import Hydrocyclone, partition_psd, plitt_d50c, rosin_rammler_efficiency

# Crusher models
from .crusher import ConeCrusher, JawCrusher, apply_css_crushing

# Mill models
from .mill import (
    BallMill,
    MillType,
    SAGMill,
    bond_energy,
    estimate_product_p80,
    generate_product_psd,
)

# Screen models
from .screen import (
    BananaScreen,
    VibScreen,
    generate_screen_product_psd,
    partition_by_screen,
    screen_efficiency_curve,
)

# ============================================================
# Version and metadata
# ============================================================

__version__ = "1.0.0"
__all__ = [
    # Base
    "BaseNode",
    "NodeCategory",
    "NodeParameter",
    "NodePort",
    "NodeRegistry",
    "NodeResult",
    "ParameterType",
    "PortDirection",
    "PortType",
    # Crushers
    "JawCrusher",
    "ConeCrusher",
    "apply_css_crushing",
    # Mills
    "SAGMill",
    "BallMill",
    "MillType",
    "bond_energy",
    "estimate_product_p80",
    "generate_product_psd",
    # Classifiers
    "Hydrocyclone",
    "rosin_rammler_efficiency",
    "partition_psd",
    "plitt_d50c",
    # Screens
    "VibScreen",
    "BananaScreen",
    "screen_efficiency_curve",
    "partition_by_screen",
    "generate_screen_product_psd",
]


def get_all_node_types() -> dict[str, type[BaseNode]]:
    """
    Получить все зарегистрированные типы узлов.

    Returns:
        Dict[node_type, NodeClass]
    """
    return NodeRegistry.get_all()


def list_nodes_by_category() -> dict[NodeCategory, list[str]]:
    """
    Список узлов по категориям.

    Returns:
        Dict[category, list of node_types]
    """
    result: dict[NodeCategory, list[str]] = {}

    for node_type, node_class in NodeRegistry.get_all().items():
        category = node_class.category
        if category not in result:
            result[category] = []
        result[category].append(node_type)

    return result
