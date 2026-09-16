import { useEffect, useState } from "react";
import { subscribeApiLog, type ApiCall } from "@/api/client";

/** Live list of every backend endpoint the UI has called, newest first. */
export function ApiActivity() {
  const [calls, setCalls] = useState<ApiCall[]>([]);
  useEffect(() => subscribeApiLog(setCalls), []);
  const recent = [...calls].reverse().slice(0, 8);
  return (
    <div className="panel">
      <h2>API activity <span className="count">{calls.length} calls</span></h2>
      <div className="api-log">
        {recent.map((c) => (
          <div key={c.id} className={`api-row${c.status && c.status >= 400 ? " bad" : ""}${c.status === null ? " bad" : ""}`}>
            <span className={`method ${c.method.toLowerCase()}`}>{c.method}</span>
            <span className="path" title={c.path}>{c.path.replace(/\?.*$/, "")}</span>
            <span className="status">{c.status ?? "ERR"}</span>
            <span className="ms">{Math.round(c.ms)} ms</span>
          </div>
        ))}
        {recent.length === 0 && <div className="hint">No calls yet.</div>}
      </div>
      <a className="swagger-link" href="/api/docs" target="_blank" rel="noreferrer">Open Swagger UI ↗</a>
    </div>
  );
}
