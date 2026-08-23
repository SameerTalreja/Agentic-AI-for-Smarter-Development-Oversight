import { motion } from "framer-motion";
import { TrendingUp, HeartHandshake, Scale, Gavel, Check, Loader2 } from "lucide-react";

const AGENT_ICONS = {
  "Finance Agent": TrendingUp,
  "Delivery Agent": HeartHandshake,
  "Equity Agent": Scale,
  "Coordinator": Gavel,
};

const STATUS_LABEL = { pending: "Waiting", running: "Working...", done: "Done" };

export default function SpecialistProgress({ specialists, coordinatorRunning }) {
  const entries = Object.entries(specialists);
  if (entries.length === 0) return null;

  const allSpecialistsDone = entries.every(([, s]) => s === "done");

  return (
    <div className="specialist-progress">
      {entries.map(([name, status]) => {
        const Icon = AGENT_ICONS[name] || TrendingUp;
        return (
          <motion.div
            key={name}
            className={`specialist-progress-item specialist-progress-${status}`}
            animate={status === "running" ? { scale: [1, 1.02, 1] } : {}}
            transition={{ duration: 1.2, repeat: status === "running" ? Infinity : 0 }}
          >
            <span className="specialist-progress-icon"><Icon size={16} /></span>
            <span className="specialist-progress-name">{name}</span>
            <span className="specialist-progress-status">
              {status === "done" && <Check size={13} />}
              {status === "running" && <Loader2 size={13} className="spin" />}
              {STATUS_LABEL[status]}
            </span>
          </motion.div>
        );
      })}

      <motion.div
        className={`specialist-progress-item ${
          allSpecialistsDone
            ? coordinatorRunning
              ? "specialist-progress-running"
              : "specialist-progress-done"
            : "specialist-progress-pending"
        }`}
        animate={coordinatorRunning ? { scale: [1, 1.02, 1] } : {}}
        transition={{ duration: 1.2, repeat: coordinatorRunning ? Infinity : 0 }}
      >
        <span className="specialist-progress-icon"><Gavel size={16} /></span>
        <span className="specialist-progress-name">Coordinator</span>
        <span className="specialist-progress-status">
          {!allSpecialistsDone && "Waiting for specialists"}
          {allSpecialistsDone && coordinatorRunning && (
            <>
              <Loader2 size={13} className="spin" /> Deliberating...
            </>
          )}
          {allSpecialistsDone && !coordinatorRunning && "—"}
        </span>
      </motion.div>
    </div>
  );
}