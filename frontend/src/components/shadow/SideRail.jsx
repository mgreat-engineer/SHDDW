import { UserButton } from "@clerk/react";
import { BarChart3, Brain, CalendarClock, FolderOpen, History, LayoutTemplate, Laptop, ShieldCheck, Sparkles } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export const PANELS = [
  { id: "skills", label: "Skills", icon: Sparkles },
  { id: "templates", label: "Workspace templates", icon: LayoutTemplate },
  { id: "reports", label: "Daily report", icon: BarChart3 },
  { id: "schedules", label: "Schedules", icon: CalendarClock },
  { id: "memory", label: "Memory", icon: Brain },
  { id: "files", label: "Files", icon: FolderOpen },
  { id: "history", label: "Run history", icon: History },
  { id: "permissions", label: "Permissions", icon: ShieldCheck },
  { id: "laptop", label: "Laptop", icon: Laptop },
];

export default function SideRail({ panel, setPanel, open = true }) {
  return (
    <TooltipProvider delayDuration={150}>
      <nav className="w-14 shrink-0 border-r border-[#DADCE0] bg-[#F8F9FA] flex flex-col items-center py-4 gap-2 relative z-10" data-testid="side-rail">
        <div className="h-9 w-9 mb-4 rounded-full bg-[#1A73E8] flex items-center justify-center" title="Shadow">
          <div className="h-3 w-3 rounded-full bg-white" />
        </div>
        {PANELS.map(({ id, label, icon: Icon }) => (
          <Tooltip key={id}>
            <TooltipTrigger asChild>
              <button onClick={() => setPanel(id)} data-testid={`nav-${id}-link`}
                className={`h-10 w-10 rounded-full flex items-center justify-center transition-colors duration-200 ${panel === id && open ? "bg-[#E8F0FE] text-[#1A73E8]" : "text-[#5F6368] hover:text-[#202124] hover:bg-[#E8EAED]"}`}>
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
