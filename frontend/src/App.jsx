import { BrowserRouter, Routes, Route, NavLink, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import LandingPage from "./pages/LandingPage";
import QueryAgentPage from "./pages/QueryAgentPage";
import AuditAgentPage from "./pages/AuditAgentPage";
import ReviewBoardPage from "./pages/ReviewBoardPage";
import HistoryPage from "./pages/HistoryPage";
import DatasetsPage from "./pages/DatasetsPage";
import "./index.css";
import AdminPage from "./pages/AdminPage";

function AnimatedRoutes() {
  const location = useLocation();
  const isLanding = location.pathname === "/";

  return (
    <div className="app-shell">
      {!isLanding && (
        <nav className="sidebar">
          <div className="sidebar-brand">
            <div className="brand-mark">BSDI</div>
            <span className="app-title">Agentic AI for
Smarter Development Oversight</span>
          </div>

          <div className="nav-group">
            <div className="nav-group-label">Workspace</div>
            <NavLink to="/query" className="nav-link">Query Agent</NavLink>
            <NavLink to="/audit" className="nav-link">Audit Agent</NavLink>
            <NavLink to="/review-board" className="nav-link">Review Board</NavLink>
          </div>

          <div className="nav-group">
            <div className="nav-group-label">Data</div>
            <NavLink to="/datasets" className="nav-link">Datasets</NavLink>
          </div>

          <div className="nav-group">
            <div className="nav-group-label">Activity</div>
            <NavLink to="/history" className="nav-link">History</NavLink>
          </div>

          <div className="sidebar-footer">
            <div>Open Source</div>
            <div className="sidebar-footer-sub">MIT Licensed</div>
          </div>
        </nav>
      )}

      <main className={isLanding ? "main-content-full" : "main-content"}>
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            <Routes location={location}>
              <Route path="/" element={<LandingPage />} />
              <Route path="/query" element={<QueryAgentPage />} />
              <Route path="/audit" element={<AuditAgentPage />} />
              <Route path="/review-board" element={<ReviewBoardPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/datasets" element={<DatasetsPage />} />
              <Route path="/admin_11" element={<AdminPage />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AnimatedRoutes />
    </BrowserRouter>
  );
}