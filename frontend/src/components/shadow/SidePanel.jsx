import { PANELS } from "./SideRail";
import SkillsPanel from "./SkillsPanel";
import MemoryPanel from "./MemoryPanel";
import FilesPanel from "./FilesPanel";
import HistoryPanel from "./HistoryPanel";
import PermissionsPanel from "./PermissionsPanel";

export default function SidePanel({ panel, refresh, onRunSkill, onSelectRun, selectedRunId }) {
  const label = PANELS.find((p) => p.id === panel)?.label;
  return (
    <aside className="w-[300px] shrink-0 border-r border-[#262B3D] bg-[#0F111A] flex flex-col relative z-10" data-testid="side-panel">
      <div className="px-5 pt-5 pb-3">
        <p className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Shadow</p>
        <h2 className="font-display text-lg font-semibold tracking-tight" data-testid="side-panel-title">{label}</h2>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto thin-scroll px-4 pb-4">
        {panel === "skills" && <SkillsPanel refresh={refresh} onRun={onRunSkill} />}
        {panel === "memory" && <MemoryPanel />}
        {panel === "files" && <FilesPanel refresh={refresh} />}
        {panel === "history" && <HistoryPanel refresh={refresh} onSelect={onSelectRun} selectedId={selectedRunId} />}
        {panel === "permissions" && <PermissionsPanel refresh={refresh} />}
      </div>
    </aside>
  );
}
