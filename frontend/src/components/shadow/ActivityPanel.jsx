import { useEffect, useState } from "react";
import { CheckCircle2, ChevronRight, Circle, CircleDot, Eye, Hand, Lightbulb, MinusCircle, Pause, Play, PlayCircle, Square, XCircle } from "lucide-react";
import { useApi } from "@/lib/api";
import StatusBadge from "./StatusBadge";
import ResultsTable from "./ResultsTable";
import PreviewViewer from "./PreviewViewer";

function Shot({ runId, idx }) {
  const api = useApi();
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let u;
    api.get(`/runs/${runId}/shot/${idx}`, { responseType: "blob" }).then((r) => { u = URL.createObjectURL(r.data); setSrc(u); }).catch(() => {});
    return () => u && URL.revokeObjectURL(u);
  }, [api, runId, idx]);
  return src ? <img src={src} alt={`Step ${idx}`} className="mt-2 rounded-md border border-[#DADCE0] w-full" data-testid={`step-shot-${idx}`} /> : null;
}

const PLAN_ICON = { done: CheckCircle2, active: CircleDot, skipped: MinusCircle, todo: Circle };

function Step({ s, runId }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`border-l pl-3 py-1.5 fade-up ${s.simulated ? "border-[#B06000]/50" : "border-[#DADCE0]"}`} data-testid={`run-step-${s.idx}`}>
      <button onClick={() => setOpen(!open)} className="w-full text-left flex items-start gap-1.5">
        <ChevronRight className={`h-3.5 w-3.5 mt-0.5 text-[#80868B] transition-transform ${open ? "rotate-90" : ""}`} />
        <div className="min-w-0">
          <p className="text-xs font-mono"><span className="text-[#80868B]">#{s.idx}</span> <span className={s.simulated ? "text-[#B06000]" : s.ok ? "text-[#1A73E8]" : "text-[#D93025]"}>{s.simulated ? `would ${s.action}` : s.action}</span></p>
          <p className="text-xs text-[#3C4043] leading-snug">{s.simulated ? s.result.replace("PREVIEW — not done. Would ", "Would ") : s.reason}</p>
        </div>
      </button>
      {open && (
        <div className="ml-5">
          <pre className="mt-1 text-[10px] text-[#80868B] whitespace-pre-wrap break-all font-mono">{JSON.stringify(s.args)}</pre>
          <p className="text-[11px] text-[#5F6368] mt-1 break-words">→ {s.result.slice(0, 400)}</p>
          {s.has_shot && <Shot runId={runId} idx={s.idx} />}
        </div>
      )}
    </div>
  );
}

function Controls({ run, onAction }) {
  const b = "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors";
  return (
    <div className="flex gap-2 flex-wrap">
      {run.status === "running" && <button data-testid="run-pause-button" onClick={() => onAction("pause")} className={`${b} border-[#B06000]/40 text-[#B06000] hover:bg-[#B06000]/10`}><Hand className="h-3.5 w-3.5" />Pause & take over</button>}
      {["paused", "failed", "stopped"].includes(run.status) && <button data-testid="run-resume-button" onClick={() => onAction("resume")} className={`${b} border-[#1A73E8]/40 text-[#1A73E8] hover:bg-[#1A73E8]/10`}><Play className="h-3.5 w-3.5" />Resume</button>}
      {["running", "paused", "awaiting_approval", "waiting_input"].includes(run.status) && <button data-testid="run-stop-button" onClick={() => onAction("stop")} className={`${b} border-[#DADCE0] text-[#3C4043] hover:bg-[#F1F3F4]`}><Square className="h-3.5 w-3.5" />Stop</button>}
    </div>
  );
}

function PreviewBar({ run, onRunReal, onView }) {
  if (run.mode !== "preview") return null;
  const done = run.status === "completed";
  return (
    <div className="rounded-lg border border-[#B06000]/40 bg-[#B06000]/10 p-3 space-y-2" data-testid="preview-banner">
      <p className="text-xs text-[#B06000] flex items-center gap-1.5"><Eye className="h-3.5 w-3.5" />Preview — Shadow only looks and plans. Nothing is clicked or typed.</p>
      <div className="flex gap-2 flex-wrap">
        {(run.steps || []).length > 0 && <button onClick={onView} data-testid="preview-view-steps-button" className="text-xs px-3 py-1.5 rounded-lg border border-[#B06000]/40 text-[#B06000] hover:bg-[#B06000]/10">Step-by-step</button>}
        {done && run.skill_id && <button onClick={() => onRunReal(run)} data-testid="preview-run-real-button" className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-[#1A73E8] text-white font-semibold"><PlayCircle className="h-3.5 w-3.5" />Run it for real</button>}
      </div>
    </div>
  );
}

export default function ActivityPanel({ run, onAction, onRunReal, onCollapse }) {
  const [viewer, setViewer] = useState(false);
  return (
    <aside className="w-full h-full border-l border-[#DADCE0] bg-white flex flex-col relative z-10" data-testid="activity-panel">
      <div className="px-5 pt-4 pb-3 border-b border-[#DADCE0]">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[#5F6368]">Live activity</p>
          {onCollapse && <button onClick={onCollapse} title="Hide activity" data-testid="activity-collapse-button" className="h-7 w-7 -mr-2 rounded-full flex items-center justify-center text-[#5F6368] hover:bg-[#F1F3F4]"><ChevronRight className="h-4 w-4" /></button>}
        </div>
        {!run ? <p className="text-sm text-[#5F6368] mt-2" data-testid="activity-empty">No task yet. Type a command, run a skill, or press Watch me.</p> : (
          <div className="mt-2 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-display text-base font-semibold leading-snug min-w-0 break-words line-clamp-3" title={run.goal} data-testid="run-goal">{run.goal}</h3>
              <StatusBadge status={run.status} />
            </div>
            <p className="text-[11px] font-mono text-[#80868B]">{run.step_count} steps{run.skill_name ? ` · skill: ${run.skill_name}` : ""}{run.trigger === "schedule" ? " · scheduled" : ""} · {run.target === "laptop" ? "laptop" : "cloud"}</p>
            <PreviewBar run={run} onRunReal={onRunReal} onView={() => setViewer(true)} />
            <Controls run={run} onAction={onAction} />
            {run.status === "paused" && <p className="text-xs text-[#B06000]" data-testid="run-paused-hint">You have control. Anything you do now is learned as a correction — press Resume when done.</p>}
            {run.pending?.question && run.status === "waiting_input" && <p className="text-sm text-[#1A73E8] bg-[#1A73E8]/10 rounded-lg p-3" data-testid="run-question">{run.pending.question}</p>}
            {run.summary && <p className="text-xs text-[#3C4043] bg-[#F1F3F4] rounded-lg p-3" data-testid="run-summary">{run.summary}</p>}
            {run.learned && <p className="text-xs text-[#1E8E3E] flex gap-1.5" data-testid="run-learned"><Lightbulb className="h-3.5 w-3.5 shrink-0" />{run.learned}</p>}
          </div>
        )}
      </div>
      {run && (
        <div className="flex-1 min-h-0 overflow-y-auto thin-scroll px-5 py-4 space-y-5">
          <ResultsTable run={run} />
          {run.plan?.length > 0 && (
            <div data-testid="run-plan">
              <p className="text-[10px] font-mono uppercase tracking-widest text-[#80868B] mb-2">Checklist · {run.plan.filter((p) => p.status === "done").length}/{run.plan.length}</p>
              <ul className="space-y-1.5">
                {run.plan.map((p, i) => { const Icon = PLAN_ICON[p.status] || Circle; return (
                  <li key={i} className={`flex gap-2 text-xs ${p.status === "done" ? "text-[#80868B] line-through" : p.status === "active" ? "text-[#1A73E8]" : "text-[#3C4043]"}`} data-testid={`run-plan-item-${i}`}>
                    <Icon className="h-3.5 w-3.5 shrink-0 mt-0.5" />{p.title}
                  </li>); })}
              </ul>
            </div>
          )}
          <div data-testid="run-steps">
            <p className="text-[10px] font-mono uppercase tracking-widest text-[#80868B] mb-2">Steps (newest first)</p>
            {(run.steps || []).length === 0 && <p className="text-xs text-[#80868B] flex items-center gap-2"><Pause className="h-3 w-3" />Thinking about the first step…</p>}
            {(run.steps || []).map((s) => <Step key={s.id} s={s} runId={run.id} />)}
          </div>
          {run.status === "failed" && <p className="text-xs text-[#D93025] flex gap-1.5"><XCircle className="h-3.5 w-3.5" />Press Resume to continue from the last saved step.</p>}
        </div>
      )}
      <PreviewViewer run={run} open={viewer} onOpenChange={setViewer} />
    </aside>
  );
}
