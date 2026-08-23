import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function DatasetSelector({ value, onChange }) {
  const [datasets, setDatasets] = useState([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api.listDatasets()
      .then((res) => setDatasets(res.datasets))
      .catch(() => setFailed(true));
  }, []);

  if (failed) {
    return (
      <span className="dataset-selector-error">
        ⚠ Backend unreachable — is it running on port 8000?
      </span>
    );
  }

  return (
    <select
      className="dataset-selector"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {datasets.map((d) => (
        <option key={d.id} value={d.id}>
          {d.name} {d.protected ? "(default)" : ""}
        </option>
      ))}
    </select>
  );
}