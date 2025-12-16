import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api/client";

export const LoginPage = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append("username", email);
      params.append("password", password);
      const response = await api.post("/api/auth/token", params, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      const { access_token } = response.data;
      if (access_token) {
        setToken(access_token);
        navigate("/", { replace: true });
      } else {
        setError("Не удалось получить токен");
      }
    } catch (err) {
      setError("Неверный логин или пароль");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="card">
        <h1>GrindLab — Login</h1>
        <form onSubmit={handleSubmit} className="form">
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Пароль
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <div className="error">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? "Входим..." : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
