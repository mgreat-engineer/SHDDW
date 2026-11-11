import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { useApi } from "@/lib/api";
import StatusBadge from "./StatusBadge";
import { popOut } from "./GroupBar";

function useTileFrame(api, id) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let alive = true, prev = null, timer;
    const tick = async () => {
      if (!document.hidden) {
        try {
          const r = await api.get("/browser/frame", { responseType: "blob", params: { group: id, quality: 30 } });
          const u = URL.createObjectURL(r.data);
          if (!alive) return URL.revokeObjectURL(u);
          setSrc(u); if (prev) URL.revokeObjectURL(prev); prev = u;
        } catch {}
      }
      if (alive) timer = setTimeout(tick, 1600);
    };
    tick();
    return () => { alive = false; clearTimeout(timer); if (prev) URL.revokeObjectURL(prev); };
  }, [api, id]);
  return src;
}

function Tile({ g, onOpen }) {
  const api = useApi();
  const src = useTileFrame(api, g.id);
  return (
    <div onClick={() => onOpen(g.id)} data-testid={`group-tile-${g.id}`}
      className="group/tile cursor-pointer rounded-xl border border-[#262B3D] bg-[#0F111A] overflow-hidden flex flex-col hover:border-[#00F0FF]/50 transition-colors fade-up">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[#262B3D] bg-[#181B26]">
        <span className="flex-1 min-w-0 flex flex-col leading-tight">
          <span className="text-xs font-semibold truncate" data-testid={`group-tile-name-${g.id}`}>{g.name}</span>
          {g.label && <span className="text-[10px] text-[#00F0FF]/70 truncate" data-testid={`group-tile-label-${g.id}`}>{g.label}</span>}
        </span>
        {g.run ? <StatusBadge status={g.run.status} /> : <span className="text-[10px] font-mono uppercase text-slate-500">{g.recording ? "recording" : "idle"}</span>}
        <button title="Open in its own window" data-testid={`group-tile-popout-${g.id}`} onClick={(e) => { e.stopPropagation(); popOut(g.id); }}
          className="p-1 rounded text-slate-400 hover:bg-white/10"><ExternalLink className="h-3.5 w-3.5" /></button>
      </div>
      <div className="aspect-[16/10] bg-black/60 flex items-center justify-center">
        {src ? <img src={src} alt={g.name} className="w-full h-full object-contain" draggable={false} /> : <span className="text-xs font-mono text-slate-600 animate-pulse">Loading…</span>}
      </div>
      <p className="px-3 py-2 text-[11px] text-slate-400 truncate" title={g.run?.goal || g.url} data-testid={`group-tile-goal-${g.id}`}>{g.run?.goal || g.url || "Empty"}</p>
    </div>
  );
}

export default function GroupGrid({ groups, onOpen }) {
  return (
    <section className="flex-1 min-h-0 overflow-y-auto thin-scroll" data-testid="group-grid">
      <div className="grid gap-3 grid-cols-1 md:grid-cols-2 2xl:grid-cols-3">
        {groups.map((g) => <Tile key={g.id} g={g} onOpen={onOpen} />)}
      </div>
    </section>
  );
}
