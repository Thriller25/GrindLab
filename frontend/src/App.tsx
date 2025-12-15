import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { CalcRunPage } from "./pages/CalcRunPage";
import { CalcRunDetailPage } from "./pages/CalcRunDetailPage";
import { CompareCalcRunsPage } from "./pages/CompareCalcRunsPage";
import { CalcScenariosPage } from "./pages/CalcScenariosPage";

export const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<HomePage />} />
        <Route path="/calc-run" element={<CalcRunPage />} />
        <Route path="/calc-runs/:runId" element={<CalcRunDetailPage />} />
        <Route path="/calc-runs/compare" element={<CompareCalcRunsPage />} />
        <Route path="/calc-scenarios" element={<CalcScenariosPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
