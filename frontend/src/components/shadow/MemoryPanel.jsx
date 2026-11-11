import { useCallback, useEffect, useState } from "react";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg } from "@/lib/api";

function MemoryItem({ m, onSave, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(m.content);
  return (
    <div className="group rounded-lg bg-white border border-[#DADCE0] p-3" data-testid={`memory-item-${m.id}`}>
      {editing ? (
        <div className="flex gap-2">
          <textarea value={val} onChange={(e) => setVal(e.target.value)} rows={2} className="flex-1 bg-[#F1F3F4] border border-[#DADCE0] rounded p-2 text-sm outline-none" data-testid={`memory-edit-input-${m.id}`} />
          <div className="flex flex-col gap-1">
            <button onClick={() => { onSave(m.id, val); setEditing(false); }} className="text-[#1E8E3E]" data-testid={`memory-save-button-${m.id}`}><Check className="h-4 w-4" /></button>
            <button onClick={() => setEditing(false)} className="text-[#80868B]"><X className="h-4 w-4" /></button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <p className="text-sm flex-1 leading-snug">{m.content}</p>
          <div className="flex gap-2 opacity-50 group-hover:opacity-100 transition-opacity">
            <button onClick={() => setEditing(true)} data-testid={`memory-edit-button-${m.id}`}><Pencil className="h-3.5 w-3.5" /></button>
            <button onClick={() => onDelete(m.id)} className="hover:text-[#D93025]" data-testid={`memory-delete-button-${m.id}`}><Trash2 className="h-3.5 w-3.5" /></button>
          </div>
        </div>
      )}
      <p className="text-[10px] font-mono text-[#80868B] mt-1.5">{m.source === "agent" ? "learned during a task" : "added by you"}</p>
    </div>
  );
}

export default function MemoryPanel() {
  const api = useApi();
  const [items, setItems] = useState([]);
  const [text, setText] = useState("");
  const load = useCallback(() => api.get("/memories").then((r) => setItems(r.data)).catch(() => {}), [api]);
  useEffect(() => { load(); }, [load]);
  const wrap = (fn) => async (...a) => { try { await fn(...a); load(); } catch (e) { toast.error(errMsg(e)); } };
  const add = wrap(async () => { if (!text.trim()) return; await api.post("/memories", { content: text }); setText(""); });
  const save = wrap((id, content) => api.put(`/memories/${id}`, { content }));
  const del = wrap((id) => api.delete(`/memories/${id}`));

  return (
    <div className="space-y-3" data-testid="memory-panel">
      <p className="text-xs text-[#5F6368]">Facts and preferences Shadow uses on every task.</p>
      <div className="flex gap-2">
        <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} placeholder='e.g. "Always choose PDF"'
          className="flex-1 bg-white border border-[#DADCE0] rounded-lg px-3 py-2 text-sm outline-none focus:border-[#1A73E8]/50" data-testid="memory-add-input" />
        <button onClick={add} className="h-9 w-9 rounded-lg bg-[#1A73E8] text-white flex items-center justify-center" data-testid="memory-add-button"><Plus className="h-4 w-4" /></button>
      </div>
      {items.length === 0 && <p className="text-sm text-[#80868B]" data-testid="memory-empty">Nothing remembered yet.</p>}
      {items.map((m) => <MemoryItem key={m.id} m={m} onSave={save} onDelete={del} />)}
    </div>
  );
}
