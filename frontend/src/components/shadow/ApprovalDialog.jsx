import { AlertTriangle } from "lucide-react";
import { AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

const LABEL = { pay: "make a payment", send: "send or submit something", delete: "delete something" };

export default function ApprovalDialog({ run, onDecide }) {
  const open = run?.status === "awaiting_approval" && !!run.pending;
  const p = run?.pending || {};
  return (
    <AlertDialog open={open}>
      <AlertDialogContent className="bg-[#12141C] border-2 border-[#FF3B30] shadow-[0_0_60px_rgba(255,59,48,0.25)] max-w-lg" data-testid="approval-modal">
        <AlertDialogHeader>
          <div className="flex items-center gap-2 text-[#FF3B30]">
            <AlertTriangle className="h-5 w-5" />
            <span className="text-xs font-mono uppercase tracking-widest">Approval needed · {p.risk}</span>
          </div>
          <AlertDialogTitle className="font-display text-xl">Shadow wants to {LABEL[p.risk] || "do something risky"}</AlertDialogTitle>
          <AlertDialogDescription className="text-slate-300" data-testid="approval-reason">{p.reason}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="rounded-lg bg-black/40 border border-[#262B3D] p-3 space-y-1">
          <p className="text-xs font-mono text-slate-400 break-all" data-testid="approval-url">{p.url}</p>
          <p className="text-xs font-mono text-slate-200 break-all" data-testid="approval-action">{p.tool}({JSON.stringify(p.args)})</p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button onClick={() => onDecide("approve")} data-testid="approval-approve-button" className="py-2.5 rounded-lg bg-[#00E676] text-black font-semibold text-sm hover:brightness-110">Approve once</button>
          <button onClick={() => onDecide("reject")} data-testid="approval-reject-button" className="py-2.5 rounded-lg bg-[#FF3B30] text-white font-semibold text-sm hover:brightness-110">Reject</button>
          <button onClick={() => onDecide("always")} data-testid="approval-always-button" className="py-2 rounded-lg border border-[#262B3D] text-xs text-slate-300 hover:bg-white/5">Always allow "{p.risk}" without asking</button>
          {run?.skill_id ? (
            <button onClick={() => onDecide("always_skill")} data-testid="approval-always-skill-button" className="py-2 rounded-lg border border-[#262B3D] text-xs text-slate-300 hover:bg-white/5">Always for this skill only</button>
          ) : <span />}
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}
