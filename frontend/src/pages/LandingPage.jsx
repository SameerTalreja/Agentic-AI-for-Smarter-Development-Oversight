import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.12, duration: 0.6, ease: "easeOut" },
  }),
};

const stats = [
  { label: "Projects tracked", value: "4,083" },
  { label: "Districts covered", value: "39" },
  { label: "Portfolio value", value: "₨51.5B" },
  { label: "Agent tracks", value: "3" },
];

const features = [
  {
    title: "Query Agent",
    desc: "Ask plain-English questions. The agent plans, calls real tools, and cites the exact filters behind every number.",
    tag: "Track A",
  },
  {
    title: "Audit Agent",
    desc: "Give it a goal, not a checklist. It self-generates its own investigation plan and produces a ranked risk report.",
    tag: "Track B",
  },
  {
    title: "Review Board",
    desc: "Finance, Delivery, and Equity agents debate independently. A Coordinator resolves their disagreement into one recommendation.",
    tag: "Track C",
  },
];

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="landing">
      <div className="landing-bg-glow" />

      <motion.section
        className="landing-hero"
        initial="hidden"
        animate="visible"
      >
        <motion.span className="landing-eyebrow" variants={fadeUp} custom={0}>
          GOVERNMENT OF BALOCHISTAN · BSDI · PMTS Analyst 
        </motion.span>

        <motion.h1 className="landing-title" variants={fadeUp} custom={1}>
          Agentic AI for
          <br />
          <span className="landing-title-accent">Smarter Development Oversight</span>
        </motion.h1>

        <motion.p className="landing-lead" variants={fadeUp} custom={2}>
        An agentic AI system designed to help analyze, investigate, and monitor
        development projects under the Balochistan Special Development
        Initiative (BSDI). It turns complex project data into grounded insights, identifies
        potential risks, and supports faster, more transparent decision-making.
        </motion.p>

        <motion.div className="landing-cta-row" variants={fadeUp} custom={3}>
          <button className="btn-primary btn-lg" onClick={() => navigate("/query")}>
            Launch AI Agent →
          </button>
          <button className="btn-ghost btn-lg" onClick={() => navigate("/datasets")}>
            View the dataset
          </button>
        </motion.div>
      </motion.section>

      <motion.section
        className="landing-stats"
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.4 }}
      >
        {stats.map((s, i) => (
          <motion.div className="stat-tile" key={s.label} variants={fadeUp} custom={i}>
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </motion.div>
        ))}
      </motion.section>

      <motion.section
        className="landing-features"
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.2 }}
      >
        <motion.h2 variants={fadeUp} custom={0}>Three ways to investigate</motion.h2>
        <div className="feature-grid">
          {features.map((f, i) => (
            <motion.div className="feature-card" key={f.title} variants={fadeUp} custom={i + 1}>
              <span className="feature-tag">{f.tag}</span>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </motion.section>

      <motion.section
        className="landing-about"
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.3 }}
      >
        <motion.div variants={fadeUp} custom={0}>
          <h2>About this project</h2>
          <p>
            This system is built on the PMTS Projects List — a real
            government development portfolio spanning 39 districts of
            Balochistan, Pakistan, covering water schemes, schools, roads,
            health facilities, and more. The data is deliberately messy:
            inconsistent phone formats, near-duplicate agency names, and
            thousands of missing values.
          </p>
          <p>
            Every agent here is required to ground its answers in real tool
            calls, acknowledge missing data honestly, and never invent a
            number it hasn't actually retrieved. The full reasoning trace —
            every tool call, every filter — stays visible and auditable.
          </p>
        </motion.div>
      </motion.section>

  <footer className="landing-footer">
  <div className="footer-main">
    <span>Agentic AI Development Intelligence · BSDI</span>
    <span>Concept & Development · Sameer Talreja</span>
  </div>

  <span className="footer-tagline">
    Built for intelligent analysis, transparency, and data-driven development oversight.
  </span>
</footer>
    
  </div>
          
  );
  }
