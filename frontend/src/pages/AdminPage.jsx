import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Trash2, ShieldCheck, ShieldOff, RefreshCw, Download,
  Activity, CheckCircle2, XCircle, LayoutDashboard,
} from "lucide-react";
import { api } from "../api/client";
import AgentTrace from "../components/AgentTrace";
import MarkdownAnswer from "../components/MarkdownAnswer";

export default function AdminPage() {
  const [runs, setRuns] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [historyRes, datasetsRes, statsRes] = await Promise.all([
        api.listHistory({ limit: 100 }),
        api.listDatasets(),
        api.getDailyStats(14),
      ]);
      setRuns(historyRes.runs);
      setDatasets(datasetsRes.datasets);
      setStats(statsRes);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const openRun = async (queryId) => {
    const detail = await api.getHistoryDetail(queryId);
    setSelectedRun(detail);
  };

  const handleDeleteRun = async (queryId) => {
    if (!window.confirm(`Delete run ${queryId}? This cannot be undone.`)) return;
    await api.deleteQuery(queryId);
    if (selectedRun?.query_id === queryId) setSelectedRun(null);
    loadAll();
  };

  const handleDeleteDataset = async (datasetId, protectedFlag) => {
    if (protectedFlag) {
      alert("This dataset is protected and cannot be deleted.");
      return;
    }
    if (!window.confirm(`Delete dataset ${datasetId} and all its history? This cannot be undone.`)) return;
    await api.deleteDataset(datasetId);
    loadAll();
  };

  const handleToggleProtect = async (datasetId, currentlyProtected) => {
    await api.protectDataset(datasetId, !currentlyProtected);
    loadAll();
  };

  return (
    <div className="page admin-page">
      <div className="admin-header">
        <div>
          <h1>
            <LayoutDashboard size={22} style={{ verticalAlign: "-4px", marginRight: 8 }} />
            Admin Panel
          </h1>
          <p className="page-subtitle">
            Unlisted page — full trace visibility, dataset and history management.
          </p>
        </div>
        <button className="btn-ghost btn-sm" onClick={loadAll} disabled={loading}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {stats && (
        <div className="admin-stats-row">
          <motion.div className="admin-stat-card" whileHover={{ y: -2 }}>
            <div className="admin-stat-icon admin-stat-icon-blue">
              <Activity size={18} />
            </div>
            <div>
              <div className="admin-stat-value">{stats.total_runs}</div>
              <div className="admin-stat-label">Total runs (14 days)</div>
            </div>
          </motion.div>

          <motion.div className="admin-stat-card" whileHover={{ y: -2 }}>
            <div className="admin-stat-icon admin-stat-icon-green">
              <CheckCircle2 size={18} />
            </div>
            <div>
              <div className="admin-stat-value">{stats.total_completed}</div>
              <div className="admin-stat-label">Completed</div>
            </div>
          </motion.div>

          <motion.div className="admin-stat-card" whileHover={{ y: -2 }}>
            <div className="admin-stat-icon admin-stat-icon-red">
              <XCircle size={18} />
            </div>
            <div>
              <div className="admin-stat-value">{stats.total_failed}</div>
              <div className="admin-stat-label">Failed</div>
            </div>
          </motion.div>

          <motion.div className="admin-stat-card" whileHover={{ y: -2 }}>
            <div className="admin-stat-icon admin-stat-icon-purple">A</div>
            <div>
              <div className="admin-stat-value">{stats.total_by_track.A}</div>
              <div className="admin-stat-label">Query Agent runs</div>
            </div>
          </motion.div>

          <motion.div className="admin-stat-card" whileHover={{ y: -2 }}>
            <div className="admin-stat-icon admin-stat-icon-orange">B</div>
            <div>
              <div className="admin-stat-value">{stats.total_by_track.B}</div>
              <div className="admin-stat-label">Audit Agent runs</div>
            </div>
          </motion.div>

          <motion.div className="admin-stat-card" whileHover={{ y: -2 }}>
            <div className="admin-stat-icon admin-stat-icon-indigo">C</div>
            <div>
              <div className="admin-stat-value">{stats.total_by_track.C}</div>
              <div className="admin-stat-label">Review Board runs</div>
            </div>
          </motion.div>
        </div>
      )}

      {stats && stats.total_runs > 0 && (
        <div className="chart-card admin-dashboard-chart">
          <img src={api.getStatsChartUrl(14)} alt="Daily agent runs" className="chart-image" />
        </div>
      )}

      <div className="admin-grid">
        <section className="admin-section">
          <h2>Datasets ({datasets.length})</h2>
          <div className="admin-list">
            {datasets.map((d) => (
              <div className="admin-list-item" key={d.id}>
                <div className="admin-list-item-main">
                  <div className="admin-list-item-title">
                    {d.name}
                    {d.protected && <span className="protected-badge">protected</span>}
                  </div>
                  <div className="admin-list-item-sub mono">
                    {d.id} · {d.type} · {d.filename}
                  </div>
                </div>
                <div className="admin-list-item-actions">
                  <button
                    className="icon-btn"
                    title={d.protected ? "Unprotect" : "Protect (make permanent)"}
                    onClick={() => handleToggleProtect(d.id, d.protected)}
                  >
                    {d.protected ? <ShieldOff size={15} /> : <ShieldCheck size={15} />}
                  </button>
                  <button
                    className="icon-btn icon-btn-danger"
                    title="Delete dataset"
                    onClick={() => handleDeleteDataset(d.id, d.protected)}
                    disabled={d.protected}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="admin-section">
          <h2>Run History ({runs.length})</h2>
          <div className="admin-list">
            {runs.map((r) => (
              <div
                className={`admin-list-item admin-run-item ${
                  selectedRun?.query_id === r.query_id ? "admin-run-item-active" : ""
                }`}
                key={r.query_id}
              >
                <div className="admin-list-item-main" onClick={() => openRun(r.query_id)}>
                  <div className="admin-list-item-title">
                    <span className="track-badge">{r.track}</span> {r.question}
                  </div>
                  <div className="admin-list-item-sub mono">
                    {r.query_id} · {r.created_at}
                  </div>
                </div>
                <div className="admin-list-item-actions">
                  <a
                    className="icon-btn"
                    title="Download PDF (with trace)"
                    href={api.getAdminPdfUrl(r.query_id)}
                    download
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Download size={15} />
                  </a>
                  <button
                    className="icon-btn icon-btn-danger"
                    title="Delete run"
                    onClick={() => handleDeleteRun(r.query_id)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {selectedRun && (
        <section className="admin-detail-panel">
          <div className="admin-detail-header">
            <h2>Run Detail — {selectedRun.query_id}</h2>
            <a
              className="btn-ghost btn-sm"
              href={api.getAdminPdfUrl(selectedRun.query_id)}
              download
            >
              <Download size={14} /> Download PDF (with trace)
            </a>
          </div>
          <p>
            <strong>Question:</strong> {selectedRun.question}
          </p>
          <h3>Final Answer</h3>
          <div className="final-answer">
            <MarkdownAnswer content={selectedRun.final_answer || "(none)"} />
          </div>
          <h3>Full Tool Trace (always visible here)</h3>
          <AgentTrace steps={selectedRun.tool_calls} forceOpen />
        </section>
      )}
    </div>
  );
}