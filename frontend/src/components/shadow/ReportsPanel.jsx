import { useCallback, useEffect, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { useApi, fmtTime } from "@/lib/api";
import StatusBadge from "./StatusBadge";

const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
const today = () => new Date().toLocaleDateString("en-CA");
const shift = (d, n) => { const x = new Date(`${d}T12:00:00`); x.setDate(x.getDate() + n); return x.toLocaleDateString("en-CA"); };
const COUNTS = [["completed", "Finished", "text-[#1E8E3E]"], ["needs_you", "Needs you", "text-[#B06000]"], ["running", "Working", "text-[#1A73E8]"], ["failed", "Failed", "text-[#D93025]"], ["stopped", "Stopped", "text-[#5F6368]"]];

function Counts({ counts, testId }) {
  return (
    <div className="grid grid-cols-5 gap-1" data-testid={testId}>
      {COUNTS.map(([k, t, c]) => (
        <div key={k} className="rounded-md bg-[#F1F3F4] px-1 py-1.5 text-center">
          <p className={`font-mono text-sm font-semibold ${c}`} data-testid={`${testId}-${k}`}>{counts[k] || 0}</p>
          <p className="text-[10px] whitespace-nowrap text-[#5F6368]">{t}</p>
        </div>
      ))}
    </div>
  );
}

export default function ReportsPanel({ refresh, onSelectRun }) {
  const api = useApi();
  const [date, setDate] = useState(today());
  const [calOpen, setCalOpen] = useState(false);
  const [data, setData] = useState(null);
  const load = useCallback(() => api.get("/reports/daily", { params: { date, tz: TZ } }).then((r) => setData(r.data)).catch(() => setData({ clients: [], totals: {}, total: 0 })), [api, date]);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load, refresh]);
  const nav = "p-1.5 rounded-md border border-[#DADCE0] text-[#5F6368] hover:bg-[#F1F3F4] disabled:opacity-30";
  return (
    <div className="space-y-3" data-testid="reports-panel">
      <div className="flex items-center gap-2">
        <button onClick={() => setDate(shift(date, -1))} className={nav} data-testid="report-prev-day"><ChevronLeft className="h-3.5 w-3.5" /></button>
        <Popover open={calOpen} onOpenChange={setCalOpen}>
          <PopoverTrigger asChild>
            <button data-testid="report-date-input" className="flex-1 flex items-center justify-center gap-1.5 bg-white border border-[#DADCE0] rounded-md px-2 py-1 text-xs text-[#202124] hover:bg-[#F1F3F4]">
              <CalendarDays className="h-3.5 w-3.5 text-[#5F6368]" />{new Date(`${date}T12:00:00`).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric", year: "numeric" })}
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="center">
            <Calendar mode="single" selected={new Date(`${date}T12:00:00`)} disabled={{ after: new Date() }}
              onSelect={(d) => { if (d) { setDate(d.toLocaleDateString("en-CA")); setCalOpen(false); } }} initialFocus data-testid="report-calendar" />
          </PopoverContent>
        </Popover>
        <button onClick={() => setDate(shift(date, 1))} disabled={date >= today()} className={nav} data-testid="report-next-day"><ChevronRight className="h-3.5 w-3.5" /></button>
      </div>
      {!data ? <p className="text-sm text-[#80868B] animate-pulse">Loading report…</p> : (
        <>
          <p className="text-xs text-[#5F6368]" data-testid="report-total">{data.total} task{data.total === 1 ? "" : "s"} on this day · {TZ}</p>
          {data.total > 0 && <Counts counts={data.totals} testId="report-totals" />}
          {data.clients.length === 0 && <p className="text-sm text-[#80868B]" data-testid="report-empty">No tasks on this day.</p>}
          {data.clients.map((c, i) => (
            <div key={c.label} className="rounded-lg border border-[#DADCE0] bg-white p-3 space-y-2" data-testid={`report-client-${i}`}>
              <div>
                <p className="text-sm font-semibold" data-testid={`report-client-name-${i}`}>{c.label}</p>
                <p className="text-[10px] font-mono text-[#80868B] truncate">{c.workspaces.join(" · ")}</p>
              </div>
              <Counts counts={c.counts} testId={`report-client-counts-${i}`} />
              <div className="space-y-1">
                {c.runs.map((r) => (
                  <button key={r.id} onClick={() => onSelectRun(r.id)} data-testid={`report-run-${r.id}`} className="w-full text-left rounded-md px-2 py-1.5 hover:bg-[#F1F3F4] transition-colors">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs leading-snug line-clamp-2">{r.goal}</p>
                      <StatusBadge status={r.status} testId={`report-run-status-${r.id}`} />
                    </div>
                    <p className="text-[10px] font-mono text-[#80868B] mt-0.5">{fmtTime(r.created_at)} · {r.workspace_name || "Main"} · {r.step_count} steps</p>
                    {r.question && ["waiting_input", "awaiting_approval"].includes(r.status) && <p className="text-[11px] text-[#B06000] mt-0.5 line-clamp-2">{r.question}</p>}
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
