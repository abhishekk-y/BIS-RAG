import { BrowserRouter, Routes, Route, Navigate } from "react-router";
import LandingPage from "./components/LandingPage";
import DashboardPage from "./components/DashboardPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}