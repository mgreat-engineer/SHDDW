import { useCallback, useEffect, useState } from "react";
import { KeyRound, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg, fmtTime } from "@/lib/api";

export default function PasswordsPanel({ refresh }) {
  const api = useApi();
  const [items, setItems] = useState(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const importCsv = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setBusy(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await api.post("/passwords/import", fd);
      toast.success(`Imported ${r.data.saved} password(s)` + (r.data.skipped ? `, skipped ${r.data.skipped}` : ""));
      load();
    } catch (err) { toast.error(errMsg(err)); } finally { setBusy(false); }
  };
  const load = useCallback(() => api.get("/passwords").then((r) => setItems(r.data)).catch(() => setItems([])), [api]);
  useEffect(() => { load(); }, [load, refresh]);
  useEffect(() => { window.addEventListener("shadow:passwords", load); return () => window.removeEventListener("shadow:passwords", load); }, [load]);
  const del = async (p) => {
    if (!window.confirm(`Delete the saved password for ${p.username || "this login"} on ${p.origin}?`)) return;
    try { await api.delete(`/passwords/${p.id}`); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  if (items === null) return <p className="text-sm text-[#80868B] animate-pulse">Loading passwords…</p>;
  const shown = items.filter((p) => `${p.origin} ${p.username}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="space-y-3" data-testid="passwords-panel">
      <p className="text-xs text-[#5F6368]">When you sign in to a site, Shadow offers to save the password (encrypted). Use the key in the address bar to fill it, or let Shadow sign in during tasks — the AI never sees the password.</p>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search passwords" data-testid="passwords-search-input"
        className="w-full bg-[#F1F3F4] rounded-full px-4 py-2 text-sm outline-none focus:bg-white focus:ring-2 focus:ring-[#1A73E8]" />
      <details className="rounded-lg border border-[#DADCE0] p-3 text-xs text-[#5F6368]" data-testid="passwords-import-section">
        <summary className="cursor-pointer text-sm text-[#1A73E8] font-medium">Import passwords from Chrome</summary>
        <ol className="list-decimal pl-4 mt-2 space-y-1">
          <li>In Chrome, open <span className="font-mono">chrome://password-manager/settings</span></li>
          <li>Click <b>Export passwords</b> and save the CSV file</li>
          <li>Choose that file below, then delete the CSV from your computer</li>
        </ol>
        <label className="mt-3 inline-flex items-center gap-2 text-sm px-4 py-1.5 rounded-full bg-[#1A73E8] text-white cursor-pointer" data-testid="passwords-import-button">
          {busy ? "Importing…" : "Choose CSV file"}
          <input type="file" accept=".csv,text/csv" className="hidden" disabled={busy} onChange={importCsv} data-testid="passwords-import-input" />
        </label>
      </details>
      {shown.length === 0 && <p className="text-sm text-[#80868B]" data-testid="passwords-empty">No saved passwords yet.</p>}
      {shown.map((p) => (
        <div key={p.id} className="flex items-center gap-3 rounded-lg border border-[#DADCE0] p-3" data-testid={`password-item-${p.id}`}>
          <KeyRound className="h-4 w-4 text-[#5F6368] shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium truncate">{p.origin.replace(/^https?:\/\//, "")}</p>
            <p className="text-xs text-[#5F6368] truncate">{p.username || "(no username)"} · {fmtTime(p.updated_at)}</p>
          </div>
          <button onClick={() => del(p)} title="Delete" data-testid={`password-delete-${p.id}`} className="p-1.5 rounded-full text-[#5F6368] hover:text-[#D93025] hover:bg-[#F1F3F4]"><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
    </div>
  );
}
