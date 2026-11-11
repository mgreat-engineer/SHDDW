import { useState } from "react";
import { ExternalLink, LayoutGrid, Plus, Square, X } from "lucide-react";

const DOT = { running: "bg-[#00F0FF] rec-pulse", awaiting_approval: "bg-[#FFB000] rec-pulse", waiting_input: "bg-[#FFB000] rec-pulse", paused: "bg-slate-400" };

export const popOut = (id) => window.open(`/?group=${id}&solo=1`, `shadow-group-${id}`, "popup,width=1440,height=920");

function Chip({ g, active, onSelect, onClose, onRename }) {
  const [edit, setEdit] = useState(false);
  const [name, setName] = useState(g.name);
  const save = () => { setEdit(false); if (name.trim() && name !== g.name) onRename(g.id, name.trim()); };
  return (
    <div data-testid={`group-chip-${g.id}`} onClick={() => onSelect(g.id)} onDoubleClick={() => { setName(g.name); setEdit(true); }}
      className={`group/chip shrink-0 flex items-center gap-2 pl-3 pr-1.5 py-1.5 rounded-lg border text-xs cursor-pointer transition-colors ${active ? "border-[#00F0FF]/50 bg-[#00F0FF]/10 text-slate-100" : "border-[#262B3D] text-slate-400 hover:bg-white/5"}`}>
      <span className={`h-2 w-2 rounded-full ${DOT[g.run?.status] || (g.recording ? "bg-[#FF3B30]" : "bg-slate-600")}`} data-testid={`group-status-${g.id}`} title={g.run ? `${g.run.status}: ${g.run.goal}` : "Idle"} />
      {edit ? (
        <input autoFocus value={name} onChange={(e) => setName(e.target.value)} onBlur={save} onKeyDown={(e) => e.key === "Enter" && save()}
          onClick={(e) => e.stopPropagation()} data-testid={`group-rename-input-${g.id}`} className="w-28 bg-transparent outline-none border-b border-[#00F0FF]/50" />
      ) : <span className="max-w-[140px] truncate" data-testid={`group-name-${g.id}`}>{g.name}</span>}
      <span className="font-mono text-[10px] text-slate-500">{g.tabs}</span>
      <button title="Open in its own window (drag it to another screen)" data-testid={`group-popout-${g.id}`} onClick={(e) => { e.stopPropagation(); popOut(g.id); }}
        className="p-0.5 rounded opacity-50 hover:opacity-100 hover:bg-white/10"><ExternalLink className="h-3 w-3" /></button>
      {g.id !== "1" && (
        <button title="Close group" data-testid={`group-close-${g.id}`} onClick={(e) => { e.stopPropagation(); onClose(g); }}
          className="p-0.5 rounded opacity-50 hover:opacity-100 hover:bg-white/10"><X className="h-3 w-3" /></button>
      )}
    </div>
  );
}

export default function GroupBar({ groups, max, current, view, onView, onSelect, onNew, onClose, onRename }) {
  return (
    <div className="flex items-center gap-2" data-testid="group-bar">
      <button onClick={() => onView(view === "grid" ? "single" : "grid")} data-testid="group-grid-toggle" title={view === "grid" ? "Show one group" : "See all groups"}
        className={`shrink-0 h-8 w-8 rounded-lg border flex items-center justify-center transition-colors ${view === "grid" ? "border-[#00F0FF]/50 text-[#00F0FF] bg-[#00F0FF]/10" : "border-[#262B3D] text-slate-400 hover:bg-white/5"}`}>
        {view === "grid" ? <Square className="h-3.5 w-3.5" /> : <LayoutGrid className="h-3.5 w-3.5" />}
      </button>
      <div className="flex-1 min-w-0 flex items-center gap-2 overflow-x-auto thin-scroll">
        {groups.map((g) => <Chip key={g.id} g={g} active={view !== "grid" && g.id === current} onSelect={onSelect} onClose={onClose} onRename={onRename} />)}
      </div>
      <button onClick={onNew} disabled={groups.length >= max} data-testid="group-new-button"
        className="shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-[#00F0FF]/40 text-[#00F0FF] hover:bg-[#00F0FF]/10 disabled:opacity-40 transition-colors">
        <Plus className="h-3.5 w-3.5" />New group <span className="font-mono text-[10px] text-slate-500">{groups.length}/{max}</span>
      </button>
    </div>
  );
}
