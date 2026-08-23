import { motion } from "framer-motion";

export default function LoadingPulse({ label = "Thinking..." }) {
  return (
    <div className="loading-pulse">
      <div className="pulse-dots">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="pulse-dot"
            animate={{ opacity: [0.3, 1, 0.3], scale: [0.85, 1, 0.85] }}
            transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.15 }}
          />
        ))}
      </div>
      <span>{label}</span>
    </div>
  );
}