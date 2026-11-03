import { useCallback, useEffect, useState } from "react";
import { ShieldOff } from "lucide-react";
import { toast } from "sonner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useApi, errMsg, fmtTime } from "@/lib/api";

const CATS = { pay: "Pay / purchase", send: "Send / submit", delete: "Delete / cancel" };

export default function PermissionsPanel({ refresh }) {
  const api = useApi();
  const [perms, setPerms] = useState([]);
  const [skills, setSkills] = useState([]);
  const [cat, setCat] = useState("send");
  const [scope, setScope] = useState("all");
  const load = useCallback(() => {
    api.get("/permissions").then((r) => setPerms(r.data)).catch(() => {});
    api.get("/skills").then((r) => setSkills(r.data)).catch(() => {});
  }, [api]);
  useEffect(() => { load(); }, [load, refresh]);

  const add = async () => { try { await api.post("/permissions", { category: cat, skill_id: scope === "all" ? null : scope }); load(); toast.success("Permission granted"); } catch (e) { toast.error(errMsg(e)); } };
  const revoke = async (p) => { try { await api.delete(`/permissions/${p.id}`); load(); toast("Permission turned off"); } catch (e) { toast.error(errMsg(e)); } };

  return (
    <div className="space-y-4" data-testid="permissions-panel">
      <p className="text-xs text-slate-400 leading-relaxed">By default Shadow stops and asks before paying, sending/submitting or deleting. Standing permissions skip that question.</p>
      <div className="rounded-lg border border-[#262B3D] bg-[#181B26] p-3 space-y-2">
        <Select value={cat} onValueChange={setCat}>
          <SelectTrigger className="bg-[#0F111A]" data-testid="permission-category-select"><SelectValue /></SelectTrigger>
          <SelectContent>{Object.entries(CATS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={scope} onValueChange={setScope}>
          <SelectTrigger className="bg-[#0F111A]" data-testid="permission-scope-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Everything</SelectItem>
            {skills.map((s) => <SelectItem key={s.id} value={s.id}>Only skill: {s.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <button onClick={add} className="w-full py-2 rounded-lg bg-[#00F0FF] text-black text-sm font-semibold" data-testid="permission-add-button">Allow without asking</button>
      </div>
      {perms.length === 0 && <p className="text-sm text-slate-500" data-testid="permissions-empty">No standing permissions — Shadow always asks.</p>}
      {perms.map((p) => (
        <div key={p.id} className="flex items-center gap-3 rounded-lg border border-[#FFB000]/30 bg-[#FFB000]/5 px-3 py-2.5" data-testid={`permission-item-${p.id}`}>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold">{CATS[p.category]}</p>
            <p className="text-[10px] font-mono text-slate-500">{p.skill_id ? `only "${p.skill_name || "skill"}"` : "everything"} · {fmtTime(p.created_at)}</p>
          </div>
          <button onClick={() => revoke(p)} className="text-xs flex items-center gap-1 text-slate-300 hover:text-[#FF3B30]" data-testid={`permission-revoke-button-${p.id}`}><ShieldOff className="h-3.5 w-3.5" />Turn off</button>
        </div>
      ))}
    </div>
  );
}
