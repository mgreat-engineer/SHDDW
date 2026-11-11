import { useState } from "react";
import { ArrowUpCircle, X } from "lucide-react";
import { fmtTime } from "@/lib/api";

const KEY = "shadow-helper-update-seen";

export default function UpdateBanner({ target }) {
  const upd = target?.helper?.last_update;
  const [seen, setSeen] = useState(() => localStorage.getItem(KEY));
  const recent = upd && Date.now() - new Date(upd.at).getTime() < 3 * 86400000;
  if (!recent || seen === `${upd.to}@${upd.at}`) return null;
  const dismiss = () => { const v = `${upd.to}@${upd.at}`; localStorage.setItem(KEY, v); setSeen(v); };
  return (
    <div className="flex items-center gap-3 rounded-lg border border-[#1E8E3E]/40 bg-[#1E8E3E]/10 text-[#1E8E3E] text-sm px-4 py-2 fade-up" data-testid="helper-update-banner">
      <ArrowUpCircle className="h-4 w-4 shrink-0" />
      <p className="flex-1">Shadow Helper on <span className="font-semibold">{target.helper.name}</span> updated itself to <span className="font-mono">{upd.to}</span> (from {upd.from}) on {fmtTime(upd.at)}.</p>
      <button onClick={dismiss} data-testid="helper-update-banner-dismiss" className="opacity-70 hover:opacity-100"><X className="h-4 w-4" /></button>
    </div>
  );
}
