import { useNavigate } from "react-router-dom";

export function BackToHomeButton() {
  const navigate = useNavigate();
  return (
    <button type="button" className="back-to-home-button" onClick={() => navigate("/")}>
      На главную
    </button>
  );
}

export default BackToHomeButton;
