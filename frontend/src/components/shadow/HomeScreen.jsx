import { useState } from "react";
import { UserButton } from "@clerk/react";
import { Pause, Play } from "lucide-react";
import { PANELS } from "./SideRail";
import SidePanel from "./SidePanel";
import HomeTaskBox from "./HomeTaskBox";
import WorkspaceCards from "./WorkspaceCards";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

function IconMenu({ onPick }) {
  return (
    <TooltipProvider delayDuration={150}>
      <nav className="min-w-0 flex items-center gap-1 overflow-x-auto thin-scroll" data-testid="home-icon-menu">
        {PANELS.map(({ id, label, icon: Icon }) => (
          <Tooltip key={id}>
            <TooltipTrigger asChild>
              <button onClick={() => onPick(id)} data-testid={`home-nav-${id}`} className="h-9 w-9 rounded-full flex items-center justify-center text-[#5F6368] hover:bg-[#F1F3F4] hover:text-[#202124] transition-colors"><Icon className="h-[18px] w-[18px]" /></button>
            </TooltipTrigger>
            <TooltipContent side="bottom">{label}</TooltipContent>
          </Tooltip>
        ))}
      </nav>
    </TooltipProvider>
  );
}

export default function HomeScreen({ finished, groups, max, selected, onSelect, onRun, onOpen, onEdit, onClose, onNew, onPauseAll, onResumeAll, panelProps, banner }) {
  const [panel, setPanel] = useState(null);
  const btn = "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-colors disabled:opacity-40";
  return (
    <div className="h-screen overflow-y-auto thin-scroll bg-[#F8F9FA] text-[#202124]" data-testid="home-screen">
      <header className="flex items-center gap-4 px-6 py-3 border-b border-[#DADCE0] bg-white sticky top-0 z-20">
        <div className="shrink-0 flex items-center gap-2"><span className="h-7 w-7 rounded-full bg-[#1A73E8] flex items-center justify-center"><span className="h-2.5 w-2.5 rounded-full bg-white" /></span><span className="font-display font-semibold tracking-tight">Shadow</span></div>
        <span className="flex-1" />
        <IconMenu onPick={setPanel} />
        <div className="shrink-0" data-testid="user-menu"><UserButton /></div>
      </header>
      <main className="max-w-5xl mx-auto px-6 pt-16 pb-24 flex flex-col gap-14">
        {banner}
        <section className="flex flex-col gap-6 fade-up">
          <h1 className="font-display text-4xl sm:text-5xl font-semibold tracking-tight" data-testid="home-title">What should I do next?</h1>
          <HomeTaskBox groups={groups} selected={selected} onSelect={onSelect} onRun={onRun} />
        </section>
        <section className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <h2 className="text-base md:text-lg font-semibold flex-1">Workspaces</h2>
            <button onClick={onPauseAll} disabled={!groups.some((g) => g.run?.status === "running")} data-testid="pause-all-button" className={`${btn} border-[#B06000]/40 text-[#B06000] hover:bg-[#B06000]/10`}><Pause className="h-3.5 w-3.5" />Pause all</button>
            <button onClick={onResumeAll} disabled={!groups.some((g) => g.run?.status === "paused")} data-testid="resume-all-button" className={`${btn} border-[#DADCE0] text-[#3C4043] hover:bg-[#F1F3F4]`}><Play className="h-3.5 w-3.5" />Resume all</button>
          </div>
          <WorkspaceCards finished={finished} groups={groups} max={max} onOpen={onOpen} onEdit={onEdit} onClose={onClose} onNew={onNew} />
        </section>
      </main>
      <Sheet open={!!panel} onOpenChange={(o) => !o && setPanel(null)}>
        <SheetContent side="left" className="p-0 w-[380px] sm:max-w-[420px] [&>button]:hidden" data-testid="home-panel-sheet">
          <SheetTitle className="sr-only">{PANELS.find((p) => p.id === panel)?.label}</SheetTitle>
          {panel && <SidePanel panel={panel} {...panelProps} onCollapse={() => setPanel(null)}
            onSelectRun={(id) => { setPanel(null); panelProps.onSelectRun(id); }}
            onTemplateOpened={(g, r) => { setPanel(null); panelProps.onTemplateOpened(g, r); }} />}
        </SheetContent>
      </Sheet>
    </div>
  );
}
