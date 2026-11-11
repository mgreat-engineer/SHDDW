import { AlertTriangle } from "lucide-react";
import { AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

const LABEL = { pay: "make a payment", send: "send or submit something", delete: "delete something" };

export default function ApprovalDialog({ run, onDecide }) {
  const open = run?.status === "awaiting_approval" && !!run.pending;
  const p = run?.pending || {};
  return (
    <AlertDialog open={open}>
      <AlertDialogContent className="bg-white border-2 border-[#D93025] shadow-[0_0_60px_rgba(255,59,48,0.25)] max-w-lg" data-testid="approval-modal">
        <AlertDialogHeader>
          <div className="flex items-center gap-2 text-[#D93025]">
            <AlertTriangle className="h-5 w-5" />
            <span className="text-xs font-mono uppercase tracking-widest">Approval needed · {p.risk}</span>
          </div>
          <AlertDialogTitle className="font-display text-xl">Shadow wants to {LABEL[p.risk] || "do something risky"}</AlertDialogTitle>
          <AlertDialogDescription className="text-[#3C4043]" data-testid="approval-reason">{p.reason}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="rounded-lg bg-[#F1F3F4] border border-[#DADCE0] p-3 space-y-1">
          <p className="text-xs font-mono text-[#5F6368] break-all" data-testid="approval-url">{p.url}</p>
          <p className="text-xs font-mono text-[#202124] break-all" data-testid="approval-action">{p.tool}({JSON.stringify(p.args)})</p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button onClick={() => onDecide("approve")} data-testid="approval-approve-button" className="py-2.5 rounded-lg bg-[#1E8E3E] text-white font-semibold text-sm hover:brightness-110">Approve once</button>
          <button onClick={() => onDecide("reject")} data-testid="approval-reject-button" className="py-2.5 rounded-lg bg-[#D93025] text-white font-semibold text-sm hover:brightness-110">Reject</button>
          <button onClick={() => onDecide("always")} data-testid="approval-always-button" className="py-2 rounded-lg border border-[#DADCE0] text-xs text-[#3C4043] hover:bg-[#F1F3F4]">Always allow "{p.risk}" without asking</button>
          {run?.skill_id ? (
            <button onClick={() => onDecide("always_skill")} data-testid="approval-always-skill-button" className="py-2 rounded-lg border border-[#DADCE0] text-xs text-[#3C4043] hover:bg-[#F1F3F4]">Always for this skill only</button>
          ) : <span />}
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}
