import { useState } from "react";
import { motion } from "framer-motion";
import {
  Users, TrendingUp, HeartHandshake, Scale, Gavel, MessageSquareWarning,
} from "lucide-react";
import { api } from "../api/client";
import AgentTrace from "../components/AgentTrace";
import QueryIdBadge from "../components/QueryIdBadge";
import DatasetSelector from "../components/DatasetSelector";
import MarkdownAnswer from "../components/MarkdownAnswer";
import AutoCharts from "../components/AutoCharts";
import RunControls from "../components/RunControls";
import SpecialistProgress from "../components/SpecialistProgress";
import { useAgentStream } from "../hooks/useAgentStream";

const DEFAULT_TASK =
  "We have an extra PKR 2 billion (2000 M) to allocate. Which currently 'Not Started' projects should be funded first, and why?";

const EXAMPLE_TASKS = [
  { text: "We have PKR 2 billion. Which 'Not Started' projects should be funded first?", icon: Gavel, color: "purple" },
  { text: "We have PKR 500 million. Which projects should be funded first?", icon: TrendingUp, color: "green" },
  { text: "PKR 1 billion is earmarked for water and health projects only.", icon: HeartHandshake, color: "red" },
  { text: "PKR 2 billion must be spent in the 5 most underserved districts.", icon: Scale, color: "blue" },
];

const AGENT_ICONS = {
  "FinanceAgent": TrendingUp,
  "Finance Agent": TrendingUp,
  "DeliveryRiskAgent": HeartHandshake,
  "DeliveryAgent": HeartHandshake,
  "Delivery Agent": HeartHandshake,
  "EquityAgent": Scale,
  "Equity Agent": Scale,
};

function iconFor(agentName) {
  return AGENT_ICONS[agentName] || Users;
}

export default function ReviewBoardPage() {
  const [datasetId, setDatasetId] = useState("default");
  const [task, setTask] = useState("");

  const { steps, specialists, status, result, error, elapsedSeconds, start, abort } =
    useAgentStream("/api/review-board/stream", "C");

  const runBoard = () => {
    start(
      { task: task || DEFAULT_TASK, dataset_id: datasetId },
      ["Finance Agent", "Delivery Agent", "Equity Agent"]
    );
  };

  const loading = status === "running";

  return (
    <div className="page">
      <div className="agent-header-row">
        <div>
          <h1>Multi-Agent Review Board</h1>
          <p className="page-subtitle">
            Finance, Delivery, and Equity agents investigate independently. A Coordinator resolves their disagreement.
          </p>
        </div>
        <div className="hero-illustration">
          <motion.div
            className="hero-orb hero-orb-1"
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            style={{ color: "#7c3aed" }}
          >
            <Scale size={16} />
          </motion.div>
          <motion.div
            className="hero-orb hero-orb-2"
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut", delay: 0.4 }}
            style={{ color: "#16a34a" }}
          >
            <TrendingUp size={16} />
          </motion.div>
          <div className="hero-search-icon" style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)" }}>
            <Gavel size={28} strokeWidth={2.2} />
          </div>
        </div>
      </div>

      <div className="search-bar-shell">
        <Gavel size={18} className="search-bar-icon" />
        <input
          type="text"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runBoard()}
          placeholder={DEFAULT_TASK}
          className="search-bar-input"
          disabled={loading}
        />
      </div>

      <div className="search-bar-controls">
        <DatasetSelector value={datasetId} onChange={setDatasetId} />
        <span className="hint-text">Board runs take a few minutes — 4 separate agent loops</span>
        <button className="btn-primary" onClick={runBoard} disabled={loading}>
          {loading ? "Deliberating..." : "Convene Board →"}
        </button>
      </div>

      {!result && !loading && status !== "cancelled" && (
        <>
          <h3 className="section-label">✨ Try these tasks</h3>
          <div className="example-grid">
            {EXAMPLE_TASKS.map((t) => {
              const Icon = t.icon;
              return (
                <motion.button
                  key={t.text}
                  className={`example-card example-card-${t.color}`}
                  onClick={() => setTask(t.text)}
                  whileHover={{ y: -3 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <span className={`example-icon example-icon-${t.color}`}>
                    <Icon size={18} />
                  </span>
                  <span className="example-text">{t.text}</span>
                </motion.button>
              );
            })}
          </div>
        </>
      )}

      {error && <div className="error-box">{error}</div>}

      <RunControls status={status} elapsedSeconds={elapsedSeconds} onAbort={abort} track="C" />

      {loading && (
        <SpecialistProgress
          specialists={specialists}
          coordinatorRunning={Object.values(specialists).every((s) => s === "done") && loading}
        />
      )}

     

      {(result || status === "cancelled") && (
        <div className="result-card">
          <div className="result-header">
            {result?.query_id && <QueryIdBadge queryId={result.query_id} />}
            <span className={`stopped-reason ${status === "cancelled" ? "stopped-reason-cancelled" : ""}`}>
              {status === "cancelled" ? "cancelled" : result?.stopped_reason}
            </span>
            <span className="elapsed-time">⏱ {elapsedSeconds}s</span>
            {result?.query_id && (
              <a
                href={api.getPdfUrl(result.query_id)}
                className="btn-ghost btn-sm"
                download
              >
                Download PDF
              </a>
            )}
          </div>

          {result?.plan && (
            <>
              <h3>Specialist findings</h3>
              <div className="specialist-grid">
                {result.plan.map((finding, i) => {
                  const Icon = iconFor(finding.agent);
                  return (
                    <div key={i} className="specialist-finding specialist-finding-v2">
                      <div className="specialist-header">
                        <span className="specialist-icon"><Icon size={16} /></span>
                        <h4>{finding.agent}</h4>
                      </div>
                      <ul>
                        {(finding.findings || []).map((f, j) => (
                          <li key={j}>
                            <span className={`severity severity-${f.severity}`}>{f.severity}</span>
                            {" "}
                            <strong>{f.finding}</strong> — {f.evidence}
                          </li>
                        ))}
                      </ul>
                      <p className="finding-recommendation">{finding.recommendation}</p>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {result?.final_answer && (
            <>
              <h3>
                <MessageSquareWarning size={16} style={{ verticalAlign: "-2px", marginRight: "6px" }} />
                Coordinator's final recommendation
              </h3>
              <div className="final-answer">
                <MarkdownAnswer content={result.final_answer} />
              </div>
            </>
          )}

          {result && <AutoCharts steps={result.steps} queryId={result.query_id} />}

         
        </div>
      )}
    </div>
  );
}