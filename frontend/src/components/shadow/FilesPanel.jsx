import { useCallback, useEffect, useState } from "react";
import { Download, Trash2, UploadCloud } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg, fmtSize, fmtTime, saveBlob } from "@/lib/api";

const SRC = { download: "text-[#1A73E8]", upload: "text-[#5F6368]", generated: "text-[#1E8E3E]" };

function LaptopFiles({ api }) {
  const [files, setFiles] = useState(null);
  useEffect(() => { api.get("/target/files").then((r) => setFiles(r.data)).catch(() => setFiles([])); }, [api]);
  return (
    <div className="space-y-1.5" data-testid="laptop-files">
      <p className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">On your laptop (allowed folders)</p>
      {files === null && <p className="text-xs text-[#80868B] animate-pulse">Loading…</p>}
      {files?.length === 0 && <p className="text-xs text-[#80868B]">No files in your allowed folders yet.</p>}
      {(files || []).map((f) => (
        <div key={f.name} className="flex items-center gap-2 rounded-md bg-white border border-[#DADCE0] px-3 py-2" data-testid={`laptop-file-${f.name}`}>
          <p className="text-xs truncate flex-1 font-mono" title={f.name}>{f.name}</p>
          <span className="text-[10px] font-mono text-[#80868B]">{fmtSize(f.size)}</span>
        </div>
      ))}
      <p className="text-[10px] text-[#80868B] pt-1">Downloads are saved straight into your chosen folder. Cloud files below are used only when Shadow works in the cloud.</p>
    </div>
  );
}

export default function FilesPanel({ refresh, target }) {
  const api = useApi();
  const [files, setFiles] = useState([]);
  const [drag, setDrag] = useState(false);
  const load = useCallback(() => api.get("/files").then((r) => setFiles(r.data)).catch(() => {}), [api]);
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load, refresh]);

  const upload = async (list) => {
    for (const f of list) {
      const fd = new FormData(); fd.append("file", f);
      try { await api.post("/files", fd); toast.success(`Added ${f.name}`); } catch (e) { toast.error(errMsg(e)); }
    }
    load();
  };
  const del = async (f) => { try { await api.delete(`/files/${f.id}`); load(); } catch (e) { toast.error(errMsg(e)); } };

  return (
    <div className="space-y-3" data-testid="files-panel">
      {target?.target === "laptop" && target?.helper_online && <LaptopFiles api={api} key={refresh} />}
      <label onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
        className={`flex flex-col items-center justify-center gap-1.5 py-6 rounded-lg border border-dashed cursor-pointer transition-colors ${drag ? "border-[#1A73E8] bg-[#1A73E8]/10" : "border-[#DADCE0] hover:border-[#1A73E8]/40"}`} data-testid="files-dropzone">
        <UploadCloud className="h-5 w-5 text-[#5F6368]" />
        <span className="text-xs text-[#5F6368]">Drop files or click — Shadow can upload them to websites</span>
        <input type="file" multiple className="hidden" onChange={(e) => upload(e.target.files)} data-testid="files-upload-input" />
      </label>
      {files.length === 0 && <p className="text-sm text-[#80868B]" data-testid="files-empty">Downloads from the browser land here.</p>}
      {files.map((f) => (
        <div key={f.id} className="group flex items-center gap-3 rounded-lg bg-white border border-[#DADCE0] px-3 py-2.5" data-testid={`file-item-${f.id}`}>
          <span className="text-[10px] font-mono uppercase w-10 text-center py-1 rounded bg-[#F1F3F4] text-[#3C4043]">{(f.name.split(".").pop() || "").slice(0, 4)}</span>
          <div className="min-w-0 flex-1">
            <p className="text-sm truncate">{f.name}</p>
            <p className="text-[10px] font-mono text-[#80868B]"><span className={SRC[f.source]}>{f.source}</span> · {fmtSize(f.size)} · {fmtTime(f.created_at)}</p>
          </div>
          <button onClick={() => saveBlob(api, `/files/${f.id}/download`, f.name).catch((e) => toast.error(errMsg(e)))} data-testid={`file-download-button-${f.id}`} title="Save to my computer"><Download className="h-4 w-4 text-[#5F6368] hover:text-[#1A73E8]" /></button>
          <button onClick={() => del(f)} data-testid={`file-delete-button-${f.id}`}><Trash2 className="h-4 w-4 text-[#80868B] hover:text-[#D93025]" /></button>
        </div>
      ))}
    </div>
  );
}
