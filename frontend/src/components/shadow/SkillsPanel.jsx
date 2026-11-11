import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Eye, Pencil, Play, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useApi, errMsg, fmtTime } from "@/lib/api";
import SkillEditor from "./SkillEditor";
import ScheduleDialog from "./ScheduleDialog";

const BLANK = { name: "", description: "", steps: [""], parameters: [] };

export default function SkillsPanel({ refresh, onRun, onPreview }) {
  const api = useApi();
  const [skills, setSkills] = useState([]);
  const [edit, setEdit] = useState(null);
  const [sched, setSched] = useState(null);
  const load = useCallback(() => api.get("/skills").then((r) => setSkills(r.data)).catch(() => {}), [api]);
  useEffect(() => { load(); }, [load, refresh]);

  const save = async () => {
    const body = { ...edit, steps: edit.steps.filter((s) => s.trim()) };
    try { edit.id ? await api.put(`/skills/${edit.id}`, body) : await api.post("/skills", body); setEdit(null); load(); toast.success("Skill saved"); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const del = async (s) => {
    if (!window.confirm(`Delete skill "${s.name}"?`)) return;
    try { await api.delete(`/skills/${s.id}`); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="space-y-3" data-testid="skills-panel">
      <button onClick={() => setEdit(BLANK)} className="w-full text-xs flex items-center justify-center gap-1.5 py-2 rounded-lg border border-dashed border-[#DADCE0] text-[#5F6368] hover:text-[#202124] hover:border-[#1A73E8]/40 transition-colors" data-testid="skill-create-button"><Plus className="h-3.5 w-3.5" />Write a skill by hand</button>
      {skills.length === 0 && <p className="text-sm text-[#80868B] leading-relaxed" data-testid="skills-empty">No skills yet. Press <span className="text-[#D93025]">Watch me</span>, do a task in the browser, then Stop — Shadow learns it.</p>}
      {skills.map((s, i) => (
        <div key={s.id} className="group rounded-lg bg-white border border-[#DADCE0] p-3 hover:border-[#1A73E8]/30 transition-colors fade-up" style={{ animationDelay: `${i * 40}ms` }} data-testid={`skill-card-${s.id}`}>
          <div className="flex items-start justify-between gap-2">
            <p className="font-semibold text-sm leading-snug">{s.name}</p>
            <button onClick={() => onRun(s)} className="shrink-0 h-7 w-7 rounded-md bg-[#1A73E8]/15 text-[#1A73E8] flex items-center justify-center hover:bg-[#1A73E8]/25" data-testid={`skill-run-button-${s.id}`} title="Run now"><Play className="h-3.5 w-3.5" /></button>
          </div>
          <p className="text-xs text-[#5F6368] mt-1 line-clamp-2">{s.description}</p>
          <div className="flex items-center justify-between mt-2">
            <span className="text-[10px] font-mono text-[#80868B]">{s.steps?.length || 0} steps · {fmtTime(s.updated_at)}</span>
            <div className="flex gap-2 opacity-60 group-hover:opacity-100 transition-opacity">
              <button onClick={() => onPreview(s)} title="Preview (dry run)" data-testid={`skill-preview-button-${s.id}`} className="hover:text-[#B06000]"><Eye className="h-3.5 w-3.5" /></button>
              <button onClick={() => setSched({ skill_id: s.id })} title="Schedule" data-testid={`skill-schedule-button-${s.id}`} className="hover:text-[#1A73E8]"><CalendarClock className="h-3.5 w-3.5" /></button>
              <button onClick={() => setEdit(s)} data-testid={`skill-edit-button-${s.id}`}><Pencil className="h-3.5 w-3.5" /></button>
              <button onClick={() => del(s)} className="hover:text-[#D93025]" data-testid={`skill-delete-button-${s.id}`}><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          </div>
          {s.history?.length > 0 && <p className="text-[10px] text-[#1E8E3E] mt-1.5">Improved {s.history.length}× from your corrections</p>}
        </div>
      ))}
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="bg-white border-[#DADCE0] max-w-2xl" data-testid="skill-edit-dialog">
          <DialogHeader><DialogTitle className="font-display">{edit?.id ? "Edit skill" : "New skill"}</DialogTitle></DialogHeader>
          {edit && <SkillEditor skill={edit} onChange={setEdit} />}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setEdit(null)}>Cancel</Button>
            <Button onClick={save} disabled={!edit?.name?.trim()} data-testid="skill-edit-save-button">Save</Button>
          </div>
        </DialogContent>
      </Dialog>
      <ScheduleDialog open={!!sched} onOpenChange={(o) => !o && setSched(null)} skills={skills} initial={sched} onSaved={() => toast("See it under Schedules")} />
    </div>
  );
}
