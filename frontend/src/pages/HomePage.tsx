import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getToken } from "../api/client";

type DashboardResponse = {
  user: { email: string };
  summary: { calc_runs_total?: number; scenarios_total?: number; comments_total?: number; projects_total?: number };
  projects: any[];
  member_projects: any[];
  recent_calc_runs: any[];
  recent_comments: any[];
};

export const HomePage = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      navigate("/login", { replace: true });
      return;
    }

    const fetchDashboard = async () => {
      try {
        setLoading(true);
        const resp = await api.get<DashboardResponse>("/api/me/dashboard");
        setData(resp.data);
      } catch (err) {
        setError("Не удалось загрузить данные");
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [navigate]);

  if (loading) {
    return (
      <div className="page">
        <div className="card">Загрузка...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <div className="card error">{error}</div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="page">
      <div className="card">
        <h1>GrindLab Dashboard</h1>
        <p>Email: <strong>{data.user?.email}</strong></p>
        <div className="grid">
          <div className="stat">
            <div className="stat-label">Проекты (owner)</div>
            <div className="stat-value">{data.projects?.length ?? 0}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Проекты (member)</div>
            <div className="stat-value">{data.member_projects?.length ?? 0}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Calc Runs</div>
            <div className="stat-value">{data.summary?.calc_runs_total ?? 0}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Сценарии</div>
            <div className="stat-value">{data.summary?.scenarios_total ?? 0}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Комментарии</div>
            <div className="stat-value">{data.summary?.comments_total ?? 0}</div>
          </div>
        </div>

        <section>
          <h2>Последние расчёты</h2>
          {data.recent_calc_runs?.length ? (
            <ul>
              {data.recent_calc_runs.map((run, idx) => (
                <li key={idx}>{run.id || run.scenario_name || "calc run"}</li>
              ))}
            </ul>
          ) : (
            <p>Нет расчётов</p>
          )}
        </section>

        <section>
          <h2>Последние комментарии</h2>
          {data.recent_comments?.length ? (
            <ul>
              {data.recent_comments.map((c, idx) => (
                <li key={idx}>{c.text || JSON.stringify(c)}</li>
              ))}
            </ul>
          ) : (
            <p>Нет комментариев</p>
          )}
        </section>
      </div>
    </div>
  );
};

export default HomePage;
