import { Eye, Repeat, ShieldCheck } from "lucide-react";

const POINTS = [
  { icon: Eye, t: "Watch me", d: "Do a task once. Shadow learns every click, upload and download." },
  { icon: Repeat, t: "Do it like me", d: "Say the word and it repeats the job in its own Chrome." },
  { icon: ShieldCheck, t: "Asks before risky moves", d: "Payments, sending and deleting wait for your OK." },
];

export default function AuthLayout({ children }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#F8F9FA] grain" data-testid="auth-page">
      <div className="hidden lg:flex flex-col justify-between p-14 grid-bg border-r border-[#DADCE0] relative overflow-hidden">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-[#1A73E8]/10 border border-[#1A73E8]/40 flex items-center justify-center">
            <div className="h-3 w-3 rounded-full bg-[#1A73E8] shadow-[0_0_16px_#1A73E8]" />
          </div>
          <span className="font-display text-xl font-bold tracking-tight">Shadow</span>
        </div>
        <div className="max-w-lg">
          <p className="text-xs font-mono uppercase tracking-widest text-[#1A73E8] mb-5">AI browser · learns your routine</p>
          <h1 className="text-4xl lg:text-5xl font-extrabold tracking-tight leading-[1.05]">
            Show it once.<br /><span className="text-[#5F6368]">It works like you after that.</span>
          </h1>
          <div className="mt-12 space-y-6">
            {POINTS.map(({ icon: Icon, t, d }, i) => (
              <div key={t} className="flex gap-4 fade-up" style={{ animationDelay: `${i * 120}ms` }}>
                <Icon className="h-5 w-5 text-[#1A73E8] mt-0.5 shrink-0" />
                <div><p className="font-semibold">{t}</p><p className="text-sm text-[#5F6368]">{d}</p></div>
              </div>
            ))}
          </div>
        </div>
        <p className="text-xs font-mono text-[#80868B]">Runs in its own Chrome — your mouse and keyboard stay yours.</p>
      </div>
      <div className="flex items-center justify-center p-6">{children}</div>
    </div>
  );
}
