import { Plus, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export default function SkillEditor({ skill, onChange }) {
  const set = (k, v) => onChange({ ...skill, [k]: v });
  const setStep = (i, v) => set("steps", skill.steps.map((s, j) => (j === i ? v : s)));
  return (
    <div className="space-y-4">
      <div>
        <label className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">Name</label>
        <Input value={skill.name} onChange={(e) => set("name", e.target.value)} className="mt-1 bg-[#F1F3F4]" data-testid="skill-name-input" />
      </div>
      <div>
        <label className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">When to use it</label>
        <Textarea value={skill.description} onChange={(e) => set("description", e.target.value)} rows={2} className="mt-1 bg-[#F1F3F4]" data-testid="skill-description-input" />
      </div>
      <div>
        <label className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">Steps</label>
        <div className="mt-1 space-y-2 max-h-72 overflow-y-auto thin-scroll pr-1">
          {skill.steps.map((s, i) => (
            <div key={i} className="flex gap-2 items-start">
              <span className="text-xs font-mono text-[#1A73E8] mt-2.5 w-5 text-right">{i + 1}</span>
              <Textarea value={s} onChange={(e) => setStep(i, e.target.value)} rows={1} className="bg-[#F1F3F4] min-h-[38px] text-sm" data-testid={`skill-step-input-${i}`} />
              <button onClick={() => set("steps", skill.steps.filter((_, j) => j !== i))} className="mt-2 text-[#80868B] hover:text-[#D93025]" data-testid={`skill-step-delete-${i}`}><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </div>
        <button onClick={() => set("steps", [...skill.steps, ""])} className="mt-2 text-xs text-[#1A73E8] flex items-center gap-1" data-testid="skill-add-step-button"><Plus className="h-3.5 w-3.5" />Add step</button>
      </div>
      {skill.parameters?.length > 0 && (
        <div>
          <label className="text-[10px] font-mono uppercase tracking-widest text-[#80868B]">Things that can change each time</label>
          <div className="mt-1 flex flex-wrap gap-2">
            {skill.parameters.map((p, i) => <span key={i} className="text-xs px-2 py-1 rounded border border-[#DADCE0] bg-[#F1F3F4]" title={p.description}>{p.name}{p.example ? ` · e.g. ${p.example}` : ""}</span>)}
          </div>
        </div>
      )}
    </div>
  );
}
