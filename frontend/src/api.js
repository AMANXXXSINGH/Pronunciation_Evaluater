const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function evaluateAudio({
  audioBlob,
  expectedText,
  language,
  modelName,
}) {
  const fd = new FormData();
  fd.append("audio", audioBlob, "audio.webm");
  fd.append("expected_text", expectedText ?? "");
  if (language) fd.append("language", language);
  if (modelName) fd.append("model_name", modelName);

  const res = await fetch(`${API_BASE}/api/evaluate`, {
    method: "POST",
    body: fd,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Evaluate failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function fetchHistory({ limit = 20 } = {}) {
  const res = await fetch(
    `${API_BASE}/api/history?limit=${encodeURIComponent(limit)}`,
  );
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`History failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function deleteHistory() {
  const res = await fetch(`${API_BASE}/api/history`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Delete history failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function deleteHistoryItem({ attemptId }) {
  const res = await fetch(
    `${API_BASE}/api/history/${encodeURIComponent(attemptId)}`,
    {
      method: "DELETE",
    },
  );
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Delete history item failed (${res.status}): ${text}`);
  }
  return res.json();
}
