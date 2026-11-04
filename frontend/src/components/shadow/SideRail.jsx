import { UserButton } from "@clerk/react";
import { Brain, FolderOpen, History, Laptop, ShieldCheck, Sparkles } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export const PANELS = [
  { id: "skills", label: "Skills", icon: Sparkles },
  { id: "memory", label: "Memory", icon: Brain },
  { id: "files", label: "Files", icon: FolderOpen },
  { id: "history", label: "Run history", icon: History },
  { id: "permissions", label: "Permissions", icon: ShieldCheck },
  { id: "laptop", label: "Laptop", icon: Laptop },
];

export default function SideRail({ panel, setPanel }) {
  return (
    <TooltipProvider delayDuration={150}>
      <nav className="w-14 shrink-0 border-r border-[#262B3D] bg-[#0C0E15] flex flex-col items-center py-4 gap-2 relative z-10" data-testid="side-rail">
        <div className="h-9 w-9 mb-4 rounded-lg bg-[#00F0FF]/10 border border-[#00F0FF]/40 flex items-center justify-center" title="Shadow">
          <div className="h-2.5 w-2.5 rounded-full bg-[#00F0FF] shadow-[0_0_14px_#00F0FF]" />
        </div>
        {PANELS.map(({ id, label, icon: Icon }) => (
          <Tooltip key={id}>
            <TooltipTrigger asChild>
              <button onClick={() => setPanel(id)} data-testid={`nav-${id}-link`}
                className={`h-10 w-10 rounded-lg flex items-center justify-center transition-colors duration-200 ${panel === id ? "bg-[#00F0FF]/15 text-[#00F0FF]" : "text-slate-500 hover:text-slate-200 hover:bg-white/5"}`}>
                <Icon className="h-[18px] w-[18px]" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
          </Tooltip>
        ))}
        <div className="mt-auto" data-testid="user-menu"><UserButton /></div>
      </nav>
    </TooltipProvider>
  );
}
