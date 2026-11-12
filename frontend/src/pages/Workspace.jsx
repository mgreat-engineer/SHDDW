import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useApi, errMsg, getGroup, setGroup } from "@/lib/api";
import GroupBar from "@/components/shadow/GroupBar";
import GroupGrid from "@/components/shadow/GroupGrid";
import WorkspaceDialog from "@/components/shadow/WorkspaceDialog";
import SideRail from "@/components/shadow/SideRail";
import SidePanel from "@/components/shadow/SidePanel";
import BrowserView from "@/components/shadow/BrowserView";
import CommandBar from "@/components/shadow/CommandBar";
import ActivityPanel from "@/components/shadow/ActivityPanel";
import ApprovalDialog from "@/components/shadow/ApprovalDialog";
import SkillReviewDialog from "@/components/shadow/SkillReviewDialog";
import UpdateBanner from "@/components/shadow/UpdateBanner";
import HomeScreen from "@/components/shadow/HomeScreen";
import DesktopLinkDialog from "@/components/shadow/DesktopLinkDialog";
import { ArrowLeft } from "lucide-react";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";

const HANDLE = "w-1 bg-[#DADCE0] hover:bg-[#1A73E8]/60 data-[resize-handle-state=drag]:bg-[#1A73E8] transition-colors";

function useLayout() {
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const [left, setLeft] = useState(true);
  const [right, setRight] = useState(true);
  const [bar, setBar] = useState(localStorage.getItem("shadow-bar") !== "0");
  const flip = (ref) => { const p = ref.current; if (p) (p.isCollapsed() ? p.expand() : p.collapse()); };
  const toggleBar = () => setBar((b) => { localStorage.setItem("shadow-bar", b ? "0" : "1"); return !b; });
  return { leftRef, rightRef, left, right, bar, setLeft, setRight, toggleLeft: () => flip(leftRef), toggleRight: () => flip(rightRef), toggleBar };
}

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
  const [screen, setScreen] = useState(SOLO ? "browser" : "home");
  const [wsDialog, setWsDialog] = useState(null);
  const [panel, setPanel] = useState("skills");
  const layout = useLayout();
  const pickPanel = (id) => {
    const p = layout.leftRef.current;
    if (id === panel && p && !p.isCollapsed()) p.collapse();
    else { setPanel(id); p?.expand(); }
  };
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

  const [finished, setFinished] = useState({});
  const notifyOther = useCallback((g, st, full) => {
    if (full) setFinished((f) => ({ ...f, [g.id]: st }));
    else if (st) setFinished((f) => (f[g.id] ? { ...f, [g.id]: null } : f));
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

  const saveWorkspace = async (body) => {
    try {
      if (wsDialog?.id) { await api.put(`/browser/groups/${wsDialog.id}`, { name: body.name, label: body.label }); loadGroups(); }
      else { const r = await api.post("/browser/groups", body); await loadGroups(); switchGroup(r.data.id); toast.success(`${r.data.name} opened`); }
      setWsDialog(null);
    } catch (e) { toast.error(errMsg(e)); }
  };
  const allRuns = async (what) => {
    try {
      const r = await api.post(`/runs/${what}-all`);
      toast(what === "pause" ? `Paused ${r.data.paused} workspace task(s) — you have control` : `Resumed ${r.data.resumed} workspace task(s)`, { description: r.data.errors?.join(" · ") });
      loadGroups(); pollRun();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const closeGroup = async (g) => {
    try { await api.delete(`/browser/groups/${g.id}`); if (g.id === group) switchGroup("1"); loadGroups(); toast(`${g.name} closed`); }
    catch (e) { toast.error(errMsg(e)); }
  };

  useEffect(() => { api.get("/status").then((r) => setStatus(r.data)).catch(() => {}); }, [api]);

  const loadTarget = useCallback(() => api.get("/target").then((r) => setTarget(r.data)).catch(() => {}), [api]);
  useEffect(() => { loadTarget(); const t = setInterval(() => !document.hidden && loadTarget(), 4000); return () => clearInterval(t); }, [loadTarget]);
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
    const t = setInterval(() => { pollActive(); pollRun(); }, screen === "home" ? 4000 : 1500);
    return () => clearInterval(t);
  }, [pollActive, pollRun, screen]);

  const startRun = async (payload) => {
    try {
      if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
      const r = await api.post("/runs", payload);
      setRunId(r.data.id); setRun(null); bump(); lastRunByGroup.current[getGroup()] = r.data.id; loadGroups();
      const name = groups.find((x) => x.id === getGroup())?.name || "this workspace";
      toast.success(r.data.status === "running" ? `Shadow is on it in ${name}` : "Reply sent");
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

  const banner = status && !status.openai_configured && (
    <div className="rounded-lg border border-[#B06000]/40 bg-[#B06000]/10 text-[#B06000] text-sm px-4 py-2" data-testid="openai-key-banner">
      OpenAI key not added yet — the browser works, but learning, commands and voice are off until the key is added.
    </div>
  );

  if (screen === "home") return (
    <>
      <HomeScreen finished={finished} groups={groups} max={max} selected={group} onSelect={switchGroup}
        onRun={(id, command) => { switchGroup(id); startRun({ command }); }}
        onOpen={(id) => {
          switchGroup(id); setScreen("browser");
          if (!lastRunByGroup.current[id]) api.get("/runs").then((r) => { const last = r.data.find((x) => (x.group_id || "1") === id); if (last && getGroup() === id && !lastActive.current) { lastRunByGroup.current[id] = last.id; setRunId(last.id); } }).catch(() => {});
        }}
        onEdit={(g) => setWsDialog(g)} onClose={closeGroup} onNew={() => setWsDialog({})}
        onPauseAll={() => allRuns("pause")} onResumeAll={() => allRuns("resume")}
        banner={<>{banner}<UpdateBanner target={target} /></>}
        panelProps={{ refresh, target, onTarget: changeTarget, currentWorkspace: current, selectedRunId: runId,
          onRunSkill: (s) => startRun({ skill_id: s.id, command: "" }), onPreviewSkill: (s) => startRun({ skill_id: s.id, command: "", mode: "preview" }),
          onSelectRun: (id) => { setRunId(id); setScreen("browser"); },
          onTemplateOpened: async (g, r) => { if (r) lastRunByGroup.current[g.id] = r.id; await loadGroups(); switchGroup(g.id); bump(); } }} />
      <WorkspaceDialog open={!!wsDialog} workspace={wsDialog?.id ? wsDialog : null} onClose={() => setWsDialog(null)} onSave={saveWorkspace} />
      <ApprovalDialog run={run} onDecide={(decision) => runAction("approval", { decision })} />
      <DesktopLinkDialog onLinked={loadTarget} />
    </>
  );

  return (
    <div className="h-screen flex bg-white text-[#202124] overflow-hidden" data-testid="workspace">
      {!SOLO && <SideRail panel={panel} setPanel={pickPanel} open={layout.left} />}
      <ResizablePanelGroup direction="horizontal" autoSaveId={SOLO ? "shadow-layout-solo" : "shadow-layout"} className="flex-1 min-w-0">
      {!SOLO && <>
      <ResizablePanel id="left" order={1} ref={layout.leftRef} collapsible collapsedSize={0} minSize={14} maxSize={35} defaultSize={20}
        onCollapse={() => layout.setLeft(false)} onExpand={() => layout.setLeft(true)} data-testid="left-panel">
      <SidePanel panel={panel} refresh={refresh} onRunSkill={(s) => startRun({ skill_id: s.id, command: "" })}
        onPreviewSkill={(s) => startRun({ skill_id: s.id, command: "", mode: "preview" })}
        onSelectRun={setRunId} selectedRunId={runId} target={target} onTarget={changeTarget} onCollapse={layout.toggleLeft}
        currentWorkspace={current} onTemplateOpened={async (g, r) => { if (r) lastRunByGroup.current[g.id] = r.id; await loadGroups(); switchGroup(g.id); bump(); }} />
      </ResizablePanel>
      <ResizableHandle className={HANDLE} data-testid="left-resize-handle" />
      </>}
      <ResizablePanel id="main" order={2} minSize={35}>
      <main className="h-full min-w-0 flex flex-col p-2 gap-2 relative z-10 bg-[#F8F9FA]">
        {banner}
        {!SOLO && <UpdateBanner target={target} />}
        {SOLO ? (
          <p className="text-xs font-mono uppercase tracking-widest text-[#5F6368]" data-testid="solo-group-name">Workspace · <span className="text-[#1A73E8]">{current?.name || "…"}</span>{current?.label && <span className="text-[#3C4043]"> · {current.label}</span>}</p>
        ) : (
          <div className="flex items-center gap-2">
          <button onClick={() => setScreen("home")} data-testid="back-to-home-button" title="Back to main screen"
            className="shrink-0 flex items-center gap-1.5 h-8 px-3 rounded-lg border border-[#DADCE0] text-xs text-[#3C4043] hover:bg-[#F1F3F4] transition-colors"><ArrowLeft className="h-3.5 w-3.5" />Home</button>
          {layout.bar && <div className="flex-1 min-w-0"><GroupBar groups={groups} max={max} current={group} view={view} onView={setView} onSelect={switchGroup} onNew={() => setWsDialog({})} onClose={closeGroup} onEdit={(g) => setWsDialog(g)}
            onPauseAll={() => allRuns("pause")} onResumeAll={() => allRuns("resume")} /></div>}
          </div>
        )}
        {view === "grid" && !SOLO && layout.bar ? <GroupGrid groups={groups} onOpen={switchGroup} /> : (
          <BrowserView key={group} mode={mode} onState={setBstate} state={bstate} onTakeOver={() => isRunning && runAction("pause")} target={target} onTarget={changeTarget}
            layout={SOLO ? { ...layout, noLeft: true } : layout} />
        )}
        <CommandBar recording={!!bstate?.recording} recorded={bstate?.recorded || []} recordedCount={bstate?.recorded_count || 0}
          waiting={run?.status === "waiting_input"} busy={isRunning} groupName={current?.name} onRecordChange={loadGroups} onRun={startRun} onRecorded={setRecorded} />
      </main>
      </ResizablePanel>
      <ResizableHandle className={HANDLE} data-testid="right-resize-handle" />
      <ResizablePanel id="right" order={3} ref={layout.rightRef} collapsible collapsedSize={0} minSize={16} maxSize={40} defaultSize={22}
        onCollapse={() => layout.setRight(false)} onExpand={() => layout.setRight(true)} data-testid="right-panel">
        <ActivityPanel run={run} onAction={runAction} onRunReal={(r) => startRun({ skill_id: r.skill_id, command: "" })} onCollapse={layout.toggleRight} />
      </ResizablePanel>
      </ResizablePanelGroup>
      <WorkspaceDialog open={!!wsDialog} workspace={wsDialog?.id ? wsDialog : null} onClose={() => setWsDialog(null)} onSave={saveWorkspace} />
      <ApprovalDialog run={run} onDecide={(decision) => runAction("approval", { decision })} />
      <DesktopLinkDialog onLinked={loadTarget} />
      <SkillReviewDialog events={recorded} onClose={() => setRecorded(null)} onSaved={() => { setRecorded(null); setPanel("skills"); bump(); }} />
    </div>
  );
}
