import { useCallback, useEffect, useState } from "react";
import { useApi, fmtTime } from "@/lib/api";
import StatusBadge from "./StatusBadge";

export default function HistoryPanel({ refresh, onSelect, selectedId }) {
  const api = useApi();
  const [runs, setRuns] = useState([]);
  const load = useCallback(() => api.get("/runs").then((r) => setRuns(r.data)).catch(() => {}), [api]);
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, [load, refresh]);
  return (
    <div className="space-y-2" data-testid="history-panel">
      {runs.length === 0 && <p className="text-sm text-[#80868B]" data-testid="history-empty">No runs yet.</p>}
      {runs.map((r) => (
        <button key={r.id} onClick={() => onSelect(r.id)} data-testid={`history-item-${r.id}`}
          className={`w-full text-left rounded-lg border p-3 transition-colors ${selectedId === r.id ? "border-[#1A73E8]/50 bg-[#1A73E8]/5" : "border-[#DADCE0] bg-white hover:border-slate-600"}`}>
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm leading-snug line-clamp-2">{r.goal}</p>
            <StatusBadge status={r.status} testId={`history-status-badge-${r.id}`} />
          </div>
          <p className="text-[10px] font-mono text-[#80868B] mt-1.5">{fmtTime(r.created_at)} · {r.step_count} steps{r.skill_name ? ` · ${r.skill_name}` : ""}</p>
        </button>
      ))}
    </div>
  );
}
