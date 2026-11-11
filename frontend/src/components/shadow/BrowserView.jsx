import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Globe, Hand, Lock, Maximize2, Minimize2, PanelLeft, PanelRight, Plus, RotateCw, X } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg } from "@/lib/api";
import DialogBar from "./DialogBar";
import FileChooserDialog from "./FileChooserDialog";
import { TargetToggle } from "./LaptopPanel";
import { useLiveView } from "./useLiveView";

const SPECIAL = new Set(["Enter", "Backspace", "Tab", "Escape", "Delete", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"]);
const MODE = {
  recording: { t: "Learning your routine", c: "text-[#D93025] border-[#D93025]/40 bg-[#FCE8E6]" },
  agent: { t: "Shadow is working", c: "text-[#1A73E8] border-[#1A73E8]/40 bg-[#E8F0FE]" },
};
const host = (u) => { try { return new URL(u).hostname; } catch { return ""; } };

function Favicon({ url }) {
  const h = host(url);
  const [bad, setBad] = useState(false);
  if (!h || bad) return <Globe className="h-3.5 w-3.5 shrink-0 text-[#5F6368]" />;
  return <img src={`https://www.google.com/s2/favicons?domain=${h}&sz=32`} alt="" onError={() => setBad(true)} className="h-4 w-4 shrink-0" />;
}

function TabStrip({ tabs, onTab }) {
  return (
    <div className="flex items-end gap-0.5 px-2 pt-1.5 h-10 bg-[#DEE1E6] overflow-x-auto thin-scroll select-none" data-testid="browser-tab-bar">
      {tabs.map((t) => (
        <div key={t.index} data-testid={`browser-tab-${t.index}`} onClick={() => onTab("switch", t.index)} title={t.title}
          className={`group flex items-center gap-2 w-[220px] min-w-[110px] h-[34px] px-3 rounded-t-lg text-xs cursor-default transition-colors ${t.active ? "bg-white text-[#202124] shadow-[0_-1px_2px_rgba(60,64,67,0.12)]" : "text-[#5F6368] hover:bg-[#E8EAED]"}`}>
          <Favicon url={t.url} />
          <span className="truncate flex-1">{t.title || "New tab"}</span>
          <button data-testid={`browser-tab-close-${t.index}`} onClick={(e) => { e.stopPropagation(); onTab("close", t.index); }} className="p-0.5 rounded-full text-[#5F6368] hover:bg-[#DADCE0] hover:text-[#202124]"><X className="h-3.5 w-3.5" /></button>
        </div>
      ))}
      <button data-testid="browser-new-tab-button" title="New tab" onClick={() => onTab("new")} className="mb-1.5 ml-1 h-7 w-7 rounded-full flex items-center justify-center text-[#5F6368] hover:bg-[#E8EAED] hover:text-[#202124]"><Plus className="h-4 w-4" /></button>
    </div>
  );
}

function ToolBtn({ testId, title, onClick, active, children }) {
  return (
    <button data-testid={testId} title={title} onClick={onClick}
      className={`h-8 w-8 shrink-0 rounded-full flex items-center justify-center transition-colors ${active ? "text-[#1A73E8] bg-[#E8F0FE]" : "text-[#5F6368] hover:bg-[#F1F3F4] hover:text-[#202124]"}`}>{children}</button>
  );
}

export default function BrowserView({ mode, state, onState, onTakeOver, target, onTarget, layout }) {
  const api = useApi();
  const { src, live, sendInput, resize } = useLiveView(api, (d) => toast.error(d));
  const imgRef = useRef(null);
  const screenRef = useRef(null);
  useEffect(() => {
    const el = screenRef.current;
    if (!el) return;
    let t;
    const ro = new ResizeObserver(([e]) => {
      clearTimeout(t);
      t = setTimeout(() => resize(Math.round(e.contentRect.width), Math.round(e.contentRect.height)), 250);
    });
    ro.observe(el);
    return () => { ro.disconnect(); clearTimeout(t); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const queue = useRef(Promise.resolve());
  const [url, setUrl] = useState("");
  const [editing, setEditing] = useState(false);
  const active = state?.tabs?.find((t) => t.active);

  const loadState = useCallback(async () => {
    try { const r = await api.get("/browser/state"); onState(r.data); } catch {}
  }, [api, onState]);
  useEffect(() => { loadState(); const t = setInterval(loadState, 1000); return () => clearInterval(t); }, [loadState]);
  useEffect(() => { if (!editing && active) setUrl(active.url); }, [active, editing]);

  const send = (body) => {
    if (sendInput(body)) return;
    if (body.kind === "move") return;
    queue.current = queue.current.then(() => api.post("/browser/input", body)).catch((e) => toast.error(errMsg(e)));
  };
  const point = (e) => {
    const r = imgRef.current.getBoundingClientRect();
    const vp = state?.viewport || { width: 1280, height: 800 };
    return { x: Math.round(((e.clientX - r.left) * vp.width) / r.width), y: Math.round(((e.clientY - r.top) * vp.height) / r.height) };
  };
  const onClick = (e) => { if (mode === "agent") onTakeOver(); e.currentTarget.parentElement.focus(); send({ kind: "click", ...point(e) }); };
  const onDouble = (e) => send({ kind: "dblclick", ...point(e) });
  const onKey = (e) => {
    if (e.target.tagName === "INPUT") return;
    const mod = e.ctrlKey || e.metaKey;
    if (e.key.length === 1 && !mod) send({ kind: "type", text: e.key });
    else if (SPECIAL.has(e.key) || (mod && e.key.length === 1)) send({ kind: "key", key: mod ? `Control+${e.key}` : e.key });
    else return;
    e.preventDefault();
  };
  const wheel = useRef({ dy: 0, t: null });
  const onWheel = (e) => {
    const p = point(e);
    wheel.current.dy += e.deltaY;
    if (wheel.current.t) return;
    wheel.current.t = setTimeout(() => { send({ kind: "scroll", dy: Math.round(wheel.current.dy), ...p }); wheel.current = { dy: 0, t: null }; }, live ? 40 : 120);
  };
  const lastMove = useRef(0);
  const onMove = (e) => {
    if (!live || mode === "agent") return;
    const n = Date.now(); if (n - lastMove.current < 70) return; lastMove.current = n;
    send({ kind: "move", ...point(e) });
  };
  const onPaste = (e) => { const t = e.clipboardData.getData("text"); if (t) { send({ kind: "type", text: t }); e.preventDefault(); } };

  const call = async (path, body) => { try { await api.post(path, body); loadState(); } catch (e) { toast.error(errMsg(e)); } };
  const m = MODE[mode];
  const secure = (active?.url || "").startsWith("https://");

  return (
    <section className="flex-1 min-h-0 flex flex-col rounded-xl border border-[#DADCE0] bg-white overflow-hidden shadow-sm relative" data-testid="live-browser-viewport">
      <TabStrip tabs={state?.tabs || []} onTab={(action, index) => call("/browser/tabs", { action, index })} />
      <div className="flex items-center gap-1 px-2 h-11 bg-white border-b border-[#DADCE0]">
        <ToolBtn testId="browser-back-button" title="Back" onClick={() => call("/browser/nav", { action: "back" })}><ArrowLeft className="h-4 w-4" /></ToolBtn>
        <ToolBtn testId="browser-forward-button" title="Forward" onClick={() => call("/browser/nav", { action: "forward" })}><ArrowRight className="h-4 w-4" /></ToolBtn>
        <ToolBtn testId="browser-reload-button" title="Reload" onClick={() => call("/browser/nav", { action: "reload" })}><RotateCw className="h-4 w-4" /></ToolBtn>
        <form className="flex-1 min-w-0 flex items-center gap-2 h-8 mx-1 bg-[#F1F3F4] hover:bg-[#E8EAED] focus-within:bg-white focus-within:shadow-[0_1px_3px_rgba(60,64,67,0.3)] focus-within:ring-2 focus-within:ring-[#1A73E8] rounded-full px-4 transition-colors"
          onSubmit={(e) => { e.preventDefault(); setEditing(false); call("/browser/navigate", { url }); }}>
          {secure ? <Lock className="h-3.5 w-3.5 shrink-0 text-[#5F6368]" data-testid="browser-secure-icon" /> : <Globe className="h-3.5 w-3.5 shrink-0 text-[#5F6368]" />}
          <input data-testid="browser-url-input" value={url} onFocus={(e) => { setEditing(true); e.target.select(); }} onBlur={() => setEditing(false)} onChange={(e) => setUrl(e.target.value)}
            className="flex-1 min-w-0 bg-transparent outline-none text-sm text-[#202124] placeholder-[#5F6368]" placeholder="Search Google or type a URL" />
        </form>
        {m && <span data-testid="browser-mode-badge" className={`shrink-0 text-[11px] font-medium px-2.5 py-1 rounded-full border ${m.c} ${mode === "recording" ? "rec-pulse" : ""}`}>{m.t}</span>}
        {mode === "agent" && (
          <button data-testid="take-over-button" onClick={onTakeOver} className="shrink-0 flex items-center gap-1.5 text-xs px-3 h-8 rounded-full border border-[#DADCE0] text-[#202124] hover:bg-[#F1F3F4]"><Hand className="h-3.5 w-3.5" />Take over</button>
        )}
        <TargetToggle target={target} onChange={onTarget} />
        <span title={live ? "Live stream" : "Picture mode"} data-testid="browser-live-indicator" className={`shrink-0 h-2 w-2 rounded-full mx-1 ${live ? "bg-[#1E8E3E]" : "bg-[#BDC1C6]"}`} />
        {layout && <>
          {!layout.noLeft && <ToolBtn testId="toggle-left-panel" title={layout.left ? "Hide side panel" : "Show side panel"} onClick={layout.toggleLeft} active={layout.left}><PanelLeft className="h-4 w-4" /></ToolBtn>}
          <ToolBtn testId="toggle-right-panel" title={layout.right ? "Hide activity" : "Show activity"} onClick={layout.toggleRight} active={layout.right}><PanelRight className="h-4 w-4" /></ToolBtn>
          {!layout.noLeft && <ToolBtn testId="toggle-workspace-bar" title={layout.bar ? "Full screen browser" : "Exit full screen"} onClick={layout.toggleBar}>{layout.bar ? <Maximize2 className="h-4 w-4" /> : <Minimize2 className="h-4 w-4" />}</ToolBtn>}
        </>}
      </div>
      <DialogBar dialog={state?.dialog} onDone={loadState} />
      <div ref={screenRef} tabIndex={0} onKeyDown={onKey} onPaste={onPaste} data-testid="browser-screen"
        className={`flex-1 min-h-0 flex items-center justify-center bg-[#F8F9FA] outline-none cursor-default ${mode === "recording" ? "ring-2 ring-inset ring-[#D93025]/60" : ""}`}>
        {src ? (
          <img ref={imgRef} src={src} alt="Live browser" draggable={false} onClick={onClick} onDoubleClick={onDouble} onWheel={onWheel} onMouseMove={onMove} data-testid="browser-frame-image"
            className="max-w-full max-h-full select-none cursor-default" />
        ) : (
          <p className="text-sm text-[#5F6368] animate-pulse" data-testid="browser-loading">{target?.target === "laptop" && !target?.helper_online ? "Your laptop helper is offline — open Shadow Helper or switch to Cloud" : "Starting Chrome…"}</p>
        )}
      </div>
      <FileChooserDialog open={!!state?.file_chooser} onDone={loadState} laptop={target?.target === "laptop"} />
    </section>
  );
}
