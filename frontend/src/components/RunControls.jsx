import { Square, Clock } from "lucide-react";
import { getEstimatedSeconds } from "../hooks/useAgentStream";

export default function RunControls({ status, elapsedSeconds, onAbort, track }) {
  const estimate = getEstimatedSeconds(track);

  if (status === "running") {
    return (
      <div className="run-controls">
        <div className="run-timer">
          <Clock size={14} />
          <span>{elapsedSeconds}s elapsed</span>
          {estimate && <span className="run-estimate">· usually ~{estimate}s based on your past runs</span>}
        </div>
        <button className="btn-abort" onClick={onAbort}>
          <Square size={13} fill="currentColor" />
          Abort
        </button>
      </div>
    );
  }

  if (!estimate) return null;

  return (
    <div className="run-estimate-standalone">
      <Clock size={13} />
      Usually takes ~{estimate}s, based on your last runs
    </div>
  );
}
