"""
Tests for Node Library — F4.2 Node Library.

Тестирует:
- BaseNode и NodeRegistry
- Crusher models (Jaw, Cone)
- Mill models (SAG, Ball)
- Classifier (Hydrocyclone)
- Screen models (VibScreen, BananaScreen)
"""

import pytest
from app.schemas.contracts import PSD, Material, MaterialPhase, PSDPoint, Stream, StreamType
from app.schemas.contracts.nodes import (  # Base; Crushers; Mills; Classifier; Screens
    BallMill,
    BananaScreen,
    ConeCrusher,
    Hydrocyclone,
    JawCrusher,
    NodeCategory,
    NodeRegistry,
    PortDirection,
    SAGMill,
    VibScreen,
    apply_css_crushing,
    bond_energy,
    estimate_product_p80,
    generate_product_psd,
    partition_by_screen,
    rosin_rammler_efficiency,
    screen_efficiency_curve,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def sample_psd_coarse():
    """PSD для дроблёной руды (крупная)."""
    return PSD(
        points=[
            PSDPoint(size_mm=200, cum_passing=95),
            PSDPoint(size_mm=150, cum_passing=85),
            PSDPoint(size_mm=100, cum_passing=65),
            PSDPoint(size_mm=50, cum_passing=35),
            PSDPoint(size_mm=25, cum_passing=15),
            PSDPoint(size_mm=10, cum_passing=5),
        ]
    )


@pytest.fixture
def sample_psd_medium():
    """PSD для питания мельницы (средняя)."""
    return PSD(
        points=[
            PSDPoint(size_mm=50, cum_passing=98),
            PSDPoint(size_mm=25, cum_passing=90),
            PSDPoint(size_mm=10, cum_passing=70),
            PSDPoint(size_mm=5, cum_passing=50),
            PSDPoint(size_mm=2, cum_passing=30),
            PSDPoint(size_mm=1, cum_passing=20),
        ]
    )


@pytest.fixture
def sample_psd_fine():
    """PSD для мельничного продукта (мелкая)."""
    return PSD(
        points=[
            PSDPoint(size_mm=2, cum_passing=98),
            PSDPoint(size_mm=1, cum_passing=90),
            PSDPoint(size_mm=0.5, cum_passing=75),
            PSDPoint(size_mm=0.25, cum_passing=55),
            PSDPoint(size_mm=0.1, cum_passing=35),
            PSDPoint(size_mm=0.05, cum_passing=20),
        ]
    )


@pytest.fixture
def coarse_ore_material(sample_psd_coarse):
    """Крупная руда для дробления."""
    return Material(
        name="ROM Ore",
        phase=MaterialPhase.SOLID,
        solids_tph=1000,
        water_tph=50,
        psd=sample_psd_coarse,
    )


@pytest.fixture
def mill_feed_material(sample_psd_medium):
    """Питание мельницы."""
    return Material(
        name="Crushed Ore",
        phase=MaterialPhase.SOLID,
        solids_tph=800,
        water_tph=100,
        psd=sample_psd_medium,
    )


@pytest.fixture
def slurry_material(sample_psd_fine):
    """Пульпа для классификации."""
    return Material(
        name="Mill Discharge",
        phase=MaterialPhase.SLURRY,
        solids_tph=600,
        water_tph=400,
        psd=sample_psd_fine,
    )


@pytest.fixture
def feed_stream(coarse_ore_material):
    """Поток питания для дробилки."""
    return Stream(
        name="Feed",
        stream_type=StreamType.SOLIDS,
        material=coarse_ore_material,
    )


@pytest.fixture
def mill_stream(mill_feed_material):
    """Поток питания мельницы."""
    return Stream(
        name="Mill Feed",
        stream_type=StreamType.SOLIDS,
        material=mill_feed_material,
    )


@pytest.fixture
def slurry_stream(slurry_material):
    """Поток пульпы."""
    return Stream(
        name="Slurry",
        stream_type=StreamType.SLURRY,
        material=slurry_material,
    )


# ============================================================
# Test NodeRegistry
# ============================================================


class TestNodeRegistry:
    """Тесты реестра узлов."""

    def test_registry_has_all_nodes(self):
        """Все узлы зарегистрированы."""
        all_nodes = NodeRegistry.get_all()

        assert "jaw_crusher" in all_nodes
        assert "cone_crusher" in all_nodes
        assert "sag_mill" in all_nodes
        assert "ball_mill" in all_nodes
        assert "hydrocyclone" in all_nodes
        assert "vibrating_screen" in all_nodes
        assert "banana_screen" in all_nodes

    def test_create_node_by_type(self):
        """Создание узла через реестр."""
        crusher = NodeRegistry.create("jaw_crusher", name="Test Crusher")

        assert crusher is not None
        assert crusher.name == "Test Crusher"
        assert crusher.node_type == "jaw_crusher"

    def test_create_unknown_type_returns_none(self):
        """Неизвестный тип возвращает None."""
        result = NodeRegistry.create("unknown_node", name="Test")
        assert result is None


# ============================================================
# Test Crushers
# ============================================================


class TestJawCrusher:
    """Тесты щековой дробилки."""

    def test_create_jaw_crusher(self):
        """Создание щековой дробилки."""
        crusher = JawCrusher(name="Primary Jaw")

        assert crusher.node_type == "jaw_crusher"
        assert crusher.category == NodeCategory.CRUSHER
        assert crusher.display_name == "Jaw Crusher"

    def test_jaw_crusher_has_ports(self):
        """Порты определены."""
        crusher = JawCrusher(name="Test")

        feed_port = crusher.get_port("feed")
        product_port = crusher.get_port("product")

        assert feed_port is not None
        assert feed_port.direction == PortDirection.INPUT
        assert product_port is not None
        assert product_port.direction == PortDirection.OUTPUT

    def test_jaw_crusher_has_parameters(self):
        """Параметры определены."""
        crusher = JawCrusher(name="Test")

        assert crusher.get_param("css") > 0
        assert crusher.get_param("capacity_tph") > 0
        assert crusher.get_param("power_kw") > 0

    def test_jaw_crusher_calculate(self, feed_stream):
        """Расчёт дробилки."""
        crusher = JawCrusher(name="Primary")
        crusher.set_param("css", 100)

        result = crusher.calculate({"feed": feed_stream})

        assert result.success
        assert "product" in result.outputs
        # Проверяем что KPI рассчитаны
        assert result.kpis["feed_p80_mm"] > 0
        assert result.kpis["product_p80_mm"] > 0
        # Продукт имеет PSD
        assert result.outputs["product"].material.psd is not None

    def test_jaw_crusher_validates_inputs(self):
        """Валидация входов."""
        crusher = JawCrusher(name="Test")

        result = crusher.calculate({})  # No feed

        assert not result.success
        assert len(result.errors) > 0

    def test_jaw_crusher_set_param(self):
        """Установка параметров."""
        crusher = JawCrusher(name="Test")

        crusher.set_param("css", 150)

        assert crusher.get_param("css") == 150


class TestConeCrusher:
    """Тесты конусной дробилки."""

    def test_cone_crusher_creation(self):
        """Создание конусной дробилки."""
        crusher = ConeCrusher(name="Secondary Cone")

        assert crusher.node_type == "cone_crusher"
        assert crusher.category == NodeCategory.CRUSHER

    def test_cone_crusher_calculate(self, feed_stream):
        """Расчёт конусной дробилки."""
        crusher = ConeCrusher(name="Secondary")
        crusher.set_param("css", 25)

        result = crusher.calculate({"feed": feed_stream})

        assert result.success
        assert result.kpis["reduction_ratio"] > 1


class TestCrushingFunction:
    """Тесты функции дробления."""

    def test_apply_css_crushing(self, sample_psd_coarse):
        """Применение дробления по CSS."""
        result_psd = apply_css_crushing(sample_psd_coarse, css_mm=50, reduction_ratio=4.0)

        # Продукт имеет PSD
        assert len(result_psd.points) > 0
        assert result_psd.p80 is not None

    def test_css_limits_product_size(self, sample_psd_coarse):
        """CSS ограничивает максимальный размер."""
        result_psd = apply_css_crushing(sample_psd_coarse, css_mm=25, reduction_ratio=4.0)

        # Проверяем что продукт имеет PSD с точками
        assert len(result_psd.points) > 0
        # Максимальный размер точки должен быть около CSS * 1.5 = 37.5mm
        max_size_in_product = max(p.size_mm for p in result_psd.points)
        assert max_size_in_product <= 40  # CSS * 1.5 + небольшой допуск


# ============================================================
# Test Mills
# ============================================================


class TestSAGMill:
    """Тесты SAG мельницы."""

    def test_create_sag_mill(self):
        """Создание SAG мельницы."""
        mill = SAGMill(name="SAG-1")

        assert mill.node_type == "sag_mill"
        assert mill.category == NodeCategory.MILL

    def test_sag_mill_parameters(self):
        """Параметры SAG мельницы."""
        mill = SAGMill(name="SAG-1")

        assert mill.get_param("diameter_m") > 0
        assert mill.get_param("length_m") > 0
        assert mill.get_param("speed_pct_critical") > 0
        assert mill.get_param("ball_charge_pct") > 0

    def test_sag_mill_calculate(self, mill_stream):
        """Расчёт SAG мельницы."""
        mill = SAGMill(name="SAG-1")

        result = mill.calculate({"feed": mill_stream})

        assert result.success
        assert "product" in result.outputs
        assert result.kpis["product_p80_mm"] < result.kpis["feed_p80_mm"]
        assert result.kpis["specific_energy_kwh_t"] > 0
        assert result.power_kw > 0


class TestBallMill:
    """Тесты шаровой мельницы."""

    def test_create_ball_mill(self):
        """Создание шаровой мельницы."""
        mill = BallMill(name="Ball-1")

        assert mill.node_type == "ball_mill"
        assert mill.category == NodeCategory.MILL

    def test_ball_mill_calculate(self, mill_stream):
        """Расчёт шаровой мельницы."""
        mill = BallMill(name="Ball-1")

        result = mill.calculate({"feed": mill_stream})

        assert result.success
        assert result.kpis["product_p80_mm"] < result.kpis["feed_p80_mm"]


class TestMillFunctions:
    """Тесты функций расчёта мельниц."""

    def test_bond_energy(self):
        """Расчёт энергии по Bond."""
        # F80 = 5000 um, P80 = 150 um, Wi = 15 kWh/t
        energy = bond_energy(5000, 150, 15)

        assert energy > 0
        assert energy < 50  # Reasonable range

    def test_estimate_product_p80(self):
        """Обратный расчёт P80."""
        feed_p80 = 5000  # um
        wi = 15  # kWh/t
        energy = 10  # kWh/t

        product_p80 = estimate_product_p80(feed_p80, wi, energy)

        assert product_p80 < feed_p80
        assert product_p80 > 50  # Minimum limit

    def test_generate_product_psd(self):
        """Генерация PSD продукта."""
        target_p80 = 0.150  # mm

        psd = generate_product_psd(target_p80)

        assert len(psd.points) > 0
        # P80 должен быть близок к целевому
        assert abs(psd.p80 - target_p80) < target_p80 * 0.5


# ============================================================
# Test Hydrocyclone
# ============================================================


class TestHydrocyclone:
    """Тесты гидроциклона."""

    def test_create_cyclone(self):
        """Создание гидроциклона."""
        cyclone = Hydrocyclone(name="Cyclone-1")

        assert cyclone.node_type == "hydrocyclone"
        assert cyclone.category == NodeCategory.CLASSIFIER

    def test_cyclone_ports(self):
        """Порты гидроциклона."""
        cyclone = Hydrocyclone(name="Test")

        assert cyclone.get_port("feed") is not None
        assert cyclone.get_port("overflow") is not None
        assert cyclone.get_port("underflow") is not None

    def test_cyclone_calculate(self, slurry_stream):
        """Расчёт гидроциклона."""
        cyclone = Hydrocyclone(name="Cyclone-1")
        cyclone.set_param("target_d50_um", 75)

        result = cyclone.calculate({"feed": slurry_stream})

        assert result.success
        assert "overflow" in result.outputs
        assert "underflow" in result.outputs

        # Слив тоньше песков
        of = result.outputs["overflow"].material
        uf = result.outputs["underflow"].material

        assert of.psd.p80 < uf.psd.p80

    def test_cyclone_mass_balance(self, slurry_stream):
        """Масс-баланс гидроциклона."""
        cyclone = Hydrocyclone(name="Test")
        feed_solids = slurry_stream.material.solids_tph

        result = cyclone.calculate({"feed": slurry_stream})

        of_solids = result.outputs["overflow"].material.solids_tph
        uf_solids = result.outputs["underflow"].material.solids_tph

        # Сумма продуктов = питание
        assert abs(of_solids + uf_solids - feed_solids) < 0.1


class TestCycloneFunctions:
    """Тесты функций циклона."""

    def test_rosin_rammler_efficiency(self):
        """Кривая эффективности."""
        d50c = 0.075  # mm

        # Очень мелкие идут в слив (эффективность низкая)
        e_fine = rosin_rammler_efficiency(0.01, d50c)
        assert e_fine < 0.1

        # На d50 - 50%
        e_d50 = rosin_rammler_efficiency(d50c, d50c)
        assert 0.4 < e_d50 < 0.6

        # Крупные идут в пески (эффективность высокая)
        e_coarse = rosin_rammler_efficiency(0.3, d50c)
        assert e_coarse > 0.9


# ============================================================
# Test Screens
# ============================================================


class TestVibScreen:
    """Тесты вибрационного грохота."""

    def test_create_screen(self):
        """Создание грохота."""
        screen = VibScreen(name="Screen-1")

        assert screen.node_type == "vibrating_screen"
        assert screen.category == NodeCategory.SCREEN

    def test_screen_ports(self):
        """Порты грохота."""
        screen = VibScreen(name="Test")

        assert screen.get_port("feed") is not None
        assert screen.get_port("oversize") is not None
        assert screen.get_port("undersize") is not None

    def test_screen_calculate(self, feed_stream):
        """Расчёт грохота."""
        screen = VibScreen(name="Screen-1")
        screen.set_param("aperture_mm", 25)

        result = screen.calculate({"feed": feed_stream})

        assert result.success
        assert "oversize" in result.outputs
        assert "undersize" in result.outputs

    def test_screen_mass_balance(self, feed_stream):
        """Масс-баланс грохота."""
        screen = VibScreen(name="Test")
        feed_solids = feed_stream.material.solids_tph

        result = screen.calculate({"feed": feed_stream})

        os_solids = result.outputs["oversize"].material.solids_tph
        us_solids = result.outputs["undersize"].material.solids_tph

        assert abs(os_solids + us_solids - feed_solids) < 0.1


class TestBananaScreen:
    """Тесты бананового грохота."""

    def test_create_banana_screen(self):
        """Создание бананового грохота."""
        screen = BananaScreen(name="Banana-1")

        assert screen.node_type == "banana_screen"

    def test_banana_screen_calculate(self, slurry_stream):
        """Расчёт бананового грохота."""
        screen = BananaScreen(name="Test")
        screen.set_param("aperture_mm", 0.5)

        result = screen.calculate({"feed": slurry_stream})

        assert result.success


class TestScreenFunctions:
    """Тесты функций грохота."""

    def test_screen_efficiency_curve(self):
        """Кривая эффективности грохота."""
        aperture = 25  # mm

        # Мелкие проходят
        prob_fine = screen_efficiency_curve(5, aperture)
        assert prob_fine > 0.9

        # На размере апертуры - ~50%
        prob_apt = screen_efficiency_curve(aperture, aperture)
        assert 0.3 < prob_apt < 0.7

        # Крупные не проходят
        prob_coarse = screen_efficiency_curve(50, aperture)
        assert prob_coarse < 0.1

    def test_partition_by_screen(self, sample_psd_coarse):
        """Разделение по грохоту."""
        undersize, oversize = partition_by_screen(sample_psd_coarse, 50)

        assert undersize > 0
        assert oversize > 0
        assert abs(undersize + oversize - 1.0) < 0.01


# ============================================================
# Test Node Integration
# ============================================================


class TestNodeIntegration:
    """Интеграционные тесты узлов."""

    def test_crusher_to_mill_chain(self, coarse_ore_material):
        """Цепочка дробилка → мельница."""
        # Дробление
        crusher = JawCrusher(name="Primary")
        crusher.set_param("css", 100)

        feed_stream = Stream(
            name="ROM Feed",
            stream_type=StreamType.SOLIDS,
            material=coarse_ore_material,
        )

        crush_result = crusher.calculate({"feed": feed_stream})
        assert crush_result.success

        # Мельница получает продукт дробления
        mill = SAGMill(name="SAG-1")
        mill_result = mill.calculate({"feed": crush_result.outputs["product"]})

        assert mill_result.success
        assert mill_result.kpis["product_p80_mm"] < crush_result.kpis["product_p80_mm"]

    def test_mill_cyclone_circuit(self, mill_feed_material):
        """Цикл мельница + циклон."""
        # Мельница
        mill = BallMill(name="Ball-1")
        feed_stream = Stream(
            name="Fresh Feed",
            stream_type=StreamType.SOLIDS,
            material=mill_feed_material,
        )

        mill_result = mill.calculate({"feed": feed_stream})
        assert mill_result.success

        # Классификация
        cyclone = Hydrocyclone(name="Cyclone-1")
        cyclone.set_param("target_d50_um", 100)

        cyc_result = cyclone.calculate({"feed": mill_result.outputs["product"]})

        assert cyc_result.success
        # Слив готовый продукт
        # Пески возвращаются в мельницу (в реальной схеме)

    def test_all_nodes_have_required_methods(self):
        """Все узлы имеют необходимые методы."""
        for node_type, node_class in NodeRegistry.get_all().items():
            node = node_class(name=f"Test {node_type}")

            # Обязательные атрибуты
            assert hasattr(node, "node_type")
            assert hasattr(node, "display_name")
            assert hasattr(node, "category")

            # Методы
            assert callable(getattr(node, "calculate", None))
            assert callable(getattr(node, "get_port", None))
            assert callable(getattr(node, "get_param", None))
            assert callable(getattr(node, "set_param", None))

    def test_node_serialization(self):
        """Сериализация параметров узла."""
        crusher = JawCrusher(name="Test Crusher")
        crusher.set_param("css", 150)
        crusher.set_param("capacity_tph", 2000)

        # Получаем все параметры
        params = {}
        for p in crusher.parameters.values():
            params[p.name] = crusher.get_param(p.name)

        assert params["css"] == 150
        assert params["capacity_tph"] == 2000
