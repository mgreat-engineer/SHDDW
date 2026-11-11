import { useCallback, useEffect, useState } from "react";
import { BookmarkPlus, ExternalLink, Pencil, PlayCircle, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg } from "@/lib/api";
import TemplateDialog from "./TemplateDialog";

export default function TemplatesPanel({ refresh, current, onOpened }) {
  const api = useApi();
  const [items, setItems] = useState(null);
  const [edit, setEdit] = useState(null);
  const [busy, setBusy] = useState(null);
  const load = useCallback(() => api.get("/templates").then((r) => setItems(r.data)).catch(() => setItems([])), [api]);
  useEffect(() => { load(); }, [load, refresh]);

  const open = async (t) => {
    setBusy(t.id);
    try {
      const r = await api.post(`/templates/${t.id}/open`);
      onOpened(r.data.group, r.data.run);
      if (r.data.run_error) toast.error(r.data.run_error); else toast.success(r.data.run ? `${t.name} opened — ${t.skill_name} started` : `${t.name} opened`);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(null); }
  };
  const del = async (t) => {
    if (!window.confirm(`Delete template "${t.name}"?`)) return;
    try { await api.delete(`/templates/${t.id}`); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  if (items === null) return <p className="text-sm text-[#80868B] animate-pulse">Loading templates…</p>;
  return (
    <div className="space-y-3" data-testid="templates-panel">
      <p className="text-xs text-[#5F6368]">Save a workspace's sites and client once, then reopen it in one click — for any process Shadow has learned.</p>
      <button onClick={() => setEdit({ name: current?.name || "", label: current?.label || "", urls: current?.urls || [] })} data-testid="template-save-current-button"
        className="w-full text-xs flex items-center justify-center gap-1.5 py-2 rounded-lg border border-dashed border-[#DADCE0] text-[#5F6368] hover:text-[#202124] hover:border-[#1A73E8]/40 transition-colors">
        <BookmarkPlus className="h-3.5 w-3.5" />Save "{current?.name || "this workspace"}" as template
      </button>
      {items.length === 0 && <p className="text-sm text-[#80868B]" data-testid="templates-empty">No templates yet.</p>}
      {items.map((t) => (
        <div key={t.id} className="rounded-lg border border-[#DADCE0] bg-white p-3 space-y-1.5" data-testid={`template-item-${t.id}`}>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate" data-testid={`template-name-${t.id}`}>{t.name}</p>
              {t.label && <p className="text-[11px] text-[#1A73E8]/90 truncate">{t.label}</p>}
            </div>
            <button onClick={() => open(t)} disabled={busy === t.id} data-testid={`template-open-${t.id}`} title="Open in a new workspace"
              className="shrink-0 flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-[#1A73E8] text-white font-semibold disabled:opacity-50"><ExternalLink className="h-3.5 w-3.5" />{busy === t.id ? "Opening…" : "Open"}</button>
          </div>
          <p className="text-[10px] font-mono text-[#80868B] truncate" title={t.urls.join("\n")}>{t.urls.length} site{t.urls.length === 1 ? "" : "s"}{t.urls[0] ? ` · ${t.urls[0].replace(/^https?:\/\//, "")}` : ""}</p>
          {t.skill_name && <p className="text-[11px] text-[#3C4043] flex items-center gap-1"><PlayCircle className="h-3 w-3 text-[#1E8E3E]" />Starts “{t.skill_name}”</p>}
          <div className="flex gap-3 pt-0.5">
            <button onClick={() => setEdit(t)} className="text-xs text-[#5F6368] hover:text-[#202124] flex items-center gap-1" data-testid={`template-edit-${t.id}`}><Pencil className="h-3 w-3" />Edit</button>
            <button onClick={() => del(t)} className="text-xs text-[#5F6368] hover:text-[#D93025] flex items-center gap-1" data-testid={`template-delete-${t.id}`}><Trash2 className="h-3 w-3" />Delete</button>
          </div>
        </div>
      ))}
      <TemplateDialog initial={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }} />
    </div>
  );
}
