import { useState } from "react";
import { MessageSquareWarning } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg } from "@/lib/api";

export default function DialogBar({ dialog, onDone }) {
  const api = useApi();
  const [text, setText] = useState("");
  if (!dialog) return null;
  const answer = async (accept) => {
    try { await api.post("/browser/dialog", { accept, text }); setText(""); onDone(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 bg-[#FFB000]/10 border-b border-[#FFB000]/40 fade-up" data-testid="page-dialog-bar">
      <MessageSquareWarning className="h-4 w-4 text-[#FFB000] shrink-0" />
      <p className="text-sm flex-1 truncate"><span className="font-mono text-xs uppercase text-[#FFB000] mr-2">{dialog.type}</span>{dialog.message}</p>
      {dialog.type === "prompt" && (
        <input data-testid="page-dialog-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={dialog.default || "Answer"}
          className="bg-[#0F111A] border border-[#262B3D] rounded px-2 py-1 text-sm outline-none" />
      )}
      <button data-testid="page-dialog-accept" onClick={() => answer(true)} className="text-xs px-3 py-1.5 rounded bg-[#FFB000] text-black font-semibold">OK</button>
      {dialog.type !== "alert" && (
        <button data-testid="page-dialog-dismiss" onClick={() => answer(false)} className="text-xs px-3 py-1.5 rounded border border-[#262B3D] hover:bg-white/5">Cancel</button>
      )}
    </div>
  );
}
