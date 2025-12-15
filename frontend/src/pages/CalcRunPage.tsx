import axios from "axios";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  api,
  fetchFlowsheetVersionsForPlant,
  fetchPlants,
  fetchCalcScenariosByFlowsheetVersion,
  CalcScenario,
  FlowsheetVersionSummary,
  GrindMvpBaselineComparison,
  GrindMvpResult,
  GrindMvpRunDetail,
  PlantSummary,
} from "../api/client";
import BackToHomeButton from "../components/BackToHomeButton";

type LocationState = { fromRun?: GrindMvpRunDetail };
type FieldErrors = Record<string, string | undefined>;

const defaultForm = {
  plant_id: "",
  flowsheet_version_id: "",
  scenario_name: "Базовый сценарий",
  feed: { tonnage_tph: 500, p80_mm: 12, density_t_per_m3: 2.7 },
  mill: {
    type: "SAG",
    power_installed_kw: 8000,
    power_draw_kw: 7200,
    ball_charge_percent: 12,
    speed_percent_critical: 75,
  },
  classifier: {
    type: "cyclone",
    cut_size_p80_mm: 0.18,
    circulating_load_percent: 250,
  },
};

function mapBackendPathToFieldKey(loc: any[]): string | null {
  if (loc.length >= 3 && loc[0] === "body") {
    const section = loc[1];
    const field = loc[2];
    if (section === "feed") {
      if (field === "tonnage_tph") return "feedTonnage";
      if (field === "p80_mm") return "feedP80";
      if (field === "density_t_per_m3") return "feedDensity";
    }
    if (section === "mill") {
      if (field === "power_installed_kw") return "millPowerInstalled";
      if (field === "power_draw_kw") return "millPowerDraw";
      if (field === "ball_charge_percent") return "millBallCharge";
      if (field === "speed_percent_critical") return "millSpeed";
    }
    if (section === "classifier") {
      if (field === "cut_size_p80_mm") return "classifierCutSize";
      if (field === "circulating_load_percent") return "classifierCirculatingLoad";
    }
  }
  if (loc.length >= 2 && loc[0] === "body") {
    const field = loc[1];
    if (field === "plant_id") return "plantId";
    if (field === "flowsheet_version_id") return "flowsheetVersionId";
    if (field === "scenario_name") return "scenarioName";
  }
  return null;
}

function KpiDelta({
  label,
  delta,
  deltaPercent,
}: {
  label: string;
  delta?: number | null;
  deltaPercent?: number | null;
}) {
  if (delta == null) return null;
  const sign = delta > 0 ? "+" : "";
  const className = delta > 0 ? "delta positive" : delta < 0 ? "delta negative" : "delta";
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={className}>
        {sign}
        {delta.toFixed(2)}
        {deltaPercent != null && (
          <span className="delta-percent">
            {" "}
            ({sign}
            {deltaPercent.toFixed(1)}%)
          </span>
        )}
      </div>
    </div>
  );
}

export const CalcRunPage = () => {
  const location = useLocation();
  const fromRun = (location.state as LocationState | undefined)?.fromRun;

  const initialForm = useMemo(() => {
    if (!fromRun) return defaultForm;
    const input = fromRun.input;
    return {
      plant_id: String(input.plant_id ?? ""),
      flowsheet_version_id: String(input.flowsheet_version_id ?? ""),
      scenario_name: input.scenario_name ? `${input.scenario_name} (копия)` : "Базовый сценарий",
      feed: {
        tonnage_tph: Number(input.feed.tonnage_tph),
        p80_mm: Number(input.feed.p80_mm),
        density_t_per_m3: Number(input.feed.density_t_per_m3),
      },
      mill: {
        type: input.mill.type,
        power_installed_kw: Number(input.mill.power_installed_kw),
        power_draw_kw: Number(input.mill.power_draw_kw),
        ball_charge_percent: Number(input.mill.ball_charge_percent),
        speed_percent_critical: Number(input.mill.speed_percent_critical),
      },
      classifier: {
        type: input.classifier.type,
        cut_size_p80_mm: Number(input.classifier.cut_size_p80_mm),
        circulating_load_percent: Number(input.classifier.circulating_load_percent),
      },
    };
  }, [fromRun]);

  const [form, setForm] = useState(initialForm);
  const [plantId, setPlantId] = useState<string>(initialForm.plant_id);
  const [flowsheetVersionId, setFlowsheetVersionId] = useState<string>(initialForm.flowsheet_version_id);
  const [plants, setPlants] = useState<PlantSummary[]>([]);
  const [flowsheetVersions, setFlowsheetVersions] = useState<FlowsheetVersionSummary[]>([]);
  const [scenarios, setScenarios] = useState<CalcScenario[]>([]);
  const [isPlantsLoading, setIsPlantsLoading] = useState(false);
  const [isFlowsheetsLoading, setIsFlowsheetsLoading] = useState(false);
  const [isScenariosLoading, setIsScenariosLoading] = useState(false);
  const [dictError, setDictError] = useState<string | null>(null);
  const [scenariosError, setScenariosError] = useState<string | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("");
  const [result, setResult] = useState<GrindMvpResult | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [useBaseline, setUseBaseline] = useState<boolean>(!!fromRun);

  const updateField = (path: string, value: any) => {
    setForm((prev) => {
      const clone: any = structuredClone(prev);
      const parts = path.split(".");
      let cursor: any = clone;
      for (let i = 0; i < parts.length - 1; i++) {
        cursor = cursor[parts[i]];
      }
      cursor[parts[parts.length - 1]] = value;
      return clone;
    });
  };

  useEffect(() => {
    setForm((prev) => (prev.plant_id === plantId ? prev : { ...prev, plant_id: plantId }));
  }, [plantId]);

  useEffect(() => {
    setForm((prev) =>
      prev.flowsheet_version_id === flowsheetVersionId
        ? prev
        : { ...prev, flowsheet_version_id: flowsheetVersionId },
    );
  }, [flowsheetVersionId]);

  useEffect(() => {
    setIsPlantsLoading(true);
    setDictError(null);
    fetchPlants()
      .then((data) => {
        setPlants(data);
        setPlantId((prev) => {
          if (prev || !fromRun?.input.plant_id) return prev;
          return String(fromRun.input.plant_id);
        });
      })
      .catch(() => {
        setDictError("Не удалось загрузить список фабрик");
      })
      .finally(() => setIsPlantsLoading(false));
  }, [fromRun]);

  useEffect(() => {
    setFlowsheetVersionId("");
    setFlowsheetVersions([]);
    setSelectedScenarioId("");
    setScenarios([]);
    if (!plantId) {
      setDictError(null);
      return;
    }

    setIsFlowsheetsLoading(true);
    setDictError(null);
    fetchFlowsheetVersionsForPlant(plantId)
      .then((data) => {
        setFlowsheetVersions(data);
        setFlowsheetVersionId((prev) => {
          if (prev) return prev;
          if (fromRun?.input.flowsheet_version_id) {
            return String(fromRun.input.flowsheet_version_id);
          }
          return prev;
        });
      })
      .catch(() => {
        setDictError("Не удалось загрузить версии схем");
      })
      .finally(() => setIsFlowsheetsLoading(false));
  }, [plantId, fromRun]);

  useEffect(() => {
    setSelectedScenarioId("");
    setScenarios([]);
    if (!flowsheetVersionId) return;
    setIsScenariosLoading(true);
    setScenariosError(null);
    fetchCalcScenariosByFlowsheetVersion(flowsheetVersionId)
      .then((items) => {
        setScenarios(items);
        const baseline = items.find((s) => s.is_baseline);
        if (baseline) {
          setSelectedScenarioId(baseline.id);
          updateField("scenario_name", baseline.name);
        }
      })
      .catch(() => setScenariosError("Не удалось загрузить сценарии"))
      .finally(() => setIsScenariosLoading(false));
  }, [flowsheetVersionId]);

  const validateForm = (): FieldErrors => {
    const errors: FieldErrors = {};
    if (!plantId) errors.plantId = "Укажите ID фабрики";
    if (!flowsheetVersionId) errors.flowsheetVersionId = "Укажите ID версии схемы";

    if (!form.feed.tonnage_tph || Number(form.feed.tonnage_tph) <= 0) {
      errors.feedTonnage = "Производительность должна быть больше 0";
    }
    if (!form.feed.p80_mm || Number(form.feed.p80_mm) <= 0) {
      errors.feedP80 = "P80 питания должно быть больше 0";
    }
    if (!form.feed.density_t_per_m3 || Number(form.feed.density_t_per_m3) <= 0) {
      errors.feedDensity = "Плотность должна быть больше 0";
    }

    if (!form.mill.power_installed_kw || Number(form.mill.power_installed_kw) <= 0) {
      errors.millPowerInstalled = "Установленная мощность должна быть больше 0";
    }
    if (!form.mill.power_draw_kw || Number(form.mill.power_draw_kw) <= 0) {
      errors.millPowerDraw = "Текущая мощность должна быть больше 0";
    }
    if (!form.mill.ball_charge_percent || Number(form.mill.ball_charge_percent) <= 0) {
      errors.millBallCharge = "Заполнение шарами должно быть больше 0";
    }
    if (!form.mill.speed_percent_critical || Number(form.mill.speed_percent_critical) <= 0) {
      errors.millSpeed = "Скорость должна быть больше 0";
    }

    if (!form.classifier.cut_size_p80_mm || Number(form.classifier.cut_size_p80_mm) <= 0) {
      errors.classifierCutSize = "Cut size P80 должно быть больше 0";
    }
    if (
      !form.classifier.circulating_load_percent ||
      Number(form.classifier.circulating_load_percent) <= 0
    ) {
      errors.classifierCirculatingLoad = "Циркуляционная нагрузка должна быть больше 0";
    }

    return errors;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setGeneralError(null);
    setFieldErrors({});
    const validationErrors = validateForm();
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      setGeneralError("Проверьте подсвеченные поля и исправьте ошибки.");
      return;
    }

    setIsSubmitting(true);
    setResult(null);
    try {
      const payload = {
        model_version: "grind_mvp_v1",
        plant_id: plantId.trim(),
        flowsheet_version_id: flowsheetVersionId.trim(),
        scenario_name: form.scenario_name,
        feed: {
          tonnage_tph: Number(form.feed.tonnage_tph),
          p80_mm: Number(form.feed.p80_mm),
          density_t_per_m3: Number(form.feed.density_t_per_m3),
        },
        mill: {
          type: form.mill.type,
          power_installed_kw: Number(form.mill.power_installed_kw),
          power_draw_kw: Number(form.mill.power_draw_kw),
          ball_charge_percent: Number(form.mill.ball_charge_percent),
          speed_percent_critical: Number(form.mill.speed_percent_critical),
        },
        classifier: {
          type: form.classifier.type,
          cut_size_p80_mm: Number(form.classifier.cut_size_p80_mm),
          circulating_load_percent: Number(form.classifier.circulating_load_percent),
        },
        options: { use_baseline_run_id: useBaseline && fromRun ? fromRun.id : null },
      };
      const resp = await api.post("/api/calc/grind-mvp-runs", payload);
      setResult(resp.data.result);
      setFieldErrors({});
      setGeneralError(null);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        const status = error.response.status;
        const data = error.response.data;
        if (status === 422 && Array.isArray(data.detail)) {
          const errors: FieldErrors = {};
          for (const item of data.detail) {
            const loc = item.loc || [];
            const msg = item.msg as string;
            const key = mapBackendPathToFieldKey(loc);
            if (key) {
              errors[key] = msg;
            }
          }
          setFieldErrors(errors);
          setGeneralError("Некоторые параметры заданы некорректно. Исправьте ошибки и повторите расчёт.");
          setIsSubmitting(false);
          return;
        }
        setGeneralError("Произошла ошибка при расчёте. Попробуйте ещё раз позже.");
      } else {
        setGeneralError("Произошла сетевая ошибка. Проверьте подключение к интернету.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const comparison: GrindMvpBaselineComparison | null =
    result && result.baseline_comparison ? result.baseline_comparison : null;

  return (
    <div className="page">
      <div className="card">
        <div className="page-header">
          <h1>Новый расчёт (grind_mvp_v1)</h1>
          <BackToHomeButton />
        </div>
        {dictError && <div className="general-error">{dictError}</div>}
        <form className="form" onSubmit={handleSubmit}>
          <label>
            Фабрика
            <select
              className={fieldErrors.plantId ? "input error" : "input"}
              value={plantId}
              onChange={(e) => setPlantId(e.target.value)}
              disabled={isPlantsLoading || plants.length === 0}
            >
              <option value="">Выберите фабрику...</option>
              {plants.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} (ID {p.id})
                </option>
              ))}
            </select>
            {fieldErrors.plantId && <div className="field-error">{fieldErrors.plantId}</div>}
          </label>
          <label>
            Версия схемы
            <select
              className={fieldErrors.flowsheetVersionId ? "input error" : "input"}
              value={flowsheetVersionId}
              onChange={(e) => setFlowsheetVersionId(e.target.value)}
              disabled={!plantId || isFlowsheetsLoading || flowsheetVersions.length === 0}
            >
              <option value="">Выберите версию схемы...</option>
              {flowsheetVersions.map((fv) => (
                <option key={fv.id} value={fv.id}>
                  {fv.name} (ID {fv.id})
                </option>
              ))}
            </select>
          {fieldErrors.flowsheetVersionId && (
              <div className="field-error">{fieldErrors.flowsheetVersionId}</div>
            )}
          </label>
          <label>
            Сценарий
            <select
              className="input"
              value={selectedScenarioId}
              onChange={(e) => {
                const value = e.target.value;
                setSelectedScenarioId(value);
                if (!value) {
                  updateField("scenario_name", "");
                  return;
                }
                const scenario = scenarios.find((s) => s.id === value);
                if (scenario) {
                  updateField("scenario_name", scenario.name);
                }
              }}
              disabled={!flowsheetVersionId || isScenariosLoading}
            >
              <option value="">
                {isScenariosLoading
                  ? "Загрузка сценариев…"
                  : scenarios.length === 0
                  ? "Нет сценариев для этой версии схемы"
                  : "— Выберите сценарий —"}
              </option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.is_baseline ? " (базовый)" : ""}
                </option>
              ))}
            </select>
            {scenariosError && <div className="field-error">{scenariosError}</div>}
          </label>
          <label>
            Название сценария
            <input
              className={fieldErrors.scenarioName ? "input error" : "input"}
              type="text"
              value={form.scenario_name}
              onChange={(e) => updateField("scenario_name", e.target.value)}
            />
            {fieldErrors.scenarioName && (
              <div className="field-error">{fieldErrors.scenarioName}</div>
            )}
          </label>

          {fromRun && (
            <label style={{ flexDirection: "row", gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={useBaseline}
                onChange={(e) => setUseBaseline(e.target.checked)}
              />
              Сравнить с расчётом №{fromRun.id} как с базовым
            </label>
          )}

          <h3>Питание</h3>
          <label>
            Производительность, т/ч
            <input
              className={fieldErrors.feedTonnage ? "input error" : "input"}
              type="number"
              value={form.feed.tonnage_tph}
              onChange={(e) => updateField("feed.tonnage_tph", parseFloat(e.target.value))}
            />
            {fieldErrors.feedTonnage && <div className="field-error">{fieldErrors.feedTonnage}</div>}
          </label>
          <label>
            P80 питания, мм
            <input
              className={fieldErrors.feedP80 ? "input error" : "input"}
              type="number"
              value={form.feed.p80_mm}
              onChange={(e) => updateField("feed.p80_mm", parseFloat(e.target.value))}
            />
            {fieldErrors.feedP80 && <div className="field-error">{fieldErrors.feedP80}</div>}
          </label>
          <label>
            Плотность, т/м³
            <input
              className={fieldErrors.feedDensity ? "input error" : "input"}
              type="number"
              value={form.feed.density_t_per_m3}
              onChange={(e) => updateField("feed.density_t_per_m3", parseFloat(e.target.value))}
            />
            {fieldErrors.feedDensity && <div className="field-error">{fieldErrors.feedDensity}</div>}
          </label>

          <h3>Мельница</h3>
          <label>
            Тип
            <select
              className={fieldErrors.millType ? "input error" : "input"}
              value={form.mill.type}
              onChange={(e) => updateField("mill.type", e.target.value)}
            >
              <option value="SAG">SAG</option>
              <option value="Ball">Ball</option>
              <option value="Rod">Rod</option>
            </select>
            {fieldErrors.millType && <div className="field-error">{fieldErrors.millType}</div>}
          </label>
          <label>
            Установленная мощность, кВт
            <input
              className={fieldErrors.millPowerInstalled ? "input error" : "input"}
              type="number"
              value={form.mill.power_installed_kw}
              onChange={(e) => updateField("mill.power_installed_kw", parseFloat(e.target.value))}
            />
            {fieldErrors.millPowerInstalled && (
              <div className="field-error">{fieldErrors.millPowerInstalled}</div>
            )}
          </label>
          <label>
            Текущая мощность, кВт
            <input
              className={fieldErrors.millPowerDraw ? "input error" : "input"}
              type="number"
              value={form.mill.power_draw_kw}
              onChange={(e) => updateField("mill.power_draw_kw", parseFloat(e.target.value))}
            />
            {fieldErrors.millPowerDraw && (
              <div className="field-error">{fieldErrors.millPowerDraw}</div>
            )}
          </label>
          <label>
            Заполнение шарами, %
            <input
              className={fieldErrors.millBallCharge ? "input error" : "input"}
              type="number"
              value={form.mill.ball_charge_percent}
              onChange={(e) => updateField("mill.ball_charge_percent", parseFloat(e.target.value))}
            />
            {fieldErrors.millBallCharge && (
              <div className="field-error">{fieldErrors.millBallCharge}</div>
            )}
          </label>
          <label>
            Скорость, % критической
            <input
              className={fieldErrors.millSpeed ? "input error" : "input"}
              type="number"
              value={form.mill.speed_percent_critical}
              onChange={(e) => updateField("mill.speed_percent_critical", parseFloat(e.target.value))}
            />
            {fieldErrors.millSpeed && <div className="field-error">{fieldErrors.millSpeed}</div>}
          </label>

          <h3>Классификатор</h3>
          <label>
            Тип
            <select
              className={fieldErrors.classifierType ? "input error" : "input"}
              value={form.classifier.type}
              onChange={(e) => updateField("classifier.type", e.target.value)}
            >
              <option value="cyclone">cyclone</option>
              <option value="screen">screen</option>
            </select>
            {fieldErrors.classifierType && (
              <div className="field-error">{fieldErrors.classifierType}</div>
            )}
          </label>
          <label>
            Cut size P80, мм
            <input
              className={fieldErrors.classifierCutSize ? "input error" : "input"}
              type="number"
              value={form.classifier.cut_size_p80_mm}
              onChange={(e) =>
                updateField("classifier.cut_size_p80_mm", parseFloat(e.target.value))
              }
            />
            {fieldErrors.classifierCutSize && (
              <div className="field-error">{fieldErrors.classifierCutSize}</div>
            )}
          </label>
          <label>
            Циркуляционная нагрузка, %
            <input
              className={fieldErrors.classifierCirculatingLoad ? "input error" : "input"}
              type="number"
              value={form.classifier.circulating_load_percent}
              onChange={(e) =>
                updateField("classifier.circulating_load_percent", parseFloat(e.target.value))
              }
            />
            {fieldErrors.classifierCirculatingLoad && (
              <div className="field-error">{fieldErrors.classifierCirculatingLoad}</div>
            )}
          </label>

          {generalError && <div className="general-error">{generalError}</div>}
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Считаем..." : "Рассчитать"}
          </button>
        </form>

        {result && (
          <div style={{ marginTop: 16 }}>
            <h2>Показатели</h2>
            <div className="grid">
              <div className="stat">
                <div className="stat-label">Производительность, т/ч</div>
                <div className="stat-value">{result.kpi.throughput_tph.toFixed(2)}</div>
              </div>
              <div className="stat">
                <div className="stat-label">P80 продукта, мм</div>
                <div className="stat-value">{result.kpi.product_p80_mm.toFixed(3)}</div>
              </div>
              <div className="stat">
                <div className="stat-label">Удельная энергия, кВт·ч/т</div>
                <div className="stat-value">{result.kpi.specific_energy_kwh_per_t.toFixed(2)}</div>
              </div>
              <div className="stat">
                <div className="stat-label">Циркуляционная нагрузка, %</div>
                <div className="stat-value">{result.kpi.circulating_load_percent.toFixed(1)}</div>
              </div>
              <div className="stat">
                <div className="stat-label">Использование мощности, %</div>
                <div className="stat-value">{result.kpi.mill_utilization_percent.toFixed(1)}</div>
              </div>
            </div>

            {comparison && (
              <div style={{ marginTop: 12 }}>
                <h3>Сравнение с базовым сценарием</h3>
                <p>Базовый расчёт: №{comparison.baseline_run_id}</p>
                <div className="grid">
                  <KpiDelta
                    label="Производительность, т/ч"
                    delta={comparison.throughput_delta_tph}
                    deltaPercent={comparison.throughput_delta_percent}
                  />
                  <KpiDelta
                    label="P80 продукта, мм"
                    delta={comparison.product_p80_delta_mm}
                  />
                  <KpiDelta
                    label="Удельная энергия, кВт·ч/т"
                    delta={comparison.specific_energy_delta_kwhpt}
                    deltaPercent={comparison.specific_energy_delta_percent}
                  />
                </div>
              </div>
            )}

            <h3>Гранулометрический состав питания</h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Размер, мм</th>
                  <th>Сумм., %</th>
                </tr>
              </thead>
              <tbody>
                {result.size_distribution.feed.map((p, idx) => (
                  <tr key={idx}>
                    <td>{p.size_mm}</td>
                    <td>{p.cum_percent}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h3>Гранулометрический состав продукта</h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Размер, мм</th>
                  <th>Сумм., %</th>
                </tr>
              </thead>
              <tbody>
                {result.size_distribution.product.map((p, idx) => (
                  <tr key={idx}>
                    <td>{p.size_mm}</td>
                    <td>{p.cum_percent}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default CalcRunPage;
