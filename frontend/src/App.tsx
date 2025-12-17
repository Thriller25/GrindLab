import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { CalcRunPage } from "./pages/CalcRunPage";
import { CalcScenariosPage } from "./pages/CalcScenariosPage";
import { ProjectPage } from "./pages/ProjectPage";

export const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<HomePage />} />
        <Route path="/calc-run" element={<CalcRunPage />} />
        <Route path="/calc-scenarios" element={<CalcScenariosPage />} />
        <Route path="/projects/:projectId" element={<ProjectPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
