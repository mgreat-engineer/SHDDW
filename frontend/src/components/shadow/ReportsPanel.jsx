import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useApi, fmtTime } from "@/lib/api";
import StatusBadge from "./StatusBadge";

const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
const today = () => new Date().toLocaleDateString("en-CA");
const shift = (d, n) => { const x = new Date(`${d}T12:00:00`); x.setDate(x.getDate() + n); return x.toLocaleDateString("en-CA"); };
const COUNTS = [["completed", "Finished", "text-[#00E676]"], ["needs_you", "Needs you", "text-[#FFB000]"], ["running", "Working", "text-[#00F0FF]"], ["failed", "Failed", "text-[#FF3B30]"], ["stopped", "Stopped", "text-slate-400"]];

function Counts({ counts, testId }) {
  return (
    <div className="grid grid-cols-5 gap-1" data-testid={testId}>
      {COUNTS.map(([k, t, c]) => (
        <div key={k} className="rounded-md bg-white/5 px-1 py-1.5 text-center">
          <p className={`font-mono text-sm font-semibold ${c}`} data-testid={`${testId}-${k}`}>{counts[k] || 0}</p>
          <p className="text-[10px] whitespace-nowrap text-slate-400">{t}</p>
        </div>
      ))}
    </div>
  );
}

export default function ReportsPanel({ refresh, onSelectRun }) {
  const api = useApi();
  const [date, setDate] = useState(today());
  const [data, setData] = useState(null);
  const load = useCallback(() => api.get("/reports/daily", { params: { date, tz: TZ } }).then((r) => setData(r.data)).catch(() => setData({ clients: [], totals: {}, total: 0 })), [api, date]);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load, refresh]);
  const nav = "p-1.5 rounded-md border border-[#262B3D] text-slate-400 hover:bg-white/5 disabled:opacity-30";
  return (
    <div className="space-y-3" data-testid="reports-panel">
      <div className="flex items-center gap-2">
        <button onClick={() => setDate(shift(date, -1))} className={nav} data-testid="report-prev-day"><ChevronLeft className="h-3.5 w-3.5" /></button>
        <input type="date" value={date} max={today()} onChange={(e) => e.target.value && setDate(e.target.value)} data-testid="report-date-input"
          className="flex-1 bg-[#181B26] border border-[#262B3D] rounded-md px-2 py-1 text-xs font-mono text-slate-200 outline-none [color-scheme:dark]" />
        <button onClick={() => setDate(shift(date, 1))} disabled={date >= today()} className={nav} data-testid="report-next-day"><ChevronRight className="h-3.5 w-3.5" /></button>
      </div>
      {!data ? <p className="text-sm text-slate-500 animate-pulse">Loading report…</p> : (
        <>
          <p className="text-xs text-slate-400" data-testid="report-total">{data.total} task{data.total === 1 ? "" : "s"} on this day · {TZ}</p>
          {data.total > 0 && <Counts counts={data.totals} testId="report-totals" />}
          {data.clients.length === 0 && <p className="text-sm text-slate-500" data-testid="report-empty">No tasks on this day.</p>}
          {data.clients.map((c, i) => (
            <div key={c.label} className="rounded-lg border border-[#262B3D] bg-[#181B26] p-3 space-y-2" data-testid={`report-client-${i}`}>
              <div>
                <p className="text-sm font-semibold" data-testid={`report-client-name-${i}`}>{c.label}</p>
                <p className="text-[10px] font-mono text-slate-500 truncate">{c.workspaces.join(" · ")}</p>
              </div>
              <Counts counts={c.counts} testId={`report-client-counts-${i}`} />
              <div className="space-y-1">
                {c.runs.map((r) => (
                  <button key={r.id} onClick={() => onSelectRun(r.id)} data-testid={`report-run-${r.id}`} className="w-full text-left rounded-md px-2 py-1.5 hover:bg-white/5 transition-colors">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs leading-snug line-clamp-2">{r.goal}</p>
                      <StatusBadge status={r.status} testId={`report-run-status-${r.id}`} />
                    </div>
                    <p className="text-[10px] font-mono text-slate-500 mt-0.5">{fmtTime(r.created_at)} · {r.workspace_name || "Main"} · {r.step_count} steps</p>
                    {r.question && ["waiting_input", "awaiting_approval"].includes(r.status) && <p className="text-[11px] text-[#FFB000] mt-0.5 line-clamp-2">{r.question}</p>}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
