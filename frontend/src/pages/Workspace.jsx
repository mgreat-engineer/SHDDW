import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useApi, errMsg } from "@/lib/api";
import SideRail from "@/components/shadow/SideRail";
import SidePanel from "@/components/shadow/SidePanel";
import BrowserView from "@/components/shadow/BrowserView";
import CommandBar from "@/components/shadow/CommandBar";
import ActivityPanel from "@/components/shadow/ActivityPanel";
import ApprovalDialog from "@/components/shadow/ApprovalDialog";
import SkillReviewDialog from "@/components/shadow/SkillReviewDialog";
import UpdateBanner from "@/components/shadow/UpdateBanner";

const ALERT = { completed: "Task finished", failed: "Task failed", awaiting_approval: "Shadow needs your OK", waiting_input: "Shadow has a question" };

function notify(title, body) {
  toast(title, { description: body });
  if (document.hidden && "Notification" in window && Notification.permission === "granted") new Notification(title, { body });
}

export default function Workspace() {
  const api = useApi();
  const [panel, setPanel] = useState("skills");
  const [bstate, setBstate] = useState(null);
  const [status, setStatus] = useState(null);
  const [runId, setRunId] = useState(null);
  const [run, setRun] = useState(null);
  const [recorded, setRecorded] = useState(null);
  const [target, setTarget] = useState(null);
  const [refresh, setRefresh] = useState(0);
  const lastStatus = useRef({});
  const lastActive = useRef(null);

  const bump = () => setRefresh((n) => n + 1);

  useEffect(() => { api.get("/status").then((r) => setStatus(r.data)).catch(() => {}); }, [api]);

  const loadTarget = useCallback(() => api.get("/target").then((r) => setTarget(r.data)).catch(() => {}), [api]);
  useEffect(() => { loadTarget(); const t = setInterval(loadTarget, 4000); return () => clearInterval(t); }, [loadTarget]);
  const changeTarget = async (t) => {
    if (!t) return loadTarget();
    try { const r = await api.put("/target", { target: t }); setTarget(r.data); toast.success(t === "laptop" ? "Shadow now works on your laptop" : "Shadow now works in the cloud"); }
    catch (e) { toast.error(errMsg(e)); }
  };

  const pollActive = useCallback(async () => {
    try {
      const r = await api.get("/runs/active");
      const id = r.data.run?.id || null;
      if (id && id !== lastActive.current) setRunId(id);
      lastActive.current = id;
    } catch {}
  }, [api]);

  const pollRun = useCallback(async () => {
    if (!runId) return;
    try {
      const r = await api.get(`/runs/${runId}`);
      setRun(r.data);
      const prev = lastStatus.current[runId];
      if (prev && prev !== r.data.status && ALERT[r.data.status]) {
        notify(ALERT[r.data.status], r.data.summary || r.data.pending?.question || r.data.goal);
        bump();
      }
      lastStatus.current[runId] = r.data.status;
    } catch {}
  }, [api, runId]);

  useEffect(() => {
    pollActive(); pollRun();
    const t = setInterval(() => { pollActive(); pollRun(); }, 1500);
    return () => clearInterval(t);
  }, [pollActive, pollRun]);

  const startRun = async (payload) => {
    try {
      if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
      const r = await api.post("/runs", payload);
      setRunId(r.data.id); setRun(null); bump();
      toast.success(r.data.status === "running" ? "Shadow is on it" : "Reply sent");
    } catch (e) { toast.error(errMsg(e)); }
  };

  const runAction = async (action, body) => {
    try { await api.post(`/runs/${run.id}/${action}`, body); pollRun(); bump(); }
    catch (e) { toast.error(errMsg(e)); }
  };

  const isRunning = run?.status === "running";
  const mode = bstate?.recording ? "recording" : isRunning ? "agent" : "manual";

  return (
    <div className="h-screen flex bg-[#08090E] text-slate-100 overflow-hidden grain" data-testid="workspace">
      <SideRail panel={panel} setPanel={setPanel} />
      <SidePanel panel={panel} refresh={refresh} onRunSkill={(s) => startRun({ skill_id: s.id, command: "" })}
        onPreviewSkill={(s) => startRun({ skill_id: s.id, command: "", mode: "preview" })}
        onSelectRun={setRunId} selectedRunId={runId} target={target} onTarget={changeTarget} />
      <main className="flex-1 min-w-0 flex flex-col p-3 gap-3 relative z-10">
        {status && !status.openai_configured && (
          <div className="rounded-lg border border-[#FFB000]/40 bg-[#FFB000]/10 text-[#FFB000] text-sm px-4 py-2" data-testid="openai-key-banner">
            OpenAI key not added yet — the browser works, but learning, commands and voice are off until the key is added.
          </div>
        )}
        <UpdateBanner target={target} />
        <BrowserView mode={mode} onState={setBstate} state={bstate} onTakeOver={() => isRunning && runAction("pause")} target={target} onTarget={changeTarget} />
        <CommandBar recording={!!bstate?.recording} recorded={bstate?.recorded || []} recordedCount={bstate?.recorded_count || 0}
          waiting={run?.status === "waiting_input"} busy={isRunning} onRun={startRun} onRecorded={setRecorded} />
      </main>
      <ActivityPanel run={run} onAction={runAction} onRunReal={(r) => startRun({ skill_id: r.skill_id, command: "" })} />
      <ApprovalDialog run={run} onDecide={(decision) => runAction("approval", { decision })} />
      <SkillReviewDialog events={recorded} onClose={() => setRecorded(null)} onSaved={() => { setRecorded(null); setPanel("skills"); bump(); }} />
    </div>
  );
}
