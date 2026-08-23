import { useState } from "react";
import { motion } from "framer-motion";
import {
  ShieldAlert, ClipboardList, ListChecks, AlertTriangle, Search, Zap,
} from "lucide-react";
import { api } from "../api/client";
import AgentTrace from "../components/AgentTrace";
import QueryIdBadge from "../components/QueryIdBadge";
import DatasetSelector from "../components/DatasetSelector";
import MarkdownAnswer from "../components/MarkdownAnswer";
import AutoCharts from "../components/AutoCharts";
import RunControls from "../components/RunControls";
import { useAgentStream } from "../hooks/useAgentStream";

const DEFAULT_GOAL =
  "Find the projects most at risk of failing or being mismanaged in this infrastructure portfolio.";

const EXAMPLE_GOALS = [
  { text: "Find the projects most at risk of failing or being mismanaged.", icon: ShieldAlert, color: "red" },
  { text: "Identify procurement irregularities across the portfolio.", icon: ClipboardList, color: "orange" },
  { text: "Find districts with the largest unspent 'Not Started' budgets.", icon: AlertTriangle, color: "purple" },
  { text: "Flag high-cost projects with no assigned contractor.", icon: Search, color: "blue" },
];

const FEATURES = [
  { icon: ListChecks, title: "Self-Generated Checklist", desc: "The agent decides what to check — not hardcoded by us." },
  { icon: Search, title: "Real Tool Execution", desc: "Every check runs against live filtered/aggregated data." },
  { icon: AlertTriangle, title: "Ranked Findings", desc: "Issues ordered by severity and impact, with real examples." },
  { icon: Zap, title: "Honest Coverage", desc: "If a check can't be computed, it says so — never invents." },
];

export default function AuditAgentPage() {
  const [datasetId, setDatasetId] = useState("default");
  const [goal, setGoal] = useState("");

  const { steps, plan, status, result, error, elapsedSeconds, start, abort } =
    useAgentStream("/api/audit/stream", "B");

  const runAudit = () => {
    start({ goal: goal || DEFAULT_GOAL, dataset_id: datasetId });
  };

  const loading = status === "running";

  return (
    <div className="page">
      <div className="agent-header-row">
        <div>
          <h1>Audit Agent</h1>
          <p className="page-subtitle">
            Give it a goal, not a checklist. It plans its own investigation, runs it, and reports back.
          </p>
        </div>
        <div className="hero-illustration">
          <motion.div
            className="hero-orb hero-orb-1"
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            style={{ color: "#dc2626" }}
          >
            <AlertTriangle size={16} />
          </motion.div>
          <motion.div
            className="hero-orb hero-orb-2"
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut", delay: 0.4 }}
            style={{ color: "#ea580c" }}
          >
            <ClipboardList size={16} />
          </motion.div>
          <div className="hero-search-icon" style={{ background: "linear-gradient(135deg, #dc2626, #ea580c)" }}>
            <ShieldAlert size={30} strokeWidth={2.2} />
          </div>
        </div>
      </div>

      <div className="search-bar-shell">
        <ShieldAlert size={18} className="search-bar-icon" />
        <input
          type="text"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runAudit()}
          placeholder={DEFAULT_GOAL}
          className="search-bar-input"
          disabled={loading}
        />
      </div>

      <div className="search-bar-controls">
        <DatasetSelector value={datasetId} onChange={setDatasetId} />
        <span className="hint-text">Leave blank to use the default goal</span>
        <button className="btn-primary" onClick={runAudit} disabled={loading}>
          {loading ? "Auditing..." : "Run Audit →"}
        </button>
      </div>

      {!result && !loading && status !== "cancelled" && (
        <>
          <h3 className="section-label">✨ Try these goals</h3>
          <div className="example-grid">
            {EXAMPLE_GOALS.map((g) => {
              const Icon = g.icon;
              return (
                <motion.button
                  key={g.text}
                  className={`example-card example-card-${g.color}`}
                  onClick={() => setGoal(g.text)}
                  whileHover={{ y: -3 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <span className={`example-icon example-icon-${g.color}`}>
                    <Icon size={18} />
                  </span>
                  <span className="example-text">{g.text}</span>
                </motion.button>
              );
            })}
          </div>

          <div className="feature-strip">
            {FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <div className="feature-strip-item" key={f.title}>
                  <span className="feature-strip-icon" style={{ color: "#dc2626" }}><Icon size={18} /></span>
                  <div>
                    <div className="feature-strip-title">{f.title}</div>
                    <div className="feature-strip-desc">{f.desc}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {error && <div className="error-box">{error}</div>}

      <RunControls status={status} elapsedSeconds={elapsedSeconds} onAbort={abort} track="B" />

      {loading && plan && plan.length > 0 && (
        <>
          <h3 className="section-label">Self-generated checklist (executing now)</h3>
          <div className="checklist-grid">
            {plan.map((check, i) => (
              <div className="checklist-item" key={i}>
                <span className="checklist-number">{i + 1}</span>
                <div>
                  <div className="checklist-name">{check.check_name}</div>
                  <div className="checklist-desc">{check.description}</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/*{loading && steps.length > 0 && (
        <div className="live-steps-preview">
          <AgentTrace steps={steps} forceOpen />
        </div>
      )}*/}

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

          {result?.plan && result.plan.length > 0 && (
            <>
              <h3>Self-generated checklist</h3>
              <div className="checklist-grid">
                {result.plan.map((check, i) => (
                  <div className="checklist-item" key={i}>
                    <span className="checklist-number">{i + 1}</span>
                    <div>
                      <div className="checklist-name">{check.check_name}</div>
                      <div className="checklist-desc">{check.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {result?.final_answer && (
            <>
              <h3>Ranked risk report</h3>
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