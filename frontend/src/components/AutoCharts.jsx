const BASE_URL = "http://127.0.0.1:8000";

export default function AutoCharts({ steps, queryId, maxCharts = 4 }) {
  if (!steps || steps.length === 0 || !queryId) return null;

  const chartable = steps.filter(
    (s) =>
      s.tool_name === "aggregate" &&
      s.result &&
      s.result.groups &&
      Object.keys(s.result.groups).length > 1 &&
      !s.result.error
  );

  if (chartable.length === 0) return null;

  const shown = chartable.slice(-maxCharts);

  return (
    <div className="auto-charts-grid">
      {shown.map((step) => (
        <div className="chart-card" key={step.step_number}>
          <img
            src={`${BASE_URL}/api/history/${queryId}/chart/${step.step_number}`}
            alt={`${step.result.operation} by ${step.result.group_by}`}
            className="chart-image"
            loading="lazy"
          />
        </div>
      ))}
    </div>
  );
}