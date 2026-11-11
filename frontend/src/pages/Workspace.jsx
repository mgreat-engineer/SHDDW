import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useApi, errMsg, getGroup, setGroup } from "@/lib/api";
import GroupBar from "@/components/shadow/GroupBar";
import GroupGrid from "@/components/shadow/GroupGrid";
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

const SOLO = new URLSearchParams(window.location.search).get("solo") === "1";
const NEEDS = { awaiting_approval: "needs your OK", waiting_input: "has a question" };

function useGroups(api, notifyOther) {
  const [data, setData] = useState({ groups: [], max: 10 });
  const seen = useRef({});
  const load = useCallback(async () => {
    try {
      const r = await api.get("/browser/groups");
      setData(r.data);
      r.data.groups.forEach((g) => {
        const prev = seen.current[g.id];
        const st = g.run?.status;
        if (st && prev?.status && prev.status !== st) notifyOther(g, st);
        if (!g.run && prev?.id) api.get(`/runs/${prev.id}`).then((x) => notifyOther(g, x.data.status, x.data)).catch(() => {});
        seen.current[g.id] = g.run ? { id: g.run.id, status: st } : null;
      });
    } catch {}
  }, [api, notifyOther]);
  useEffect(() => { load(); const t = setInterval(load, 2500); return () => clearInterval(t); }, [load]);
  return [data, load];
}

export default function Workspace() {
  const api = useApi();
  const [group, setGroupState] = useState(getGroup());
  const [view, setView] = useState("single");
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

  const notifyOther = useCallback((g, st, full) => {
    if (g.id === getGroup()) return;
    if (NEEDS[st]) notify(`${g.name} ${NEEDS[st]}`, g.run?.goal || "");
    else if (full && ALERT[st]) notify(`${g.name}: ${ALERT[st]}`, full.summary || full.goal);
  }, []);
  const lastRunByGroup = useRef({});
  const [{ groups, max }, loadGroups] = useGroups(api, notifyOther);
  const current = groups.find((g) => g.id === group);

  const switchGroup = useCallback((id) => {
    setGroup(id); setGroupState(id); setView("single");
    delete lastStatus.current[lastRunByGroup.current[id]];
    setBstate(null); setRunId(lastRunByGroup.current[id] || null); setRun(null); lastActive.current = null;
  }, []);
  useEffect(() => { if (groups.length && !current) switchGroup("1"); }, [groups, current, switchGroup]);
  useEffect(() => { if (current) document.title = SOLO ? `Shadow · ${current.name}` : "Shadow"; }, [current]);

  const newGroup = async () => {
    try { const r = await api.post("/browser/groups", { name: "" }); await loadGroups(); switchGroup(r.data.id); toast.success(`${r.data.name} opened`); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const closeGroup = async (g) => {
    try { await api.delete(`/browser/groups/${g.id}`); if (g.id === group) switchGroup("1"); loadGroups(); toast(`${g.name} closed`); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const renameGroup = async (id, name) => { try { await api.put(`/browser/groups/${id}`, { name }); loadGroups(); } catch (e) { toast.error(errMsg(e)); } };

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
      const g = getGroup();
      const r = await api.get("/runs/active");
      if (g !== getGroup()) return;
      const id = r.data.run?.id || null;
      if (id) lastRunByGroup.current[g] = id;
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
      setRunId(r.data.id); setRun(null); bump(); lastRunByGroup.current[getGroup()] = r.data.id; loadGroups();
      toast.success(r.data.status === "running" ? `Shadow is on it in ${current?.name || "this group"}` : "Reply sent");
    } catch (e) { toast.error(errMsg(e)); }
  };

  const runAction = async (action, body) => {
    try {
      await api.post(`/runs/${run.id}/${action}`, body); pollRun(); bump();
      if (action === "resume" && run.group_id && run.group_id !== getGroup()) { await loadGroups(); lastRunByGroup.current[run.group_id] = run.id; switchGroup(run.group_id); }
    }
    catch (e) { toast.error(errMsg(e)); }
  };

  const isRunning = run?.status === "running";
  const mode = bstate?.recording ? "recording" : isRunning ? "agent" : "manual";

  return (
    <div className="h-screen flex bg-[#08090E] text-slate-100 overflow-hidden grain" data-testid="workspace">
      {!SOLO && <SideRail panel={panel} setPanel={setPanel} />}
      {!SOLO && <SidePanel panel={panel} refresh={refresh} onRunSkill={(s) => startRun({ skill_id: s.id, command: "" })}
        onPreviewSkill={(s) => startRun({ skill_id: s.id, command: "", mode: "preview" })}
        onSelectRun={setRunId} selectedRunId={runId} target={target} onTarget={changeTarget} />}
      <main className="flex-1 min-w-0 flex flex-col p-3 gap-3 relative z-10">
        {status && !status.openai_configured && (
          <div className="rounded-lg border border-[#FFB000]/40 bg-[#FFB000]/10 text-[#FFB000] text-sm px-4 py-2" data-testid="openai-key-banner">
            OpenAI key not added yet — the browser works, but learning, commands and voice are off until the key is added.
          </div>
        )}
        {!SOLO && <UpdateBanner target={target} />}
        {SOLO ? (
          <p className="text-xs font-mono uppercase tracking-widest text-slate-400" data-testid="solo-group-name">Window group · <span className="text-[#00F0FF]">{current?.name || "…"}</span></p>
        ) : (
          <GroupBar groups={groups} max={max} current={group} view={view} onView={setView} onSelect={switchGroup} onNew={newGroup} onClose={closeGroup} onRename={renameGroup} />
        )}
        {view === "grid" && !SOLO ? <GroupGrid groups={groups} onOpen={switchGroup} /> : (
          <BrowserView key={group} mode={mode} onState={setBstate} state={bstate} onTakeOver={() => isRunning && runAction("pause")} target={target} onTarget={changeTarget} />
        )}
        <CommandBar recording={!!bstate?.recording} recorded={bstate?.recorded || []} recordedCount={bstate?.recorded_count || 0}
          waiting={run?.status === "waiting_input"} busy={isRunning} groupName={current?.name} onRecordChange={loadGroups} onRun={startRun} onRecorded={setRecorded} />
      </main>
      <ActivityPanel run={run} onAction={runAction} onRunReal={(r) => startRun({ skill_id: r.skill_id, command: "" })} />
      <ApprovalDialog run={run} onDecide={(decision) => runAction("approval", { decision })} />
      <SkillReviewDialog events={recorded} onClose={() => setRecorded(null)} onSaved={() => { setRecorded(null); setPanel("skills"); bump(); }} />
    </div>
  );
}
