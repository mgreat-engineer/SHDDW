import { useEffect, useState } from "react";
import { Loader2, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApi, errMsg } from "@/lib/api";
import SkillEditor from "./SkillEditor";

export default function SkillReviewDialog({ events, onClose, onSaved }) {
  const api = useApi();
  const [hint, setHint] = useState("");
  const [skill, setSkill] = useState(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => { setSkill(null); setHint(""); }, [events]);

  const learn = async () => {
    setLoading(true);
    try { const r = await api.post("/skills/synthesize", { events, hint }); setSkill(r.data); }
    catch (e) { toast.error(errMsg(e)); } finally { setLoading(false); }
  };
  const save = async () => {
    try { await api.post("/skills", { ...skill, steps: skill.steps.filter((s) => s.trim()), events }); toast.success(`Learned "${skill.name}"`); onSaved(); }
    catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <Dialog open={!!events} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-[#12141C] border-[#262B3D] max-w-2xl max-h-[90vh] overflow-y-auto thin-scroll" data-testid="skill-review-dialog">
        <DialogHeader>
          <DialogTitle className="font-display text-xl">{skill ? "Review the new skill" : "Here's what Shadow saw"}</DialogTitle>
          <DialogDescription>{skill ? "Rename it, adjust steps, then save." : `${events?.length || 0} actions captured. Add a hint, then let Shadow turn it into a skill.`}</DialogDescription>
        </DialogHeader>
        {!skill ? (
          <div className="space-y-4">
            <ol className="max-h-64 overflow-y-auto thin-scroll space-y-1 text-xs font-mono text-slate-300 bg-black/30 rounded-lg p-3" data-testid="recorded-events-list">
              {(events || []).map((e, i) => <li key={i}><span className="text-slate-500 mr-2">{i + 1}.</span>{e.desc}</li>)}
              {events?.length === 0 && <li className="text-slate-500">Nothing was captured.</li>}
            </ol>
            <Input value={hint} onChange={(e) => setHint(e.target.value)} placeholder='What is this task? e.g. "Download this month&apos;s bank statement"' className="bg-[#0F111A]" data-testid="skill-hint-input" />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={onClose} data-testid="skill-review-discard">Discard</Button>
              <Button onClick={learn} disabled={loading || !events?.length} data-testid="skill-learn-button">
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Wand2 className="h-4 w-4 mr-2" />}Turn into skill
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <SkillEditor skill={skill} onChange={setSkill} />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={onClose} data-testid="skill-review-cancel">Cancel</Button>
              <Button onClick={save} disabled={!skill.name.trim()} data-testid="skill-save-button">Save skill</Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
