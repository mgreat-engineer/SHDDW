import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useApi, errMsg } from "@/lib/api";

export const DAYS = [["Sun", 0], ["Mon", 1], ["Tue", 2], ["Wed", 3], ["Thu", 4], ["Fri", 5], ["Sat", 6]];
const TIMES = Array.from({ length: 96 }, (_, i) => `${String(Math.floor(i / 4)).padStart(2, "0")}:${String((i % 4) * 15).padStart(2, "0")}`);
const PRESETS = { Weekdays: [1, 2, 3, 4, 5], "Every day": [0, 1, 2, 3, 4, 5, 6], Weekends: [0, 6] };
const tz = () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

export default function ScheduleDialog({ open, onOpenChange, skills, initial, onSaved }) {
  const api = useApi();
  const [f, setF] = useState(null);
  useEffect(() => {
    if (open) setF(initial?.id ? { ...initial } : { skill_id: initial?.skill_id || skills[0]?.id || "", days: [1, 2, 3, 4, 5], time: "08:00", target: "laptop", instructions: "", enabled: true, timezone: tz() });
  }, [open, initial, skills]);
  if (!f) return null;
  const set = (k, v) => setF({ ...f, [k]: v });
  const toggleDay = (d) => set("days", f.days.includes(d) ? f.days.filter((x) => x !== d) : [...f.days, d]);
  const save = async () => {
    const body = { skill_id: f.skill_id, days: f.days, time: f.time, timezone: f.timezone || tz(), target: f.target, instructions: f.instructions, enabled: f.enabled };
    try { f.id ? await api.put(`/schedules/${f.id}`, body) : await api.post("/schedules", body); toast.success("Schedule saved"); onSaved(); onOpenChange(false); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white border-[#DADCE0] max-w-lg" data-testid="schedule-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">{f.id ? "Edit schedule" : "Schedule a skill"}</DialogTitle>
          <DialogDescription>Times are in your time zone ({f.timezone || tz()}), on quarter hours.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">Skill</label>
            <Select value={f.skill_id} onValueChange={(v) => set("skill_id", v)}>
              <SelectTrigger className="mt-1 bg-[#F1F3F4]" data-testid="schedule-skill-select"><SelectValue placeholder="Pick a skill" /></SelectTrigger>
              <SelectContent>{skills.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">Days</label>
              <div className="flex gap-2">{Object.entries(PRESETS).map(([k, v]) => <button key={k} onClick={() => set("days", v)} className="text-[11px] text-[#1A73E8] hover:underline" data-testid={`schedule-preset-${k.replace(" ", "-").toLowerCase()}`}>{k}</button>)}</div>
            </div>
            <div className="mt-1 grid grid-cols-7 gap-1.5">
              {DAYS.map(([n, d]) => (
                <button key={d} onClick={() => toggleDay(d)} data-testid={`schedule-day-${d}`}
                  className={`py-2 rounded-lg text-xs font-semibold border transition-colors ${f.days.includes(d) ? "bg-[#1A73E8]/15 border-[#1A73E8]/50 text-[#1A73E8]" : "border-[#DADCE0] text-[#5F6368] hover:bg-[#F1F3F4]"}`}>{n}</button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">Time</label>
              <Select value={f.time} onValueChange={(v) => set("time", v)}>
                <SelectTrigger className="mt-1 bg-[#F1F3F4]" data-testid="schedule-time-select"><SelectValue /></SelectTrigger>
                <SelectContent className="max-h-64">{TIMES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">Run on</label>
              <Select value={f.target} onValueChange={(v) => set("target", v)}>
                <SelectTrigger className="mt-1 bg-[#F1F3F4]" data-testid="schedule-target-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="laptop">My laptop (cloud if it's off)</SelectItem>
                  <SelectItem value="cloud">Cloud</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <label className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">Extra instructions (optional)</label>
            <input value={f.instructions || ""} onChange={(e) => set("instructions", e.target.value)} placeholder="e.g. use yesterday's date" data-testid="schedule-instructions-input"
              className="mt-1 w-full bg-[#F1F3F4] border border-[#DADCE0] rounded-md px-3 py-2 text-sm outline-none focus:border-[#1A73E8]/50" />
          </div>
          <p className="text-[11px] text-[#80868B]">Risky steps (pay, send, delete) still wait for your OK unless you gave standing permission.</p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button onClick={save} disabled={!f.skill_id || !f.days.length} data-testid="schedule-save-button">Save schedule</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
