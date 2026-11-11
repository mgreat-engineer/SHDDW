import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useApi, errMsg } from "@/lib/api";

const field = "w-full bg-[#F1F3F4] border border-[#DADCE0] rounded-lg px-3 py-2 text-sm outline-none focus:border-[#1A73E8]/50 transition-colors mt-1";

export default function TemplateDialog({ initial, onClose, onSaved }) {
  const api = useApi();
  const [f, setF] = useState({ name: "", label: "", sites: "", skill_id: "", instructions: "" });
  const [skills, setSkills] = useState([]);
  useEffect(() => {
    if (!initial) return;
    setF({ name: initial.name || "", label: initial.label || "", sites: (initial.urls || []).join("\n"), skill_id: initial.skill_id || "", instructions: initial.instructions || "" });
    api.get("/skills").then((r) => setSkills(r.data)).catch(() => {});
  }, [initial, api]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async (e) => {
    e.preventDefault();
    const body = { name: f.name, label: f.label, urls: f.sites.split("\n").map((s) => s.trim()).filter(Boolean), skill_id: f.skill_id || null, instructions: f.instructions };
    try { initial.id ? await api.put(`/templates/${initial.id}`, body) : await api.post("/templates", body); toast.success("Template saved"); onSaved(); }
    catch (err) { toast.error(errMsg(err)); }
  };
  return (
    <Dialog open={!!initial} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-white border-[#DADCE0] text-[#202124] max-w-lg" data-testid="template-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">{initial?.id ? "Edit template" : "Save as template"}</DialogTitle>
          <DialogDescription className="text-[#5F6368]">Reopens these sites in a fresh workspace with this client. Logins are not saved, so you sign in again each time.</DialogDescription>
        </DialogHeader>
        <form onSubmit={save} className="space-y-3">
          <label className="block text-xs text-[#5F6368]">Template name<input autoFocus value={f.name} onChange={set("name")} maxLength={60} className={field} data-testid="template-name-input" /></label>
          <label className="block text-xs text-[#5F6368]">Client or company<input value={f.label} onChange={set("label")} maxLength={80} className={field} data-testid="template-label-input" /></label>
          <label className="block text-xs text-[#5F6368]">Sites to open (one per line)<textarea value={f.sites} onChange={set("sites")} rows={4} className={`${field} font-mono text-xs`} data-testid="template-sites-input" /></label>
          <label className="block text-xs text-[#5F6368]">Start a skill when it opens (optional)
            <select value={f.skill_id} onChange={set("skill_id")} className={field} data-testid="template-skill-select">
              <option value="">Don't start anything</option>
              {skills.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          {f.skill_id && <label className="block text-xs text-[#5F6368]">Extra instructions for the skill<textarea value={f.instructions} onChange={set("instructions")} rows={2} className={field} data-testid="template-instructions-input" /></label>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="text-sm px-4 py-2 rounded-lg border border-[#DADCE0] text-[#3C4043] hover:bg-[#F1F3F4]" data-testid="template-cancel-button">Cancel</button>
            <button type="submit" className="text-sm px-4 py-2 rounded-lg bg-[#1A73E8] text-white font-semibold" data-testid="template-save-button">Save template</button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
