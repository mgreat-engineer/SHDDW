import { useState } from "react";
import { Loader2, Mic, Send } from "lucide-react";
import { useApi } from "@/lib/api";
import { useVoice } from "./CommandBar";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function HomeTaskBox({ groups, selected, onSelect, onRun }) {
  const api = useApi();
  const [text, setText] = useState("");
  const g = groups.find((x) => x.id === selected);
  const waiting = g?.run?.status === "waiting_input";
  const submit = (t = text) => { if (!t.trim()) return; onRun(selected, t.trim()); setText(""); };
  const voice = useVoice(api, (t) => submit(t));
  return (
    <div className="rounded-3xl border border-[#DADCE0] bg-white shadow-[0_8px_30px_rgba(60,64,67,0.10)] p-3 flex flex-col gap-3 focus-within:border-[#1A73E8]/60 transition-colors" data-testid="home-task-box">
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} data-testid="home-task-input"
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
        placeholder={waiting ? `Reply to ${g.name}'s question…` : voice.listening ? "Listening… release to send" : "What should Shadow do?"}
        className="w-full resize-none bg-transparent outline-none text-base px-3 pt-2 placeholder:text-[#80868B]" />
      <div className="flex items-center gap-2">
        <Select value={selected} onValueChange={onSelect}>
          <SelectTrigger className="w-auto min-w-[160px] h-9 rounded-full border-[#DADCE0] text-sm" data-testid="home-workspace-select"><SelectValue /></SelectTrigger>
          <SelectContent>{groups.map((x) => <SelectItem key={x.id} value={x.id} data-testid={`home-workspace-option-${x.id}`}>{x.name}</SelectItem>)}</SelectContent>
        </Select>
        <span className="flex-1" />
        <button onPointerDown={voice.start} onPointerUp={voice.stop} onPointerLeave={() => voice.listening && voice.stop()} data-testid="home-voice-button" title="Hold to talk"
          className={`h-9 w-9 rounded-full flex items-center justify-center transition-colors ${voice.listening ? "bg-[#1A73E8] text-white rec-pulse" : "bg-[#F1F3F4] text-[#3C4043] hover:bg-[#E8EAED]"}`}>
          {voice.busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mic className="h-4 w-4" />}
        </button>
        <button onClick={() => submit()} disabled={!text.trim()} data-testid="home-task-submit"
          className="flex items-center gap-2 h-9 px-5 rounded-full bg-[#1A73E8] text-white text-sm font-semibold hover:bg-[#1765CC] disabled:opacity-40 transition-colors"><Send className="h-4 w-4" />{waiting ? "Reply" : "Run"}</button>
      </div>
    </div>
  );
}
