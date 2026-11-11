import { ChevronLeft } from "lucide-react";
import { PANELS } from "./SideRail";
import SkillsPanel from "./SkillsPanel";
import MemoryPanel from "./MemoryPanel";
import FilesPanel from "./FilesPanel";
import HistoryPanel from "./HistoryPanel";
import PermissionsPanel from "./PermissionsPanel";
import LaptopPanel from "./LaptopPanel";
import SchedulesPanel from "./SchedulesPanel";
import TemplatesPanel from "./TemplatesPanel";
import ReportsPanel from "./ReportsPanel";

export default function SidePanel({ panel, refresh, onRunSkill, onPreviewSkill, onSelectRun, selectedRunId, target, onTarget, currentWorkspace, onTemplateOpened, onCollapse }) {
  const label = PANELS.find((p) => p.id === panel)?.label;
  return (
    <aside className="w-full h-full bg-white flex flex-col relative z-10" data-testid="side-panel">
      <div className="px-5 pt-4 pb-3 flex items-start justify-between gap-2">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wider text-[#5F6368]">Shadow</p>
          <h2 className="font-display text-lg font-semibold tracking-tight" data-testid="side-panel-title">{label}</h2>
        </div>
        <button onClick={onCollapse} title="Hide side panel" data-testid="side-panel-collapse-button" className="h-7 w-7 -mr-2 rounded-full flex items-center justify-center text-[#5F6368] hover:bg-[#F1F3F4]"><ChevronLeft className="h-4 w-4" /></button>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto thin-scroll px-4 pb-4">
        {panel === "skills" && <SkillsPanel refresh={refresh} onRun={onRunSkill} onPreview={onPreviewSkill} />}
        {panel === "schedules" && <SchedulesPanel refresh={refresh} onSelectRun={onSelectRun} />}
        {panel === "templates" && <TemplatesPanel refresh={refresh} current={currentWorkspace} onOpened={onTemplateOpened} />}
        {panel === "reports" && <ReportsPanel refresh={refresh} onSelectRun={onSelectRun} />}
        {panel === "memory" && <MemoryPanel />}
        {panel === "files" && <FilesPanel refresh={refresh} target={target} />}
        {panel === "history" && <HistoryPanel refresh={refresh} onSelect={onSelectRun} selectedId={selectedRunId} />}
        {panel === "permissions" && <PermissionsPanel refresh={refresh} />}
        {panel === "laptop" && <LaptopPanel refresh={refresh} target={target} onTarget={onTarget} />}
      </div>
    </aside>
  );
}
