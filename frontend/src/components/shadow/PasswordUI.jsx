import { useState } from "react";
import { KeyRound, X } from "lucide-react";
import { toast } from "sonner";
import { errMsg } from "@/lib/api";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

const host = (o) => { try { return new URL(o).hostname; } catch { return o; } };

export function SavePasswordBubble({ api, offer, onDone }) {
  const [busy, setBusy] = useState(false);
  if (!offer) return null;
  const act = async (action) => {
    setBusy(true);
    try { const r = await api.post("/passwords/offer", { action }); if (r.data.saved) toast.success("Password saved"); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); onDone(); }
  };
  return (
    <div className="absolute right-3 top-[124px] z-30 w-[320px] rounded-lg bg-white border border-[#DADCE0] shadow-[0_4px_16px_rgba(60,64,67,0.25)] p-4 fade-up" data-testid="save-password-bubble">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2"><KeyRound className="h-4 w-4 text-[#1A73E8]" /><p className="text-sm font-semibold text-[#202124]">Save password?</p></div>
        <button onClick={() => act("dismiss")} className="p-0.5 rounded-full text-[#5F6368] hover:bg-[#F1F3F4]" data-testid="save-password-close"><X className="h-4 w-4" /></button>
      </div>
      <p className="text-xs text-[#5F6368] mt-1">Shadow will keep it encrypted and can sign in for you in every workspace.</p>
      <div className="mt-3 rounded-md bg-[#F1F3F4] px-3 py-2 text-xs">
        <p className="text-[#5F6368]">{host(offer.origin)}</p>
        <p className="text-[#202124] font-medium truncate" data-testid="save-password-username">{offer.username || "(no username)"}</p>
        <p className="text-[#202124] tracking-widest">••••••••</p>
      </div>
      <div className="flex justify-end gap-2 mt-3">
        <button disabled={busy} onClick={() => act("dismiss")} className="text-sm px-4 py-1.5 rounded-full border border-[#DADCE0] text-[#1A73E8] hover:bg-[#F1F3F4]" data-testid="save-password-dismiss">Not now</button>
        <button disabled={busy} onClick={() => act("save")} className="text-sm px-4 py-1.5 rounded-full bg-[#1A73E8] text-white font-medium hover:bg-[#1557B0]" data-testid="save-password-save">Save</button>
      </div>
    </div>
  );
}

export function KeyButton({ api, logins }) {
  const [open, setOpen] = useState(false);
  if (!logins?.length) return null;
  const fill = async (l) => {
    setOpen(false);
    try { await api.post(`/passwords/${l.id}/fill`); toast.success(`Filled ${l.username || "saved login"}`); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" title="Fill a saved password" data-testid="password-key-button" className="shrink-0 h-6 w-6 rounded-full flex items-center justify-center text-[#1A73E8] hover:bg-[#DADCE0]"><KeyRound className="h-4 w-4" /></button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-64 p-1 bg-white">
        <p className="text-[11px] text-[#5F6368] px-3 pt-2 pb-1">Saved logins for this site</p>
        {logins.map((l) => (
          <button key={l.id} onClick={() => fill(l)} data-testid={`password-fill-${l.id}`} className="w-full text-left text-sm px-3 py-2 rounded-md hover:bg-[#F1F3F4] flex items-center gap-2">
            <KeyRound className="h-3.5 w-3.5 text-[#5F6368]" /><span className="truncate">{l.username || "(no username)"}</span>
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
