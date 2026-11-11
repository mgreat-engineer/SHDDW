const S = {
  running: ["Working", "text-[#1A73E8] border-[#1A73E8]/40 bg-[#1A73E8]/10"],
  awaiting_approval: ["Needs OK", "text-[#D93025] border-[#D93025]/50 bg-[#D93025]/10"],
  waiting_input: ["Question", "text-[#B06000] border-[#B06000]/40 bg-[#B06000]/10"],
  paused: ["Paused", "text-[#B06000] border-[#B06000]/40 bg-[#B06000]/10"],
  completed: ["Done", "text-[#1E8E3E] border-[#1E8E3E]/40 bg-[#1E8E3E]/10"],
  failed: ["Failed", "text-[#D93025] border-[#D93025]/40 bg-[#D93025]/10"],
  stopped: ["Stopped", "text-[#5F6368] border-[#DADCE0] bg-[#F1F3F4]"],
};

export default function StatusBadge({ status, testId = "run-status-badge" }) {
  const [t, c] = S[status] || [status, "text-[#5F6368] border-[#DADCE0]"];
  return <span data-testid={testId} className={`shrink-0 text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border ${c}`}>{t}</span>;
}
