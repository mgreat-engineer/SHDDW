import { Eye, Repeat, ShieldCheck } from "lucide-react";

const POINTS = [
  { icon: Eye, t: "Watch me", d: "Do a task once. Shadow learns every click, upload and download." },
  { icon: Repeat, t: "Do it like me", d: "Say the word and it repeats the job in its own Chrome." },
  { icon: ShieldCheck, t: "Asks before risky moves", d: "Payments, sending and deleting wait for your OK." },
];

export default function AuthLayout({ children }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#08090E] grain" data-testid="auth-page">
      <div className="hidden lg:flex flex-col justify-between p-14 grid-bg border-r border-[#262B3D] relative overflow-hidden">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-[#00F0FF]/10 border border-[#00F0FF]/40 flex items-center justify-center">
            <div className="h-3 w-3 rounded-full bg-[#00F0FF] shadow-[0_0_16px_#00F0FF]" />
          </div>
          <span className="font-display text-xl font-bold tracking-tight">Shadow</span>
        </div>
        <div className="max-w-lg">
          <p className="text-xs font-mono uppercase tracking-widest text-[#00F0FF] mb-5">AI browser · learns your routine</p>
          <h1 className="text-4xl lg:text-5xl font-extrabold tracking-tight leading-[1.05]">
            Show it once.<br /><span className="text-slate-400">It works like you after that.</span>
          </h1>
          <div className="mt-12 space-y-6">
            {POINTS.map(({ icon: Icon, t, d }, i) => (
              <div key={t} className="flex gap-4 fade-up" style={{ animationDelay: `${i * 120}ms` }}>
                <Icon className="h-5 w-5 text-[#00F0FF] mt-0.5 shrink-0" />
                <div><p className="font-semibold">{t}</p><p className="text-sm text-slate-400">{d}</p></div>
              </div>
            ))}
          </div>
        </div>
        <p className="text-xs font-mono text-slate-500">Runs in its own Chrome — your mouse and keyboard stay yours.</p>
      </div>
      <div className="flex items-center justify-center p-6">{children}</div>
    </div>
  );
}
