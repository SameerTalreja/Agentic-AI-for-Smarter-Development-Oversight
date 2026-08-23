import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Database, UploadCloud, ShieldCheck, AlertCircle, Copy } from "lucide-react";
import { api } from "../api/client";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState([]);
  const [qualityReport, setQualityReport] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const loadDatasets = async () => {
    const res = await api.listDatasets();
    setDatasets(res.datasets);
  };

  useEffect(() => {
    loadDatasets();
  }, []);

  const viewQuality = async (id, type) => {
    setSelectedId(id);
    setQualityReport(null);
    setError(null);
    if (type === "document") {
      return; // documents don't have a tabular quality report
    }
    try {
      const report = await api.getQualityReport(id);
      setQualityReport(report);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const newDataset = await api.uploadDataset(file);
      await loadDatasets();
      viewQuality(newDataset.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <div className="page">
      <div className="agent-header-row">
        <div>
          <h1>Datasets</h1>
          <p className="page-subtitle">
            The default PMTS Projects dataset is always available and protected. Upload additional CSV/XLSX files to query them too.
          </p>
        </div>
        <div className="hero-illustration">
          <motion.div
            className="hero-orb hero-orb-1"
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            style={{ color: "#0d9488" }}
          >
            <ShieldCheck size={16} />
          </motion.div>
          <div className="hero-search-icon" style={{ background: "linear-gradient(135deg, #0d9488, #0891b2)" }}>
            <Database size={28} strokeWidth={2.2} />
          </div>
        </div>
      </div>

      <label className="upload-box">
        <UploadCloud size={26} strokeWidth={1.8} style={{ marginBottom: 8, color: "var(--primary)" }} />
        <div>{uploading ? "Uploading and analyzing..." : "Click to upload a CSV or XLSX file"}</div>
        <div className="upload-box-hint">CSV, XLSX, PDF, or DOCX — quality report or document indexing runs automatically</div>
        <input
          type="file"
          accept=".csv,.xlsx,.xls,.pdf,.docx"
          onChange={handleUpload}
          style={{ display: "none" }}
        />
      </label>

      {error && <div className="error-box"><AlertCircle size={14} style={{ verticalAlign: "-2px", marginRight: 6 }} />{error}</div>}

      <h3 className="section-label">Available datasets</h3>
      <div className="dataset-grid">
        {datasets.map((d) => (
          <motion.div
            key={d.id}
            className={`dataset-card ${selectedId === d.id ? "dataset-card-active" : ""}`}
            onClick={() => viewQuality(d.id, d.type)}
            whileHover={{ y: -3 }}
          >
            <div className="dataset-card-icon">
              <Database size={16} />
            </div>
            <h3>{d.name} {d.protected && <span className="protected-badge">default</span>}</h3>
            <p>{d.filename}</p>
            <p className="dataset-meta">schema: {d.detected_schema || "generic"}</p>
          </motion.div>
        ))}
      </div>
       {selectedId && datasets.find((d) => d.id === selectedId)?.type === "document" && (
        <div className="quality-report">
          <h2>Document Indexed</h2>
          <p className="hint-text">
            This is a document dataset — it's searched semantically rather than queried like a spreadsheet.
            Ask about it on the Query Agent page.
          </p>
        </div>
      )} 
      {qualityReport && (
        <div className="quality-report">
          <div className="quality-report-header">
            <h2>Data Quality Report</h2>
            <button className="query-id-badge" onClick={() => navigator.clipboard.writeText(selectedId)}>
              <Copy size={12} style={{ verticalAlign: "-2px", marginRight: 4 }} />{selectedId}
            </button>
          </div>
          <div className="quality-stat-row">
            <div className="quality-stat">
              <div className="quality-stat-value">{qualityReport.total_rows ?? "—"}</div>
              <div className="quality-stat-label">Total rows</div>
            </div>
            <div className="quality-stat">
              <div className="quality-stat-value">{Object.keys(qualityReport.missing_by_column || {}).length}</div>
              <div className="quality-stat-label">Columns with missing data</div>
            </div>
            <div className="quality-stat">
              <div className="quality-stat-value">{Object.keys(qualityReport.anomalies || {}).length}</div>
              <div className="quality-stat-label">Anomalies flagged</div>
            </div>
          </div>

          <h3>Missing values by column</h3>
          {Object.keys(qualityReport.missing_by_column || {}).length === 0 ? (
            <p className="hint-text">No missing values detected.</p>
          ) : (
            <table className="quality-table">
              <thead><tr><th>Column</th><th>Missing</th><th>%</th></tr></thead>
              <tbody>
                {Object.entries(qualityReport.missing_by_column || {}).map(([col, info]) => (
                  <tr key={col}>
                    <td>{col}</td>
                    <td>{info.missing}</td>
                    <td>
                      <span className={`missing-pct ${info.pct > 50 ? "missing-pct-high" : info.pct > 15 ? "missing-pct-mid" : "missing-pct-low"}`}>
                        {info.pct}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Format issues</h3>
          <pre>{JSON.stringify(qualityReport.format_issues, null, 2) || "{}"}</pre>

          <h3>Near-duplicate categories</h3>
          <pre>{JSON.stringify(qualityReport.near_duplicate_categories, null, 2) || "{}"}</pre>

          <h3>Anomalies</h3>
          <pre>{JSON.stringify(qualityReport.anomalies, null, 2) || "{}"}</pre>
        </div>
      )}
    </div>
  );
}