const S = {
  running: ["Working", "text-[#00F0FF] border-[#00F0FF]/40 bg-[#00F0FF]/10"],
  awaiting_approval: ["Needs OK", "text-[#FF3B30] border-[#FF3B30]/50 bg-[#FF3B30]/10"],
  waiting_input: ["Question", "text-[#FFB000] border-[#FFB000]/40 bg-[#FFB000]/10"],
  paused: ["Paused", "text-[#FFB000] border-[#FFB000]/40 bg-[#FFB000]/10"],
  completed: ["Done", "text-[#00E676] border-[#00E676]/40 bg-[#00E676]/10"],
  failed: ["Failed", "text-[#FF3B30] border-[#FF3B30]/40 bg-[#FF3B30]/10"],
  stopped: ["Stopped", "text-slate-400 border-[#262B3D] bg-white/5"],
};

export default function StatusBadge({ status }) {
  const [t, c] = S[status] || [status, "text-slate-400 border-[#262B3D]"];
  return <span data-testid="run-status-badge" className={`shrink-0 text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border ${c}`}>{t}</span>;
}
