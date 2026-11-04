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
  return src ? <img src={src} alt={`Step ${idx}`} className="mt-2 rounded-md border border-[#262B3D] w-full" data-testid={`step-shot-${idx}`} /> : null;
}

const PLAN_ICON = { done: CheckCircle2, active: CircleDot, skipped: MinusCircle, todo: Circle };

function Step({ s, runId }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`border-l pl-3 py-1.5 fade-up ${s.simulated ? "border-[#FFB000]/50" : "border-[#262B3D]"}`} data-testid={`run-step-${s.idx}`}>
      <button onClick={() => setOpen(!open)} className="w-full text-left flex items-start gap-1.5">
        <ChevronRight className={`h-3.5 w-3.5 mt-0.5 text-slate-500 transition-transform ${open ? "rotate-90" : ""}`} />
        <div className="min-w-0">
          <p className="text-xs font-mono"><span className="text-slate-500">#{s.idx}</span> <span className={s.simulated ? "text-[#FFB000]" : s.ok ? "text-[#00F0FF]" : "text-[#FF3B30]"}>{s.simulated ? `would ${s.action}` : s.action}</span></p>
          <p className="text-xs text-slate-300 leading-snug">{s.simulated ? s.result.replace("PREVIEW — not done. Would ", "Would ") : s.reason}</p>
        </div>
      </button>
      {open && (
        <div className="ml-5">
          <pre className="mt-1 text-[10px] text-slate-500 whitespace-pre-wrap break-all font-mono">{JSON.stringify(s.args)}</pre>
          <p className="text-[11px] text-slate-400 mt-1 break-words">→ {s.result.slice(0, 400)}</p>
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
      {run.status === "running" && <button data-testid="run-pause-button" onClick={() => onAction("pause")} className={`${b} border-[#FFB000]/40 text-[#FFB000] hover:bg-[#FFB000]/10`}><Hand className="h-3.5 w-3.5" />Pause & take over</button>}
      {["paused", "failed", "stopped"].includes(run.status) && <button data-testid="run-resume-button" onClick={() => onAction("resume")} className={`${b} border-[#00F0FF]/40 text-[#00F0FF] hover:bg-[#00F0FF]/10`}><Play className="h-3.5 w-3.5" />Resume</button>}
      {["running", "paused", "awaiting_approval", "waiting_input"].includes(run.status) && <button data-testid="run-stop-button" onClick={() => onAction("stop")} className={`${b} border-[#262B3D] text-slate-300 hover:bg-white/5`}><Square className="h-3.5 w-3.5" />Stop</button>}
    </div>
  );
}

function PreviewBar({ run, onRunReal, onView }) {
  if (run.mode !== "preview") return null;
  const done = run.status === "completed";
  return (
    <div className="rounded-lg border border-[#FFB000]/40 bg-[#FFB000]/10 p-3 space-y-2" data-testid="preview-banner">
      <p className="text-xs text-[#FFB000] flex items-center gap-1.5"><Eye className="h-3.5 w-3.5" />Preview — Shadow only looks and plans. Nothing is clicked or typed.</p>
      <div className="flex gap-2 flex-wrap">
        {(run.steps || []).length > 0 && <button onClick={onView} data-testid="preview-view-steps-button" className="text-xs px-3 py-1.5 rounded-lg border border-[#FFB000]/40 text-[#FFB000] hover:bg-[#FFB000]/10">Step-by-step</button>}
        {done && run.skill_id && <button onClick={() => onRunReal(run)} data-testid="preview-run-real-button" className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-[#00F0FF] text-black font-semibold"><PlayCircle className="h-3.5 w-3.5" />Run it for real</button>}
      </div>
    </div>
  );
}

export default function ActivityPanel({ run, onAction, onRunReal }) {
  const [viewer, setViewer] = useState(false);
  return (
    <aside className="w-[340px] shrink-0 border-l border-[#262B3D] bg-[#12141C] flex flex-col relative z-10" data-testid="activity-panel">
      <div className="px-5 pt-5 pb-3 border-b border-[#262B3D]">
        <p className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Live activity</p>
        {!run ? <p className="text-sm text-slate-400 mt-2" data-testid="activity-empty">No task yet. Type a command, run a skill, or press Watch me.</p> : (
          <div className="mt-2 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-display text-base font-semibold leading-snug min-w-0 break-words line-clamp-3" title={run.goal} data-testid="run-goal">{run.goal}</h3>
              <StatusBadge status={run.status} />
            </div>
            <p className="text-[11px] font-mono text-slate-500">{run.step_count} steps{run.skill_name ? ` · skill: ${run.skill_name}` : ""}{run.trigger === "schedule" ? " · scheduled" : ""} · {run.target === "laptop" ? "laptop" : "cloud"}</p>
            <PreviewBar run={run} onRunReal={onRunReal} onView={() => setViewer(true)} />
            <Controls run={run} onAction={onAction} />
            {run.status === "paused" && <p className="text-xs text-[#FFB000]" data-testid="run-paused-hint">You have control. Anything you do now is learned as a correction — press Resume when done.</p>}
            {run.pending?.question && run.status === "waiting_input" && <p className="text-sm text-[#00F0FF] bg-[#00F0FF]/10 rounded-lg p-3" data-testid="run-question">{run.pending.question}</p>}
            {run.summary && <p className="text-xs text-slate-300 bg-white/5 rounded-lg p-3" data-testid="run-summary">{run.summary}</p>}
            {run.learned && <p className="text-xs text-[#00E676] flex gap-1.5" data-testid="run-learned"><Lightbulb className="h-3.5 w-3.5 shrink-0" />{run.learned}</p>}
          </div>
        )}
      </div>
      {run && (
        <div className="flex-1 min-h-0 overflow-y-auto thin-scroll px-5 py-4 space-y-5">
          <ResultsTable run={run} />
          {run.plan?.length > 0 && (
            <div data-testid="run-plan">
              <p className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">Checklist · {run.plan.filter((p) => p.status === "done").length}/{run.plan.length}</p>
              <ul className="space-y-1.5">
                {run.plan.map((p, i) => { const Icon = PLAN_ICON[p.status] || Circle; return (
                  <li key={i} className={`flex gap-2 text-xs ${p.status === "done" ? "text-slate-500 line-through" : p.status === "active" ? "text-[#00F0FF]" : "text-slate-300"}`} data-testid={`run-plan-item-${i}`}>
                    <Icon className="h-3.5 w-3.5 shrink-0 mt-0.5" />{p.title}
                  </li>); })}
              </ul>
            </div>
          )}
          <div data-testid="run-steps">
            <p className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">Steps (newest first)</p>
            {(run.steps || []).length === 0 && <p className="text-xs text-slate-500 flex items-center gap-2"><Pause className="h-3 w-3" />Thinking about the first step…</p>}
            {(run.steps || []).map((s) => <Step key={s.id} s={s} runId={run.id} />)}
          </div>
          {run.status === "failed" && <p className="text-xs text-[#FF3B30] flex gap-1.5"><XCircle className="h-3.5 w-3.5" />Press Resume to continue from the last saved step.</p>}
        </div>
      )}
      <PreviewViewer run={run} open={viewer} onOpenChange={setViewer} />
    </aside>
  );
}
