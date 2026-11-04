import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Hand, Lock, Plus, RotateCw, X } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg } from "@/lib/api";
import DialogBar from "./DialogBar";
import FileChooserDialog from "./FileChooserDialog";
import { TargetToggle } from "./LaptopPanel";

const SPECIAL = new Set(["Enter", "Backspace", "Tab", "Escape", "Delete", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"]);
const MODE = {
  recording: { t: "Learning your routine", c: "text-[#FF3B30] border-[#FF3B30]/50 bg-[#FF3B30]/15" },
  agent: { t: "Autonomous", c: "text-[#00F0FF] border-[#00F0FF]/40 bg-[#00F0FF]/10" },
  manual: { t: "Manual", c: "text-slate-300 border-[#262B3D] bg-white/5" },
};

function useFrame(api) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let alive = true, prev = null, timer;
    const tick = async () => {
      if (!document.hidden) {
        try {
          const r = await api.get("/browser/frame", { responseType: "blob" });
          const u = URL.createObjectURL(r.data);
          if (!alive) return URL.revokeObjectURL(u);
          setSrc(u); if (prev) URL.revokeObjectURL(prev); prev = u;
        } catch {}
      }
      if (alive) timer = setTimeout(tick, 450);
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [api]);
  return src;
}

function TabStrip({ tabs, onTab }) {
  return (
    <div className="flex items-end gap-1 px-2 pt-2 overflow-x-auto thin-scroll" data-testid="browser-tab-bar">
      {tabs.map((t) => (
        <div key={t.index} data-testid={`browser-tab-${t.index}`} onClick={() => onTab("switch", t.index)}
          className={`group flex items-center gap-2 max-w-[200px] min-w-[120px] px-3 py-1.5 rounded-t-lg text-xs cursor-pointer transition-colors ${t.active ? "bg-[#181B26] text-slate-100" : "text-slate-500 hover:bg-white/5"}`}>
          <span className="truncate flex-1">{t.title || "New tab"}</span>
          <button data-testid={`browser-tab-close-${t.index}`} onClick={(e) => { e.stopPropagation(); onTab("close", t.index); }} className="opacity-50 hover:opacity-100"><X className="h-3 w-3" /></button>
        </div>
      ))}
      <button data-testid="browser-new-tab-button" onClick={() => onTab("new")} className="mb-1 ml-1 h-6 w-6 rounded-md flex items-center justify-center text-slate-400 hover:bg-white/10"><Plus className="h-3.5 w-3.5" /></button>
    </div>
  );
}

export default function BrowserView({ mode, state, onState, onTakeOver, target, onTarget }) {
  const api = useApi();
  const src = useFrame(api);
  const imgRef = useRef(null);
  const queue = useRef(Promise.resolve());
  const [url, setUrl] = useState("");
  const [editing, setEditing] = useState(false);
  const active = state?.tabs?.find((t) => t.active);

  const loadState = useCallback(async () => {
    try { const r = await api.get("/browser/state"); onState(r.data); } catch {}
  }, [api, onState]);
  useEffect(() => { loadState(); const t = setInterval(loadState, 1200); return () => clearInterval(t); }, [loadState]);
  useEffect(() => { if (!editing && active) setUrl(active.url); }, [active, editing]);

  const send = (body) => {
    queue.current = queue.current.then(() => api.post("/browser/input", body)).catch((e) => toast.error(errMsg(e)));
  };
  const point = (e) => {
    const r = imgRef.current.getBoundingClientRect();
    const vp = state?.viewport || { width: 1280, height: 800 };
    return { x: ((e.clientX - r.left) * vp.width) / r.width, y: ((e.clientY - r.top) * vp.height) / r.height };
  };
  const onClick = (e) => { if (mode === "agent") onTakeOver(); e.currentTarget.parentElement.focus(); send({ kind: "click", ...point(e) }); };
  const onKey = (e) => {
    if (e.target.tagName === "INPUT") return;
    const mod = e.ctrlKey || e.metaKey;
    if (e.key.length === 1 && !mod) send({ kind: "type", text: e.key });
    else if (SPECIAL.has(e.key) || (mod && e.key.length === 1)) send({ kind: "key", key: mod ? `Control+${e.key}` : e.key });
    else return;
    e.preventDefault();
  };
  const lastWheel = useRef(0);
  const onWheel = (e) => { const n = Date.now(); if (n - lastWheel.current < 120) return; lastWheel.current = n; send({ kind: "scroll", dy: e.deltaY * 2, ...point(e) }); };
  const onPaste = (e) => { const t = e.clipboardData.getData("text"); if (t) { send({ kind: "type", text: t }); e.preventDefault(); } };

  const call = async (path, body) => { try { await api.post(path, body); loadState(); } catch (e) { toast.error(errMsg(e)); } };
  const m = MODE[mode];

  return (
    <section className="flex-1 min-h-0 flex flex-col rounded-xl border border-[#262B3D] bg-[#0F111A] overflow-hidden shadow-2xl relative" data-testid="live-browser-viewport">
      <TabStrip tabs={state?.tabs || []} onTab={(action, index) => call("/browser/tabs", { action, index })} />
      <div className="flex items-center gap-2 px-3 py-2 bg-[#181B26] border-b border-[#262B3D]">
        <button data-testid="browser-back-button" onClick={() => call("/browser/nav", { action: "back" })} className="p-1.5 rounded hover:bg-white/10 text-slate-400"><ArrowLeft className="h-4 w-4" /></button>
        <button data-testid="browser-forward-button" onClick={() => call("/browser/nav", { action: "forward" })} className="p-1.5 rounded hover:bg-white/10 text-slate-400"><ArrowRight className="h-4 w-4" /></button>
        <button data-testid="browser-reload-button" onClick={() => call("/browser/nav", { action: "reload" })} className="p-1.5 rounded hover:bg-white/10 text-slate-400"><RotateCw className="h-4 w-4" /></button>
        <form className="flex-1 flex items-center gap-2 bg-[#0F111A] border border-[#262B3D] rounded-lg px-3 py-1.5 focus-within:border-[#00F0FF]/50 transition-colors"
          onSubmit={(e) => { e.preventDefault(); setEditing(false); call("/browser/navigate", { url }); }}>
          <Lock className="h-3.5 w-3.5 text-slate-500" />
          <input data-testid="browser-url-input" value={url} onFocus={() => setEditing(true)} onBlur={() => setEditing(false)} onChange={(e) => setUrl(e.target.value)}
            className="flex-1 bg-transparent outline-none text-sm font-mono text-slate-200" placeholder="Search or enter address" />
        </form>
        <TargetToggle target={target} onChange={onTarget} />
        <span data-testid="browser-mode-badge" className={`text-[11px] font-mono uppercase tracking-wider px-2.5 py-1 rounded-full border ${m.c} ${mode === "recording" ? "rec-pulse" : ""}`}>{m.t}</span>
        {mode === "agent" && (
          <button data-testid="take-over-button" onClick={onTakeOver} className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-[#FFB000]/40 text-[#FFB000] hover:bg-[#FFB000]/10 transition-colors"><Hand className="h-3.5 w-3.5" />Take over</button>
        )}
      </div>
      <DialogBar dialog={state?.dialog} onDone={loadState} />
      <div tabIndex={0} onKeyDown={onKey} onPaste={onPaste} data-testid="browser-screen"
        className={`flex-1 min-h-0 flex items-center justify-center bg-black/60 outline-none p-2 ${mode === "recording" ? "ring-2 ring-inset ring-[#FF3B30]/60" : "focus:ring-1 focus:ring-inset focus:ring-[#00F0FF]/30"}`}>
        {src ? (
          <img ref={imgRef} src={src} alt="Live browser" draggable={false} onClick={onClick} onWheel={onWheel} data-testid="browser-frame-image"
            className="max-w-full max-h-full select-none cursor-crosshair rounded-md shadow-xl" />
        ) : (
          <p className="text-sm font-mono text-slate-500 animate-pulse" data-testid="browser-loading">{target?.target === "laptop" && !target?.helper_online ? "Your laptop helper is offline — open Shadow Helper or switch to Cloud" : "Starting Shadow's Chrome…"}</p>
        )}
      </div>
      <FileChooserDialog open={!!state?.file_chooser} onDone={loadState} />
    </section>
  );
}
