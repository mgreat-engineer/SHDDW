import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Eye } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApi } from "@/lib/api";

function BigShot({ runId, idx }) {
  const api = useApi();
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let u;
    setSrc(null);
    api.get(`/runs/${runId}/shot/${idx}`, { responseType: "blob" }).then((r) => { u = URL.createObjectURL(r.data); setSrc(u); }).catch(() => {});
    return () => u && URL.revokeObjectURL(u);
  }, [api, runId, idx]);
  return (
    <div className="aspect-[16/10] w-full rounded-lg border border-[#262B3D] bg-black/50 flex items-center justify-center overflow-hidden">
      {src ? <img src={src} alt={`Step ${idx}`} className="w-full h-full object-contain" data-testid="preview-viewer-image" /> : <p className="text-xs font-mono text-slate-500 animate-pulse">Loading screenshot…</p>}
    </div>
  );
}

export default function PreviewViewer({ run, open, onOpenChange }) {
  const steps = [...(run?.steps || [])].sort((a, b) => a.idx - b.idx);
  const [i, setI] = useState(0);
  useEffect(() => { if (open) setI(0); }, [open]);
  if (!run || !steps.length) return null;
  const s = steps[Math.min(i, steps.length - 1)];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#12141C] border-[#262B3D] max-w-4xl" data-testid="preview-viewer">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Eye className="h-4 w-4 text-[#FFB000]" />Step-by-step: {run.skill_name || run.goal}</DialogTitle></DialogHeader>
        <BigShot runId={run.id} idx={s.idx} />
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-xs font-mono text-slate-500">Step {i + 1} of {steps.length} · {s.action}</p>
            <p className={`text-sm mt-1 ${s.simulated ? "text-[#FFB000]" : "text-slate-100"}`} data-testid="preview-viewer-result">{s.simulated ? s.result.replace("PREVIEW — not done. ", "") : s.result.slice(0, 200)}</p>
            <p className="text-xs text-slate-400 mt-1">{s.reason}</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <button disabled={i === 0} onClick={() => setI(i - 1)} data-testid="preview-viewer-prev" className="h-9 w-9 rounded-lg border border-[#262B3D] flex items-center justify-center disabled:opacity-30 hover:bg-white/5"><ChevronLeft className="h-4 w-4" /></button>
            <button disabled={i >= steps.length - 1} onClick={() => setI(i + 1)} data-testid="preview-viewer-next" className="h-9 w-9 rounded-lg border border-[#262B3D] flex items-center justify-center disabled:opacity-30 hover:bg-white/5"><ChevronRight className="h-4 w-4" /></button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
