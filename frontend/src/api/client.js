const BASE_URL = import.meta.env.VITE_API_URL;

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/api/health"),
    getPdfUrl: (queryId) => `${BASE_URL}/api/history/${queryId}/pdf`,
  getAdminPdfUrl: (queryId) => `${BASE_URL}/api/history/${queryId}/pdf/admin`,
  
  listDatasets: () => request("/api/datasets"),

  getQualityReport: (datasetId) =>
    request(`/api/datasets/${datasetId}/quality-report`),

  uploadDataset: async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE_URL}/api/datasets/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Upload failed: ${res.status}`);
    }
    return res.json();
  },

  runQuery: (question, datasetId) =>
    request("/api/query", {
      method: "POST",
      body: JSON.stringify({ question, dataset_id: datasetId }),
    }),

  runAudit: (goal, datasetId) =>
    request("/api/audit", {
      method: "POST",
      body: JSON.stringify({ goal, dataset_id: datasetId }),
    }),

  runReviewBoard: (task, datasetId) =>
    request("/api/review-board", {
      method: "POST",
      body: JSON.stringify({ task, dataset_id: datasetId }),
    }),

  listHistory: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/history${qs ? `?${qs}` : ""}`);
  },

  getHistoryDetail: (queryId) => request(`/api/history/${queryId}`),

    deleteDataset: (datasetId) =>
    request(`/api/datasets/${datasetId}`, { method: "DELETE" }),

  protectDataset: (datasetId, protectedValue = true) =>
    request(`/api/datasets/${datasetId}/protect?protected=${protectedValue}`, { method: "PATCH" }),

  deleteQuery: (queryId) =>
    request(`/api/history/${queryId}`, { method: "DELETE" }),

  getDailyStats: (days = 14) => request(`/api/history/stats/daily?days=${days}`),
  getStatsChartUrl: (days = 14) => `${BASE_URL}/api/history/stats/chart?days=${days}`,
};