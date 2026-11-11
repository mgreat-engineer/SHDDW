import { ExternalLink, Eye, Pencil, Plus, X } from "lucide-react";
import StatusBadge from "./StatusBadge";
import { popOut } from "./GroupBar";

const ib = "p-1.5 rounded-full text-[#5F6368] hover:bg-[#F1F3F4] hover:text-[#202124] transition-colors";

function Card({ g, done, onOpen, onEdit, onClose, i }) {
  return (
    <div onClick={() => onOpen(g.id)} data-testid={`workspace-card-${g.id}`} style={{ animationDelay: `${i * 50}ms` }}
      className="group/card fade-up cursor-pointer rounded-2xl border border-[#DADCE0] bg-white p-5 flex flex-col gap-6 hover:border-[#1A73E8]/50 hover:shadow-[0_4px_16px_rgba(60,64,67,0.12)] transition-[border-color,box-shadow]">
      <div className="relative">
        <span title={g.name} className="block font-display text-base font-semibold truncate max-md:pr-24 md:group-hover/card:pr-24" data-testid={`workspace-card-name-${g.id}`}>{g.name}</span>
        <span className="absolute -right-2 -top-1 flex bg-white rounded-full md:opacity-0 md:group-hover/card:opacity-100 transition-opacity">
          <button title="Rename" data-testid={`workspace-card-edit-${g.id}`} onClick={(e) => { e.stopPropagation(); onEdit(g); }} className={ib}><Pencil className="h-3.5 w-3.5" /></button>
          <button title="Open in its own window" data-testid={`workspace-card-popout-${g.id}`} onClick={(e) => { e.stopPropagation(); popOut(g.id); }} className={ib}><ExternalLink className="h-3.5 w-3.5" /></button>
          {g.id !== "1" && <button title="Close workspace" data-testid={`workspace-card-close-${g.id}`} onClick={(e) => { e.stopPropagation(); onClose(g); }} className={ib}><X className="h-3.5 w-3.5" /></button>}
        </span>
      </div>
      <div className="flex items-center justify-between">
        {g.run || done ? <StatusBadge status={g.run?.status || done} testId={`workspace-card-status-${g.id}`} />
          : <span data-testid={`workspace-card-status-${g.id}`} className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border border-[#DADCE0] text-[#5F6368]">{g.recording ? "Recording" : "Idle"}</span>}
        <span className="flex items-center gap-1 text-xs text-[#1A73E8] md:opacity-0 md:group-hover/card:opacity-100 transition-opacity"><Eye className="h-3.5 w-3.5" />Watch</span>
      </div>
    </div>
  );
}

export default function WorkspaceCards({ finished = {}, groups, max, onOpen, onEdit, onClose, onNew }) {
  return (
    <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" data-testid="workspace-cards">
      {groups.map((g, i) => <Card key={g.id} g={g} done={finished[g.id]} i={i} onOpen={onOpen} onEdit={onEdit} onClose={onClose} />)}
      {!groups.length && [0, 1].map((i) => <div key={i} className="rounded-2xl border border-[#DADCE0] bg-white min-h-[116px] animate-pulse" data-testid="workspace-card-skeleton" />)}
      {groups.length > 0 && groups.length < max && (
        <button onClick={onNew} data-testid="workspace-card-new"
          className="rounded-2xl border border-dashed border-[#BDC1C6] p-5 flex items-center justify-center gap-2 text-sm text-[#5F6368] hover:border-[#1A73E8] hover:text-[#1A73E8] transition-colors min-h-[116px]">
          <Plus className="h-4 w-4" />New workspace <span className="font-mono text-[10px]">{groups.length}/{max}</span>
        </button>
      )}
    </div>
  );
}
