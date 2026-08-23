import { useState } from "react";

export default function QueryIdBadge({ queryId }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(queryId);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button className="query-id-badge" onClick={handleCopy} title="Click to copy">
      {queryId} {copied ? "✓ copied" : ""}
    </button>
  );
}