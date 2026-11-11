import { ExternalLink, LayoutGrid, Pause, Pencil, Play, Plus, Square, X } from "lucide-react";

const DOT = { running: "bg-[#00F0FF] rec-pulse", awaiting_approval: "bg-[#FFB000] rec-pulse", waiting_input: "bg-[#FFB000] rec-pulse", paused: "bg-slate-400" };

export const popOut = (id) => window.open(`/?group=${id}&solo=1`, `shadow-group-${id}`, "popup,width=1440,height=920");

function Chip({ g, active, onSelect, onClose, onEdit }) {
  const ib = "p-0.5 rounded opacity-50 hover:opacity-100 hover:bg-white/10";
  return (
    <div data-testid={`group-chip-${g.id}`} onClick={() => onSelect(g.id)} onDoubleClick={() => onEdit(g)}
      className={`shrink-0 flex items-center gap-2 pl-3 pr-1.5 py-1.5 rounded-lg border text-xs cursor-pointer transition-colors ${active ? "border-[#00F0FF]/50 bg-[#00F0FF]/10 text-slate-100" : "border-[#262B3D] text-slate-400 hover:bg-white/5"}`}>
      <span className={`h-2 w-2 rounded-full ${DOT[g.run?.status] || (g.recording ? "bg-[#FF3B30]" : "bg-slate-600")}`} data-testid={`group-status-${g.id}`} title={g.run ? `${g.run.status}: ${g.run.goal}` : "Idle"} />
      <span className="flex flex-col leading-tight max-w-[150px]">
        <span className="truncate" data-testid={`group-name-${g.id}`}>{g.name}</span>
        {g.label && <span className="truncate text-[11px] text-[#00F0FF]/90" data-testid={`group-label-${g.id}`}>{g.label}</span>}
      </span>
      <span className="font-mono text-[10px] text-slate-500">{g.tabs}</span>
      <button title="Edit name and client" data-testid={`group-edit-${g.id}`} onClick={(e) => { e.stopPropagation(); onEdit(g); }} className={ib}><Pencil className="h-3 w-3" /></button>
      <button title="Open in its own window (drag it to another screen)" data-testid={`group-popout-${g.id}`} onClick={(e) => { e.stopPropagation(); popOut(g.id); }} className={ib}><ExternalLink className="h-3 w-3" /></button>
      {g.id !== "1" && <button title="Close workspace" data-testid={`group-close-${g.id}`} onClick={(e) => { e.stopPropagation(); onClose(g); }} className={ib}><X className="h-3 w-3" /></button>}
    </div>
  );
}

export default function GroupBar({ groups, max, current, view, onView, onSelect, onNew, onClose, onEdit, onPauseAll, onResumeAll }) {
  const btn = "shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors disabled:opacity-40";
  const anyRunning = groups.some((g) => g.run?.status === "running");
  const anyPaused = groups.some((g) => g.run?.status === "paused");
  return (
    <div className="flex items-center gap-2" data-testid="group-bar">
      <button onClick={() => onView(view === "grid" ? "single" : "grid")} data-testid="group-grid-toggle" title={view === "grid" ? "Show one workspace" : "See all workspaces"}
        className={`shrink-0 h-8 w-8 rounded-lg border flex items-center justify-center transition-colors ${view === "grid" ? "border-[#00F0FF]/50 text-[#00F0FF] bg-[#00F0FF]/10" : "border-[#262B3D] text-slate-400 hover:bg-white/5"}`}>
        {view === "grid" ? <Square className="h-3.5 w-3.5" /> : <LayoutGrid className="h-3.5 w-3.5" />}
      </button>
      <div className="flex-1 min-w-0 flex items-center gap-2 overflow-x-auto thin-scroll">
        {groups.map((g) => <Chip key={g.id} g={g} active={view !== "grid" && g.id === current} onSelect={onSelect} onClose={onClose} onEdit={onEdit} />)}
      </div>
      <button onClick={onPauseAll} disabled={!anyRunning} data-testid="pause-all-button" className={`${btn} border-[#FFB000]/40 text-[#FFB000] hover:bg-[#FFB000]/10`}><Pause className="h-3.5 w-3.5" />Pause all</button>
      <button onClick={onResumeAll} disabled={!anyPaused} data-testid="resume-all-button" className={`${btn} border-[#262B3D] text-slate-300 hover:bg-white/5`}><Play className="h-3.5 w-3.5" />Resume all</button>
      <button onClick={onNew} disabled={groups.length >= max} data-testid="group-new-button" className={`${btn} border-[#00F0FF]/40 text-[#00F0FF] hover:bg-[#00F0FF]/10`}>
        <Plus className="h-3.5 w-3.5" />New workspace <span className="font-mono text-[10px] text-slate-500">{groups.length}/{max}</span>
      </button>
    </div>
  );
}
