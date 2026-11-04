import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useApi, errMsg, fmtSize } from "@/lib/api";

export default function FileChooserDialog({ open, onDone, laptop }) {
  const api = useApi();
  const [files, setFiles] = useState(null);
  const [picked, setPicked] = useState([]);
  const load = () => api.get("/target/files").then((r) => setFiles(r.data)).catch(() => setFiles([]));
  useEffect(() => { if (open) { load(); setPicked([]); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const fromComputer = async (e) => {
    for (const f of e.target.files) {
      const fd = new FormData(); fd.append("file", f);
      try { const r = await api.post("/files", fd); setPicked((p) => [...p, r.data.name]); } catch (err) { toast.error(errMsg(err)); }
    }
    load();
  };
  const submit = async (cancel) => {
    try { await api.post("/browser/filechooser", { file_names: picked, cancel }); onDone(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const toggle = (n) => setPicked((p) => (p.includes(n) ? p.filter((x) => x !== n) : [...p, n]));

  return (
    <Dialog open={open} onOpenChange={(o) => !o && submit(true)}>
      <DialogContent className="bg-[#12141C] border-[#262B3D]" data-testid="file-chooser-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">The website wants a file</DialogTitle>
          <DialogDescription>{laptop ? "Pick files from the folders you allowed on your laptop." : "Pick files from Shadow's Files area, or add one from your computer."}</DialogDescription>
        </DialogHeader>
        <div className="max-h-64 overflow-y-auto thin-scroll space-y-1">
          {files === null && <p className="text-sm text-slate-500 animate-pulse">Loading files…</p>}
          {files?.length === 0 && <p className="text-sm text-slate-500">{laptop ? "No files in your allowed folders." : "No files yet."}</p>}
          {(files || []).map((f) => (
            <label key={f.name} className="flex items-center gap-3 px-2 py-2 rounded hover:bg-white/5 cursor-pointer" data-testid={`file-chooser-item-${f.name}`}>
              <Checkbox checked={picked.includes(f.name)} onCheckedChange={() => toggle(f.name)} />
              <span className="text-sm flex-1 truncate">{f.name}</span>
              <span className="text-xs font-mono text-slate-500">{fmtSize(f.size)}</span>
            </label>
          ))}
        </div>
        {!laptop && (
          <label className="text-sm text-[#00F0FF] cursor-pointer hover:underline">
            + Add from my computer<input type="file" multiple className="hidden" onChange={fromComputer} data-testid="file-chooser-computer-input" />
          </label>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => submit(true)} data-testid="file-chooser-cancel">Cancel</Button>
          <Button disabled={!picked.length} onClick={() => submit(false)} data-testid="file-chooser-upload">Upload {picked.length || ""}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
