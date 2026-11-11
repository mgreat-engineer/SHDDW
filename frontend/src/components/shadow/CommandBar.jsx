import { useRef, useState } from "react";
import { Circle, Loader2, Mic, Send, Square, StickyNote } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg } from "@/lib/api";

const CHIPS = ["Open three tabs and compare prices for", "Download my latest invoice from", "Fill this form using my memory on"];

function useVoice(api, onText) {
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const rec = useRef(null);
  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream); const chunks = [];
      mr.ondataavailable = (e) => chunks.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        if (blob.size < 2000) return;
        setBusy(true);
        const fd = new FormData(); fd.append("file", blob, "voice.webm");
        try { const r = await api.post("/voice/transcribe", fd); if (r.data.text?.trim()) onText(r.data.text.trim()); }
        catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
      };
      mr.start(); rec.current = mr; setListening(true);
    } catch { toast.error("Microphone not available"); }
  };
  const stop = () => { if (rec.current?.state === "recording") rec.current.stop(); setListening(false); };
  return { listening, busy, start, stop };
}

export default function CommandBar({ recording, recorded, recordedCount, waiting, busy, onRun, onRecorded, groupName, onRecordChange = () => {} }) {
  const api = useApi();
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const submit = (t = text) => { if (!t.trim()) return; onRun({ command: t.trim() }); setText(""); };
  const voice = useVoice(api, (t) => submit(t));

  const startRec = async () => { try { await api.post("/record/start"); onRecordChange(); toast("Recording — do the task in the browser"); } catch (e) { toast.error(errMsg(e)); } };
  const stopRec = async () => { try { const r = await api.post("/record/stop"); onRecordChange(); onRecorded(r.data.events); } catch (e) { toast.error(errMsg(e)); } };
  const addNote = async (e) => { e.preventDefault(); if (!note.trim()) return; try { await api.post("/record/note", { text: note }); setNote(""); toast.success("Note added to this step"); } catch (err) { toast.error(errMsg(err)); } };

  if (recording) return (
    <div className="rounded-2xl border border-[#D93025]/50 bg-white/90 backdrop-blur-xl p-3 flex flex-col gap-2 fade-up" data-testid="recording-bar">
      <div className="flex items-center gap-3">
        <span className="h-2.5 w-2.5 rounded-full bg-[#D93025] rec-pulse" />
        <span className="text-xs font-mono uppercase tracking-widest text-[#D93025]" data-testid="recording-indicator">Watching you · {recordedCount} steps</span>
        <p className="flex-1 text-xs text-[#5F6368] truncate font-mono" data-testid="recording-last-step">{recorded[recorded.length - 1] || "Do your task in the browser above"}</p>
        <button onClick={stopRec} data-testid="stop-recording-button" className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#D93025] text-white text-sm font-semibold hover:bg-[#B3261E] transition-colors"><Square className="h-3.5 w-3.5 fill-white" />Stop & learn</button>
      </div>
      <form onSubmit={addNote} className="flex items-center gap-2">
        <StickyNote className="h-4 w-4 text-[#80868B]" />
        <input value={note} onChange={(e) => setNote(e.target.value)} data-testid="recording-note-input" placeholder='Add a note for this step, e.g. "always pick the latest invoice"'
          className="flex-1 bg-transparent outline-none text-sm placeholder:text-[#9AA0A6]" />
        <button data-testid="recording-note-submit" className="text-xs text-[#3C4043] px-3 py-1 rounded border border-[#DADCE0] hover:bg-[#F1F3F4]">Add note</button>
      </form>
    </div>
  );

  return (
    <div className="rounded-2xl border border-[#1A73E8]/25 bg-white/90 backdrop-blur-xl shadow-[0_10px_30px_rgba(0,0,0,0.6)] p-2.5" data-testid="command-bar">
      {!waiting && !text && (
        <div className="flex gap-2 px-1 pb-2 overflow-x-auto thin-scroll">
          {CHIPS.map((c) => <button key={c} onClick={() => setText(c + " ")} className="shrink-0 text-[11px] px-2.5 py-1 rounded-full border border-[#DADCE0] text-[#5F6368] hover:text-[#202124] hover:border-[#1A73E8]/40 transition-colors" data-testid="command-chip">{c}…</button>)}
        </div>
      )}
      <div className="flex items-center gap-2">
        <button onClick={startRec} disabled={busy} data-testid="watch-me-record-button" title="Watch me"
          className="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-[#D93025]/40 text-[#D93025] text-sm font-semibold hover:bg-[#D93025]/10 disabled:opacity-40 transition-colors"><Circle className="h-3 w-3 fill-[#D93025]" />Watch me</button>
        <button onPointerDown={voice.start} onPointerUp={voice.stop} onPointerLeave={() => voice.listening && voice.stop()} data-testid="voice-mic-button" title="Hold to talk"
          className={`h-10 w-10 shrink-0 rounded-xl flex items-center justify-center transition-colors ${voice.listening ? "bg-[#1A73E8] text-white rec-pulse" : "bg-[#F1F3F4] text-[#3C4043] hover:bg-[#E8EAED]"}`}>
          {voice.busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mic className="h-4 w-4" />}
        </button>
        <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} data-testid="command-input"
          placeholder={waiting ? "Reply to Shadow's question…" : voice.listening ? "Listening… release to send" : `Tell Shadow what to do in ${groupName || "this workspace"}, or name a skill…`}
          className="flex-1 bg-transparent outline-none text-sm px-2 placeholder:text-[#80868B]" />
        <button onClick={() => submit()} disabled={!text.trim()} data-testid="command-submit-button"
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#1A73E8] text-white text-sm font-semibold hover:shadow-[0_0_20px_rgba(26,115,232,0.45)] disabled:opacity-40 transition-shadow"><Send className="h-4 w-4" />{waiting ? "Reply" : "Run"}</button>
      </div>
    </div>
  );
}
