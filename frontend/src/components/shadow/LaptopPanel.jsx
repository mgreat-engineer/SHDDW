import { useCallback, useEffect, useState } from "react";
import { Check, Cloud, Copy, Download, Laptop, Unlink } from "lucide-react";
import { toast } from "sonner";
import { useApi, errMsg, fmtTime } from "@/lib/api";

const toB64Url = (s) => btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

export function TargetToggle({ target, onChange }) {
  const online = target?.helper_online;
  const btn = (id, Icon, label, disabled) => (
    <button key={id} disabled={disabled} onClick={() => onChange(id)} data-testid={`target-${id}-button`}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono uppercase tracking-wider transition-colors disabled:opacity-35 ${target?.target === id ? "bg-[#1A73E8]/15 text-[#1A73E8]" : "text-[#5F6368] hover:text-[#202124]"}`}>
      <Icon className="h-3.5 w-3.5" />{label}
    </button>
  );
  return (
    <div className="flex items-center rounded-lg border border-[#DADCE0] bg-[#F1F3F4] p-0.5" data-testid="target-toggle" title={online ? "" : "Open Shadow Helper on your laptop to use it"}>
      {btn("cloud", Cloud, "Cloud", false)}
      {btn("laptop", Laptop, "Laptop", !online)}
    </div>
  );
}

function PairCode() {
  const api = useApi();
  const [code, setCode] = useState(null);
  const [copied, setCopied] = useState(false);
  const make = async () => {
    try {
      const r = await api.post("/devices/pair-code");
      setCode({ text: toB64Url(JSON.stringify({ u: process.env.REACT_APP_BACKEND_URL, c: r.data.code })), exp: r.data.expires_at });
      setCopied(false);
    } catch (e) { toast.error(errMsg(e)); }
  };
  const copy = async () => { try { await navigator.clipboard.writeText(code.text); setCopied(true); } catch { toast.error("Copy failed — select the code and copy it"); } };
  if (!code) return <button onClick={make} className="w-full py-2 rounded-lg bg-[#1A73E8] text-white text-sm font-semibold" data-testid="pair-code-button">Get connection code</button>;
  return (
    <div className="space-y-2" data-testid="pair-code-box">
      <textarea readOnly value={code.text} rows={3} onFocus={(e) => e.target.select()} className="w-full bg-[#F1F3F4] border border-[#DADCE0] rounded-lg p-2 text-[11px] font-mono break-all outline-none" data-testid="pair-code-text" />
      <div className="flex gap-2">
        <button onClick={copy} className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-[#1A73E8] text-white text-sm font-semibold" data-testid="pair-code-copy-button">{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{copied ? "Copied" : "Copy code"}</button>
        <button onClick={make} className="px-3 rounded-lg border border-[#DADCE0] text-xs text-[#3C4043]" data-testid="pair-code-new-button">New</button>
      </div>
      <p className="text-[10px] font-mono text-[#80868B]">Paste it into Shadow Helper · works once · expires {fmtTime(code.exp)}</p>
    </div>
  );
}

function Device({ d, onUnlink }) {
  const i = d.info || {};
  return (
    <div className="rounded-lg border border-[#DADCE0] bg-white p-3 space-y-1.5" data-testid={`device-item-${d.id}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold flex items-center gap-2"><Laptop className="h-4 w-4 text-[#5F6368]" />{d.name}</p>
        <span data-testid={`device-status-${d.id}`} className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${d.online ? "text-[#1E8E3E] border-[#1E8E3E]/40" : "text-[#80868B] border-[#DADCE0]"}`}>{d.online ? "Online" : "Offline"}</span>
      </div>
      {i.os && <p className="text-[10px] font-mono text-[#80868B]" data-testid={`device-version-${d.id}`}>{i.os} · helper <span className="text-[#3C4043]">v{i.version}</span> · Chrome logins {i.chrome_logins ? "on" : "off"}</p>}
      {d.last_update && <p className="text-[11px] text-[#1E8E3E]" data-testid={`device-last-update-${d.id}`}>Updated {d.last_update.from} → {d.last_update.to} on {fmtTime(d.last_update.at)}</p>}
      {d.update_history?.length > 1 && (
        <details className="text-[10px] font-mono text-[#80868B]">
          <summary className="cursor-pointer">Update history</summary>
          {d.update_history.map((u) => <p key={u.at}>{fmtTime(u.at)} · {u.from} → {u.to}</p>)}
        </details>
      )}
      {i.folders?.length > 0 && (
        <div className="text-[11px] text-[#5F6368]">
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#80868B] mt-1">Allowed folders</p>
          {i.folders.map((f) => <p key={f} className="truncate font-mono" title={f}>{f}{f === i.downloads_folder ? "  ← downloads" : ""}</p>)}
        </div>
      )}
      <p className="text-[10px] font-mono text-[#80868B]">last seen {fmtTime(d.last_seen)}</p>
      <button onClick={() => onUnlink(d)} className="text-xs flex items-center gap-1 text-[#5F6368] hover:text-[#D93025]" data-testid={`device-unlink-button-${d.id}`}><Unlink className="h-3.5 w-3.5" />Unlink this computer</button>
    </div>
  );
}

export default function LaptopPanel({ target, onTarget, refresh }) {
  const api = useApi();
  const [devices, setDevices] = useState([]);
  const load = useCallback(() => api.get("/devices").then((r) => setDevices(r.data)).catch(() => {}), [api]);
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load, refresh]);
  const unlink = async (d) => {
    if (!window.confirm(`Unlink "${d.name}"? Shadow will no longer be able to use it.`)) return;
    try { await api.delete(`/devices/${d.id}`); load(); onTarget(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-4" data-testid="laptop-panel">
      <p className="text-xs text-[#5F6368] leading-relaxed">Shadow Helper runs a hidden Chrome on your Windows or Mac laptop. It uses only the folders you pick and never moves your mouse or keyboard.</p>
      <div className="rounded-lg border border-[#DADCE0] bg-white p-3 space-y-2">
        <p className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">Where Shadow works</p>
        <TargetToggle target={target} onChange={(t) => onTarget(t)} />
        <p className="text-[11px] text-[#80868B]" data-testid="laptop-helper-status">{target?.helper_online ? `Connected: ${target.helper?.name} · v${target.helper?.info?.version || "?"}` : "No laptop connected right now."}</p>
      </div>
      <div className="space-y-2">
        <p className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">Link a computer</p>
        <ol className="text-xs text-[#3C4043] space-y-1 list-decimal list-inside">
          <li>Install Shadow Helper (see below) and Google Chrome</li>
          <li>Open it and paste this code, then press Link</li>
          <li>Pick the folders Shadow may use</li>
        </ol>
        <PairCode />
      </div>
      {devices.map((d) => <Device key={d.id} d={d} onUnlink={unlink} />)}
      <div className="rounded-lg border border-dashed border-[#DADCE0] p-3 space-y-1.5" data-testid="laptop-install-help">
        <p className="text-xs font-semibold flex items-center gap-1.5"><Download className="h-3.5 w-3.5" />Get the installer</p>
        <p className="text-[11px] text-[#5F6368] leading-relaxed">Use <span className="text-[#202124]">Save to GitHub</span>. GitHub then builds the Windows (.exe) and Mac (.dmg) installers on its own. Download them from your repository's <span className="text-[#202124]">Releases</span> page.</p>
      </div>
    </div>
  );
}
