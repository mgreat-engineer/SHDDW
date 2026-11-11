import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Laptop, Cloud, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { useApi, errMsg, fmtTime } from "@/lib/api";
import ScheduleDialog, { DAYS } from "./ScheduleDialog";

const dayText = (days) => {
  const k = [...days].sort().join(",");
  if (k === "1,2,3,4,5") return "Weekdays";
  if (k === "0,1,2,3,4,5,6") return "Every day";
  if (k === "0,6") return "Weekends";
  return DAYS.filter(([, d]) => days.includes(d)).map(([n]) => n).join(", ");
};

export default function SchedulesPanel({ refresh, onSelectRun }) {
  const api = useApi();
  const [items, setItems] = useState(null);
  const [skills, setSkills] = useState(null);
  const [edit, setEdit] = useState(null);
  const load = useCallback(() => {
    api.get("/schedules").then((r) => setItems(r.data)).catch(() => setItems([]));
    api.get("/skills").then((r) => setSkills(r.data)).catch(() => setSkills([]));
  }, [api]);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load, refresh]);

  const toggle = async (s, enabled) => {
    try { await api.put(`/schedules/${s.id}`, { ...s, enabled }); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const del = async (s) => {
    if (!window.confirm(`Delete the schedule for "${s.skill_name}"?`)) return;
    try { await api.delete(`/schedules/${s.id}`); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  if (items === null || skills === null) return <p className="text-sm text-[#80868B] animate-pulse" data-testid="schedules-loading">Loading schedules…</p>;
  return (
    <div className="space-y-3" data-testid="schedules-panel">
      <p className="text-xs text-[#5F6368]">Skills that run by themselves. If your laptop is off at that time, the skill runs in the cloud instead.</p>
      <button onClick={() => setEdit({})} disabled={!skills.length} data-testid="schedule-create-button"
        className="w-full text-xs flex items-center justify-center gap-1.5 py-2 rounded-lg border border-dashed border-[#DADCE0] text-[#5F6368] hover:text-[#202124] hover:border-[#1A73E8]/40 disabled:opacity-40 transition-colors"><Plus className="h-3.5 w-3.5" />New schedule</button>
      {!skills.length && <p className="text-xs text-[#80868B]">Teach Shadow a skill first, then schedule it.</p>}
      {items.length === 0 && skills.length > 0 && <p className="text-sm text-[#80868B]" data-testid="schedules-empty">Nothing scheduled yet.</p>}
      {items.map((s) => (
        <div key={s.id} className={`rounded-lg border p-3 space-y-1.5 transition-opacity ${s.enabled ? "border-[#DADCE0] bg-white" : "border-[#DADCE0]/60 bg-[#F1F3F4]0 opacity-60"}`} data-testid={`schedule-item-${s.id}`}>
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-semibold leading-snug flex items-center gap-1.5"><CalendarClock className="h-4 w-4 text-[#1A73E8] shrink-0" />{s.skill_name}</p>
            <Switch checked={s.enabled} onCheckedChange={(v) => toggle(s, v)} data-testid={`schedule-toggle-${s.id}`} />
          </div>
          <p className="text-xs text-[#3C4043]">{dayText(s.days)} at {s.time} <span className="text-[#80868B]">({s.timezone})</span></p>
          <p className="text-[10px] font-mono text-[#80868B] flex items-center gap-1">{s.target === "laptop" ? <Laptop className="h-3 w-3" /> : <Cloud className="h-3 w-3" />}{s.target === "laptop" ? "laptop → cloud fallback" : "cloud"}{s.enabled && s.next_run_at ? ` · next ${fmtTime(s.next_run_at)}` : ""}</p>
          {s.last_run_at && (
            <p className="text-[10px] font-mono text-[#80868B]" data-testid={`schedule-last-${s.id}`}>
              last {fmtTime(s.last_run_at)} · <span className={s.last_status === "started" ? "text-[#1E8E3E]" : "text-[#B06000]"}>{s.last_status}</span>
              {s.last_run_id && <button onClick={() => onSelectRun(s.last_run_id)} className="ml-1 text-[#1A73E8] hover:underline" data-testid={`schedule-open-run-${s.id}`}>open</button>}
              {s.last_note && <span className="block text-[#80868B] normal-case">{s.last_note}</span>}
            </p>
          )}
          <div className="flex gap-3 pt-0.5">
            <button onClick={() => setEdit(s)} className="text-xs text-[#5F6368] hover:text-[#202124] flex items-center gap-1" data-testid={`schedule-edit-${s.id}`}><Pencil className="h-3 w-3" />Edit</button>
            <button onClick={() => del(s)} className="text-xs text-[#5F6368] hover:text-[#D93025] flex items-center gap-1" data-testid={`schedule-delete-${s.id}`}><Trash2 className="h-3 w-3" />Delete</button>
          </div>
        </div>
      ))}
      <ScheduleDialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)} skills={skills} initial={edit} onSaved={load} />
    </div>
  );
}
