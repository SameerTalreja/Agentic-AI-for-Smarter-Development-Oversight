import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { History, Search as SearchIcon, ShieldAlert, Users, Clock } from "lucide-react";
import { api } from "../api/client";
import QueryIdBadge from "../components/QueryIdBadge";
import MarkdownAnswer from "../components/MarkdownAnswer";
import AutoCharts from "../components/AutoCharts";

const TRACK_META = {
  A: { label: "Query", icon: SearchIcon, color: "#4f46e5" },
  B: { label: "Audit", icon: ShieldAlert, color: "#dc2626" },
  C: { label: "Review Board", icon: Users, color: "#7c3aed" },
};

export default function HistoryPage() {
  const [runs, setRuns] = useState([]);
  const [trackFilter, setTrackFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadHistory = async () => {
    const params = trackFilter ? { track: trackFilter } : {};
    const res = await api.listHistory(params);
    setRuns(res.runs);
  };

  useEffect(() => {
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackFilter]);

  const openRun = async (queryId) => {
    setLoading(true);
    try {
      const detail = await api.getHistoryDetail(queryId);
      setSelected(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="agent-header-row">
        <div>
          <h1>History</h1>
          <p className="page-subtitle">Browse and inspect past runs across all agents.</p>
        </div>
        <div className="hero-illustration">
          <motion.div
            className="hero-orb hero-orb-1"
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            style={{ color: "#4f46e5" }}
          >
            <Clock size={16} />
          </motion.div>
          <div className="hero-search-icon" style={{ background: "linear-gradient(135deg, #4f46e5, #6366f1)" }}>
            <History size={28} strokeWidth={2.2} />
          </div>
        </div>
      </div>

      <div className="track-filter-row">
        {[
          { value: "", label: "All tracks" },
          { value: "A", label: "Query" },
          { value: "B", label: "Audit" },
          { value: "C", label: "Review Board" },
        ].map((t) => (
          <button
            key={t.value}
            className={`track-filter-chip ${trackFilter === t.value ? "active" : ""}`}
            onClick={() => setTrackFilter(t.value)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="history-layout">
        <div className="history-list">
          {runs.map((r) => {
            const meta = TRACK_META[r.track] || TRACK_META.A;
            const Icon = meta.icon;
            const isActive = selected && selected.query_id === r.query_id;
            return (
              <button
                key={r.query_id}
                className={`history-item ${isActive ? "history-item-active" : ""}`}
                onClick={() => openRun(r.query_id)}
              >
                <div className="history-item-top">
                  <span className="track-badge" style={{ background: meta.color }}>
                    <Icon size={11} style={{ marginRight: 4, verticalAlign: "-2px" }} />
                    {meta.label}
                  </span>
                  <QueryIdBadge queryId={r.query_id} />
                </div>
                <div className="history-question">{r.question}</div>
                <div className="history-date">{r.created_at}</div>
              </button>
            );
          })}
          {runs.length === 0 && (
            <div className="history-empty">
              <History size={28} strokeWidth={1.5} />
              <p>No past runs yet. Ask something on one of the agent pages.</p>
            </div>
          )}
        </div>

        <div className="history-detail">
          {loading && <p className="hint-text">Loading...</p>}
          {selected && !loading && (
            <>

              <h3>Question / Goal</h3>
              <p className="history-detail-question">{selected.question}</p>
               <a             
                href={api.getPdfUrl(selected.query_id)}
                className="btn-ghost btn-sm pdf-download-btn"
                download
              >
                Download PDF report
              </a>
              <h3>Final Answer</h3>
              <div className="final-answer">
                <MarkdownAnswer content={selected.final_answer || "(no answer recorded)"} />
              </div>
              <AutoCharts steps={selected.tool_calls} queryId={selected.query_id} />
             
              {/*<AgentTrace steps={selected.tool_calls} queryId={selected.query_id} />*/}
            </>
          )}
          {!selected && !loading && (
            <div className="history-empty">
              <SearchIcon size={28} strokeWidth={1.5} />
              <p>Select a run from the list to see its full trace.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}