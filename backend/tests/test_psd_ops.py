"""
Тесты для PSD Operations (F3.3).

Проверяют:
- Стандартные сетки сит
- Перебиновка (rebin)
- Смешивание PSD (blend)
- Статистические характеристики
- Операции truncate, scale
"""

import pytest
from app.schemas.contracts import PSD
from app.schemas.contracts.psd_ops import (
    GRINDING_COARSE_SERIES,
    ISO_R20_SERIES,
    TYLER_SERIES,
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

# ==================== Sieve Series Tests ====================


class TestSieveSeries:
    """Тесты для сеток сит."""

    def test_tyler_series_exists(self):
        """Tyler series доступна."""
        assert len(TYLER_SERIES) > 40
        assert TYLER_SERIES.sizes_mm[0] < TYLER_SERIES.sizes_mm[-1]

    def test_iso_r20_series_exists(self):
        """ISO R20 series доступна."""
        assert len(ISO_R20_SERIES) > 30
        # Проверяем геометрическую прогрессию (R20 = 10^(1/20) ≈ 1.122)
        ratio = ISO_R20_SERIES.sizes_mm[5] / ISO_R20_SERIES.sizes_mm[4]
        assert 1.1 < ratio < 1.3

    def test_grinding_coarse_series(self):
        """Grinding coarse series для измельчения."""
        assert len(GRINDING_COARSE_SERIES) > 10
        # Должна включать типичные размеры для измельчения
        sizes = GRINDING_COARSE_SERIES.as_list()
        assert 0.075 in sizes  # P80 target
        assert 150.0 in sizes  # Coarse feed

    def test_get_sieve_series(self):
        """get_sieve_series по имени."""
        series = get_sieve_series("tyler")
        assert series == TYLER_SERIES

    def test_get_sieve_series_unknown(self):
        """get_sieve_series с неизвестным именем."""
        with pytest.raises(ValueError, match="Unknown sieve series"):
            get_sieve_series("nonexistent")

    def test_create_custom_series(self):
        """Создание пользовательской серии."""
        sizes = [0.1, 0.5, 0.2, 1.0]  # Неотсортированный
        series = create_custom_series(sizes, "My Series")

        assert series.name == "My Series"
        assert series.sizes_mm == (0.1, 0.2, 0.5, 1.0)  # Отсортирован


# ==================== Rebin Tests ====================


class TestRebin:
    """Тесты для перебиновки PSD."""

    @pytest.fixture
    def sample_psd(self) -> PSD:
        """PSD для тестов."""
        return PSD.from_cumulative(
            sizes_mm=[0.075, 0.150, 0.300, 0.600, 1.180, 2.360],
            cum_passing=[15.0, 35.0, 55.0, 75.0, 90.0, 98.0],
        )

    def test_rebin_to_coarser_grid(self, sample_psd: PSD):
        """Перебиновка на более грубую сетку."""
        target = [0.1, 0.5, 1.0, 2.0]
        rebinned = rebin_psd(sample_psd, target)

        assert len(rebinned.points) == 4
        # Значения должны быть интерполированы
        assert 15 < rebinned.points[0].cum_passing < 35  # 0.1 между 0.075 и 0.150

    def test_rebin_to_finer_grid(self, sample_psd: PSD):
        """Перебиновка на более мелкую сетку."""
        # Целевая сетка должна покрывать P80 исходного PSD (~0.8 мм)
        target = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2]
        rebinned = rebin_psd(sample_psd, target)

        assert len(rebinned.points) == 11
        # P80 должен сохраняться примерно
        original_p80 = sample_psd.p80
        rebinned_p80 = rebinned.p80
        assert abs(original_p80 - rebinned_p80) / original_p80 < 0.1  # <10% ошибка

    def test_rebin_preserves_source(self, sample_psd: PSD):
        """source указывает на перебиновку."""
        rebinned = rebin_psd(sample_psd, [0.1, 0.5, 1.0])
        assert "rebinned" in rebinned.source

    def test_rebin_insufficient_overlap(self, sample_psd: PSD):
        """Ошибка при недостаточном перекрытии."""
        # Целевая сетка полностью вне диапазона
        with pytest.raises(ValueError, match="insufficient overlap"):
            rebin_psd(sample_psd, [10.0, 20.0, 50.0])


# ==================== Blend Tests ====================


class TestBlend:
    """Тесты для смешивания PSD."""

    @pytest.fixture
    def psd_fine(self) -> PSD:
        """Мелкий PSD."""
        return PSD.from_cumulative(
            sizes_mm=[0.05, 0.1, 0.2, 0.5],
            cum_passing=[30.0, 60.0, 85.0, 98.0],
        )

    @pytest.fixture
    def psd_coarse(self) -> PSD:
        """Крупный PSD."""
        return PSD.from_cumulative(
            sizes_mm=[0.05, 0.1, 0.2, 0.5],
            cum_passing=[10.0, 25.0, 50.0, 80.0],
        )

    def test_blend_equal_weights(self, psd_fine: PSD, psd_coarse: PSD):
        """Смешивание 50/50."""
        blended = blend_psds([psd_fine, psd_coarse], [1.0, 1.0])

        # Результат должен быть между двумя исходными
        fine_p80 = psd_fine.p80
        coarse_p80 = psd_coarse.p80
        blended_p80 = blended.p80

        assert fine_p80 < blended_p80 < coarse_p80

    def test_blend_weighted(self, psd_fine: PSD, psd_coarse: PSD):
        """Смешивание с весами."""
        # 90% мелкий, 10% крупный
        blended = blend_psds([psd_fine, psd_coarse], [0.9, 0.1])

        # Результат ближе к мелкому
        fine_p80 = psd_fine.p80
        blended_p80 = blended.p80
        coarse_p80 = psd_coarse.p80

        # Разница с fine меньше чем разница с coarse
        assert abs(blended_p80 - fine_p80) < abs(blended_p80 - coarse_p80)

    def test_blend_single_psd(self, psd_fine: PSD):
        """Смешивание одного PSD возвращает его же."""
        result = blend_psds([psd_fine], [1.0])
        assert result == psd_fine

    def test_blend_empty_list(self):
        """Ошибка при пустом списке."""
        with pytest.raises(ValueError, match="At least one PSD"):
            blend_psds([], [])

    def test_blend_mismatched_lengths(self, psd_fine: PSD, psd_coarse: PSD):
        """Ошибка при несовпадении длин."""
        with pytest.raises(ValueError, match="must match"):
            blend_psds([psd_fine, psd_coarse], [1.0])


# ==================== Statistics Tests ====================


class TestPSDStats:
    """Тесты для статистических характеристик."""

    @pytest.fixture
    def sample_psd(self) -> PSD:
        """PSD для тестов."""
        return PSD.from_cumulative(
            sizes_mm=[0.05, 0.1, 0.2, 0.4, 0.8, 1.6],
            cum_passing=[10.0, 30.0, 55.0, 75.0, 90.0, 98.0],
        )

    def test_compute_stats(self, sample_psd: PSD):
        """Вычисление статистик."""
        stats = compute_psd_stats(sample_psd)

        assert stats.d50 is not None
        assert stats.span is not None
        assert stats.uniformity_coefficient is not None
        assert stats.d_mean is not None

    def test_stats_d50_equals_p50(self, sample_psd: PSD):
        """d50 = P50."""
        stats = compute_psd_stats(sample_psd)
        p50 = sample_psd.get_pxx(50)

        assert abs(stats.d50 - p50) < 0.001

    def test_stats_span_formula(self, sample_psd: PSD):
        """Span = (P90 - P10) / P50."""
        stats = compute_psd_stats(sample_psd)

        p10 = sample_psd.get_pxx(10)
        p50 = sample_psd.get_pxx(50)
        p90 = sample_psd.get_pxx(90)

        expected_span = (p90 - p10) / p50
        assert abs(stats.span - expected_span) < 0.001

    def test_stats_uniformity_coefficient(self, sample_psd: PSD):
        """Cu = D60 / D10."""
        stats = compute_psd_stats(sample_psd)

        p10 = sample_psd.get_pxx(10)
        p60 = sample_psd.get_pxx(60)

        expected_cu = p60 / p10
        assert abs(stats.uniformity_coefficient - expected_cu) < 0.01


# ==================== Retained Tests ====================


class TestRetained:
    """Тесты для % задержки."""

    def test_compute_retained(self):
        """Вычисление задержки."""
        psd = PSD.from_cumulative(
            sizes_mm=[0.1, 0.2, 0.5, 1.0],
            cum_passing=[20.0, 50.0, 80.0, 100.0],
        )

        retained = compute_retained(psd)

        assert len(retained) == 4
        # Первая фракция: 20% - 0% = 20%
        assert retained[0][2] == 20.0
        # Вторая фракция: 50% - 20% = 30%
        assert retained[1][2] == 30.0
        # Сумма = 100%
        total = sum(r[2] for r in retained)
        assert abs(total - 100.0) < 0.01


class TestHistogram:
    """Тесты для гистограммы."""

    def test_psd_to_histogram(self):
        """Конвертация в гистограмму."""
        psd = PSD.from_cumulative(
            sizes_mm=[0.1, 0.2, 0.5, 1.0],
            cum_passing=[20.0, 50.0, 80.0, 100.0],
        )

        hist = psd_to_histogram(psd)

        assert "bin_edges" in hist
        assert "bin_centers" in hist
        assert "frequencies" in hist
        assert len(hist["frequencies"]) == 4
        assert sum(hist["frequencies"]) == 100.0


# ==================== Truncate & Scale Tests ====================


class TestTruncate:
    """Тесты для обрезки PSD."""

    @pytest.fixture
    def sample_psd(self) -> PSD:
        """PSD для тестов."""
        return PSD.from_cumulative(
            sizes_mm=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0],
            cum_passing=[10.0, 25.0, 50.0, 75.0, 90.0, 100.0],
        )

    def test_truncate_min(self, sample_psd: PSD):
        """Обрезка снизу."""
        truncated = truncate_psd(sample_psd, min_size=0.1)

        assert len(truncated.points) == 5
        assert truncated.points[0].size_mm == 0.1
        # Перенормализовано
        assert truncated.points[0].cum_passing == 0.0

    def test_truncate_max(self, sample_psd: PSD):
        """Обрезка сверху."""
        truncated = truncate_psd(sample_psd, max_size=1.0)

        assert len(truncated.points) == 5
        assert truncated.points[-1].size_mm == 1.0
        # Перенормализовано
        assert truncated.points[-1].cum_passing == 100.0

    def test_truncate_both(self, sample_psd: PSD):
        """Обрезка с двух сторон."""
        truncated = truncate_psd(sample_psd, min_size=0.1, max_size=1.0)

        assert len(truncated.points) == 4
        assert truncated.points[0].cum_passing == 0.0
        assert truncated.points[-1].cum_passing == 100.0

    def test_truncate_insufficient_points(self, sample_psd: PSD):
        """Ошибка при слишком узком диапазоне."""
        with pytest.raises(ValueError, match="less than 2 points"):
            truncate_psd(sample_psd, min_size=0.3, max_size=0.4)


class TestScale:
    """Тесты для масштабирования PSD."""

    @pytest.fixture
    def sample_psd(self) -> PSD:
        """PSD для тестов."""
        return PSD.from_cumulative(
            sizes_mm=[0.1, 0.2, 0.5, 1.0],
            cum_passing=[20.0, 50.0, 80.0, 100.0],
        )

    def test_scale_down(self, sample_psd: PSD):
        """Масштабирование вниз (измельчение)."""
        scaled = scale_psd(sample_psd, 0.5)

        assert scaled.points[0].size_mm == 0.05  # 0.1 * 0.5
        assert scaled.points[-1].size_mm == 0.5  # 1.0 * 0.5
        # cum_passing не меняется
        assert scaled.points[0].cum_passing == 20.0

    def test_scale_up(self, sample_psd: PSD):
        """Масштабирование вверх."""
        scaled = scale_psd(sample_psd, 2.0)

        assert scaled.points[0].size_mm == 0.2  # 0.1 * 2.0
        assert scaled.points[-1].size_mm == 2.0  # 1.0 * 2.0

    def test_scale_preserves_shape(self, sample_psd: PSD):
        """Форма кривой сохраняется."""
        scaled = scale_psd(sample_psd, 0.5)

        # P80 уменьшается в 2 раза
        original_p80 = sample_psd.p80
        scaled_p80 = scaled.p80

        assert abs(scaled_p80 - original_p80 * 0.5) < 0.01

    def test_scale_invalid_factor(self, sample_psd: PSD):
        """Ошибка при некорректном факторе."""
        with pytest.raises(ValueError, match="must be positive"):
            scale_psd(sample_psd, 0)

        with pytest.raises(ValueError, match="must be positive"):
            scale_psd(sample_psd, -1)


# ==================== PSD Inverse Method Tests ====================


class TestPSDInverse:
    """Тесты для get_pxx_inverse."""

    @pytest.fixture
    def sample_psd(self) -> PSD:
        """PSD для тестов."""
        return PSD.from_cumulative(
            sizes_mm=[0.1, 0.2, 0.5, 1.0],
            cum_passing=[20.0, 50.0, 80.0, 100.0],
        )

    def test_inverse_at_known_point(self, sample_psd: PSD):
        """Inverse в известной точке."""
        cum = sample_psd.get_pxx_inverse(0.2)
        assert abs(cum - 50.0) < 0.01

    def test_inverse_interpolated(self, sample_psd: PSD):
        """Inverse с интерполяцией."""
        cum = sample_psd.get_pxx_inverse(0.15)
        # Между 0.1 (20%) и 0.2 (50%)
        assert 20 < cum < 50

    def test_inverse_boundary_min(self, sample_psd: PSD):
        """Inverse на нижней границе (вне диапазона) → None."""
        cum = sample_psd.get_pxx_inverse(0.05)  # Меньше минимума
        assert cum is None  # Вне диапазона → None

    def test_inverse_boundary_max(self, sample_psd: PSD):
        """Inverse на верхней границе (вне диапазона) → None."""
        cum = sample_psd.get_pxx_inverse(2.0)  # Больше максимума
        assert cum is None  # Вне диапазона → None

    def test_inverse_exact_boundary_min(self, sample_psd: PSD):
        """Inverse точно на нижней границе → значение."""
        cum = sample_psd.get_pxx_inverse(0.1)  # Точно минимум
        assert cum == 20.0  # Возвращает первое значение

    def test_inverse_exact_boundary_max(self, sample_psd: PSD):
        """Inverse точно на верхней границе → значение."""
        cum = sample_psd.get_pxx_inverse(1.0)  # Точно максимум
        assert cum == 100.0  # Возвращает последнее значение

    def test_inverse_roundtrip(self, sample_psd: PSD):
        """Roundtrip: get_pxx ↔ get_pxx_inverse."""
        # get_pxx(80) → размер → get_pxx_inverse → 80
        p80 = sample_psd.get_pxx(80)
        cum_back = sample_psd.get_pxx_inverse(p80)

        assert abs(cum_back - 80.0) < 1.0  # Допуск 1% на ошибку интерполяции
