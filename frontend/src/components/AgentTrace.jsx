import { useState, useEffect } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

export default function AgentTrace({ steps, forceOpen = false }) {
  const [expanded, setExpanded] = useState(forceOpen);

  useEffect(() => {
    if (forceOpen) setExpanded(true);
  }, [forceOpen]);

  if (!steps || steps.length === 0) {
    return <p className="trace-empty">No tool calls were made.</p>;
  }

  return (
    <div className="agent-trace-wrapper">
      {!forceOpen && (
        <button className="trace-toggle" onClick={() => setExpanded((e) => !e)}>
          {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          {expanded ? "Hide" : "Show"} reasoning ({steps.length} tool call{steps.length !== 1 ? "s" : ""})
        </button>
      )}
      {expanded && (
        <div className="agent-trace">
          {steps.map((step, i) => (
            <div className="trace-step" key={i}>
              <div className="trace-step-header">
                <span className="trace-step-number">#{step.step_number}</span>
                {step.agent_role && <span className="trace-agent-badge">{step.agent_role}</span>}
                <span className="trace-tool-name">{step.tool_name}</span>
              </div>
              <details className="trace-details">
                <summary>arguments</summary>
                <pre>{JSON.stringify(step.arguments, null, 2)}</pre>
              </details>
              <details className="trace-details">
                <summary>result</summary>
                <pre>{JSON.stringify(step.result, null, 2)}</pre>
              </details>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}