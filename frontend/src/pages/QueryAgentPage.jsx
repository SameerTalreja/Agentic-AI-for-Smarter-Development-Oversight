import { useState } from "react";
import { motion } from "framer-motion";
import {
  Search, Droplet, GraduationCap, Heart, Construction, TrendingUp, Map,
  Zap, ShieldCheck, History, MessageSquareText, ChevronDown,
} from "lucide-react";
import { api } from "../api/client";
import AgentTrace from "../components/AgentTrace";
import QueryIdBadge from "../components/QueryIdBadge";
import DatasetSelector from "../components/DatasetSelector";
import MarkdownAnswer from "../components/MarkdownAnswer";
import AutoCharts from "../components/AutoCharts";
import RunControls from "../components/RunControls";
import { useAgentStream } from "../hooks/useAgentStream";

const EXAMPLE_QUESTIONS = [
  { text: "How many water projects in Kech are completed?", icon: Droplet, color: "blue" },
  { text: "What's the total budget of all Not Started projects?", icon: TrendingUp, color: "purple" },
  { text: "Which district has the most education projects?", icon: GraduationCap, color: "green" },
  { text: "List the 5 most expensive health projects.", icon: Heart, color: "red" },
  { text: "Show all ongoing road projects in Balochistan.", icon: Construction, color: "orange" },
  { text: "What's the average cost of completed projects?", icon: Map, color: "teal" },
];

const FEATURES = [
  { icon: Zap, title: "Tool-Grounded Answers", desc: "Every number comes from a real query, never a guess." },
  { icon: ShieldCheck, title: "Honest About Gaps", desc: "Flags missing data instead of hiding it." },
  { icon: MessageSquareText, title: "Visible Reasoning", desc: "Every tool call and filter is shown, not hidden." },
  { icon: History, title: "Query History", desc: "Every run gets an ID you can look up later." },
];

export default function QueryAgentPage() {
  const [datasetId, setDatasetId] = useState("default");
  const [question, setQuestion] = useState("");
  const [showFilters, setShowFilters] = useState(false);

  const { steps, status, result, error, elapsedSeconds, start, abort } =
    useAgentStream("/api/query/stream", "A");

  const runQuery = (q) => {
    const finalQuestion = q ?? question;
    if (!finalQuestion.trim()) return;
    start({ question: finalQuestion, dataset_id: datasetId });
  };

  const loading = status === "running";

  return (
    <div className="page">
      <div className="agent-header-row">
        <div>
          <h1>Query Agent</h1>
          <p className="page-subtitle">
            Ask anything about the projects dataset and get tool-grounded, cited answers.
          </p>
        </div>
        <div className="hero-illustration">
          <motion.div
            className="hero-orb hero-orb-1"
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          >
            <TrendingUp size={18} />
          </motion.div>
          <motion.div
            className="hero-orb hero-orb-2"
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut", delay: 0.4 }}
          >
            <Droplet size={16} />
          </motion.div>
          <div className="hero-search-icon">
            <Search size={30} strokeWidth={2.2} />
          </div>
        </div>
      </div>

      <div className="search-bar-shell">
        <Search size={18} className="search-bar-icon" />
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runQuery()}
          placeholder="Ask about the dataset..."
          className="search-bar-input"
          disabled={loading}
        />
      </div>

      <div className="search-bar-controls">
        <div className="filter-dropdown-wrap">
          <button className="btn-ghost btn-sm" onClick={() => setShowFilters((s) => !s)}>
            {datasetId === "default" ? "Projects Dataset" : datasetId}
            <ChevronDown size={14} />
          </button>
          {showFilters && (
            <div className="filter-dropdown-panel">
              <DatasetSelector value={datasetId} onChange={(v) => { setDatasetId(v); setShowFilters(false); }} />
            </div>
          )}
        </div>
        <span className="hint-text">Press <kbd>Enter</kbd> to ask</span>
        <button className="btn-primary" onClick={() => runQuery()} disabled={loading}>
          {loading ? "Thinking..." : "Ask →"}
        </button>
      </div>

      {!result && !loading && status !== "cancelled" && (
        <>
          <h3 className="section-label">✨ Try these questions</h3>
          <div className="example-grid">
            {EXAMPLE_QUESTIONS.map((q) => {
              const Icon = q.icon;
              return (
                <motion.button
                  key={q.text}
                  className={`example-card example-card-${q.color}`}
                  onClick={() => { setQuestion(q.text); runQuery(q.text); }}
                  whileHover={{ y: -3 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <span className={`example-icon example-icon-${q.color}`}>
                    <Icon size={18} />
                  </span>
                  <span className="example-text">{q.text}</span>
                </motion.button>
              );
            })}
          </div>

          <div className="feature-strip">
            {FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <div className="feature-strip-item" key={f.title}>
                  <span className="feature-strip-icon"><Icon size={18} /></span>
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

      <RunControls status={status} elapsedSeconds={elapsedSeconds} onAbort={abort} track="A" />

      {/* {loading && steps.length > 0 && (
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
          {result?.final_answer && (
            <div className="final-answer">
              <MarkdownAnswer content={result.final_answer} />
            </div>
          )}
          {result && <AutoCharts steps={result.steps} queryId={result.query_id} />}
          
        </div>
      )}
    </div>
  );
}