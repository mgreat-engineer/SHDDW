import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@clerk/react";
import axios from "axios";
import { Apple, ArrowRight, Download, Eye, Layers, Monitor, ShieldCheck, Sparkles } from "lucide-react";
import { API } from "@/lib/api";

const OS_LABEL = { windows: "Windows", mac_arm: "Mac (Apple silicon)", mac_intel: "Mac (Intel)" };

async function detectOs() {
  const ua = navigator.userAgent;
  if (/Windows/i.test(ua)) return "windows";
  if (/Mac/i.test(ua)) {
    try {
      const v = await navigator.userAgentData?.getHighEntropyValues?.(["architecture"]);
      if (v?.architecture === "x86") return "mac_intel";
    } catch {}
    return "mac_arm";
  }
  return null;
}

function DownloadButton({ dl, os, testId }) {
  const href = os && dl?.links?.[os];
  if (!dl) return <div className="h-12 w-64 rounded-full bg-[#F1F3F4] animate-pulse" />;
  if (!dl.available) {
    return (
      <div className="flex flex-col items-start gap-2" data-testid={`${testId}-unavailable`}>
        <span className="inline-flex items-center gap-2 h-12 px-6 rounded-full bg-[#E8EAED] text-[#5F6368] font-medium"><Download className="h-4 w-4" />Download coming soon</span>
        <Link to="/sign-in" className="text-sm text-[#1A73E8] hover:underline">Use Shadow on the web meanwhile</Link>
      </div>
    );
  }
  const target = href || Object.values(dl.links)[0];
  const label = href ? OS_LABEL[os] : null;
  return (
    <a href={target} data-testid={testId}
      className="inline-flex items-center gap-2 h-12 px-7 rounded-full bg-[#1A73E8] text-white font-medium shadow-[0_1px_3px_rgba(26,115,232,0.4)] hover:bg-[#1557B0] transition-colors">
      <Download className="h-4 w-4" />{label ? `Download Shadow for ${label}` : `Download Shadow for ${OS_LABEL[Object.keys(dl.links)[0]]}`}
    </a>
  );
}

function Step({ n, icon: Icon, title, text }) {
  return (
    <div className="fade-up" style={{ animationDelay: `${n * 80}ms` }}>
      <div className="h-10 w-10 rounded-full bg-[#E8F0FE] text-[#1A73E8] flex items-center justify-center"><Icon className="h-5 w-5" /></div>
      <p className="mt-4 text-xs font-medium text-[#80868B]">Step {n}</p>
      <h3 className="mt-1 text-lg font-semibold text-[#202124]">{title}</h3>
      <p className="mt-2 text-sm text-[#5F6368] leading-relaxed">{text}</p>
    </div>
  );
}

function BrowserMock() {
  const tabs = ["Client A · Portal", "Client B · Records", "Grants search"];
  return (
    <div className="rounded-2xl border border-[#DADCE0] bg-white shadow-[0_24px_60px_-20px_rgba(60,64,67,0.35)] overflow-hidden" aria-hidden>
      <div className="flex items-end gap-1 px-3 pt-2 h-10 bg-[#DEE1E6]">
        {tabs.map((t, i) => <div key={t} className={`h-8 px-4 flex items-center rounded-t-lg text-[11px] ${i === 0 ? "bg-white text-[#202124]" : "text-[#5F6368]"}`}>{t}</div>)}
      </div>
      <div className="flex items-center gap-2 px-3 h-10 border-b border-[#DADCE0]">
        <div className="flex-1 h-7 rounded-full bg-[#F1F3F4] px-4 flex items-center text-[11px] text-[#5F6368]">portal.example.com/authorizations</div>
        <span className="text-[10px] font-medium px-2.5 py-1 rounded-full bg-[#E8F0FE] text-[#1A73E8]">Shadow is working</span>
      </div>
      <div className="grid grid-cols-3 gap-3 p-4 bg-[#F8F9FA]">
        {["Working", "Needs you", "Done"].map((s, i) => (
          <div key={s} className="rounded-lg bg-white border border-[#DADCE0] p-3">
            <p className="text-[11px] font-medium text-[#202124]">Workspace {i + 1}</p>
            <p className={`mt-1 text-[10px] ${i === 0 ? "text-[#1A73E8]" : i === 1 ? "text-[#B06000]" : "text-[#1E8E3E]"}`}>{s}</p>
            <div className="mt-3 space-y-1.5"><div className="h-1.5 rounded bg-[#E8EAED]" /><div className="h-1.5 w-2/3 rounded bg-[#E8EAED]" /></div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Landing() {
  const [dl, setDl] = useState(null);
  const [os, setOs] = useState(null);
  useEffect(() => {
    axios.get(`${API}/public/downloads`).then((r) => setDl(r.data)).catch(() => setDl({ available: false, links: {} }));
    detectOs().then(setOs);
  }, []);
  const primary = dl?.available ? (os && dl.links[os] ? os : Object.keys(dl.links)[0]) : null;
  const others = dl?.available ? Object.entries(dl.links).filter(([k]) => k !== primary) : [];
  const { isSignedIn } = useAuth();

  return (
    <div className="min-h-screen bg-white text-[#202124]" data-testid="landing-page">
      <header className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2.5"><div className="h-7 w-7 rounded-full bg-[#1A73E8] flex items-center justify-center"><div className="h-2.5 w-2.5 rounded-full bg-white" /></div><span className="font-semibold tracking-tight">Shadow</span></div>
        <nav className="flex items-center gap-2">
          <Link to={isSignedIn ? "/" : "/sign-in"} className="text-sm px-4 py-2 rounded-full text-[#3C4043] hover:bg-[#F1F3F4]" data-testid="landing-sign-in-link">{isSignedIn ? "Open Shadow" : "Sign in"}</Link>
          <a href="#download" className="text-sm px-4 py-2 rounded-full border border-[#DADCE0] text-[#1A73E8] hover:bg-[#F1F3F4]" data-testid="landing-nav-download">Download</a>
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-6">
        <section className="pt-16 lg:pt-24 pb-20 grid lg:grid-cols-2 gap-14 items-center" id="download">
          <div className="fade-up">
            <p className="inline-flex items-center gap-2 text-xs font-medium text-[#1A73E8] bg-[#E8F0FE] px-3 py-1 rounded-full"><Sparkles className="h-3.5 w-3.5" />AI browser for your desktop</p>
            <h1 className="mt-6 text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight leading-[1.05]">The browser that<br />learns your work.</h1>
            <p className="mt-6 text-base md:text-lg text-[#5F6368] max-w-lg leading-relaxed">Show Shadow a task once. It repeats it for you — in many workspaces at the same time, each with its own tabs and logins, right on your computer.</p>
            <div className="mt-9"><DownloadButton dl={dl} os={os} testId="landing-download-button" /></div>
            {dl?.version && <p className="mt-3 text-xs text-[#80868B]" data-testid="landing-version">Version {dl.version} · Free · Windows 10+ and macOS 12+ · Needs Google Chrome</p>}
            {others.length > 0 && (
              <p className="mt-2 text-xs text-[#5F6368]">Also for: {others.map(([k, href], i) => <span key={k}>{i > 0 && " · "}<a href={href} className="text-[#1A73E8] hover:underline" data-testid={`landing-download-${k}`}>{OS_LABEL[k]}</a></span>)}</p>
            )}
          </div>
          <div className="fade-up" style={{ animationDelay: "120ms" }}><BrowserMock /></div>
        </section>

        <section className="py-16 border-t border-[#DADCE0]" data-testid="landing-how-it-works">
          <h2 className="text-base md:text-lg font-semibold">How it works</h2>
          <div className="mt-10 grid md:grid-cols-3 gap-10">
            <Step n={1} icon={Monitor} title="Download and open" text="Install Shadow, sign in once, and it opens in its own window — websites open in Chrome on your own computer and network." />
            <Step n={2} icon={Eye} title="Show it once" text="Press Watch me and do the task. Shadow learns every step and turns it into a reusable skill." />
            <Step n={3} icon={Layers} title="Let it run" text="Ask in plain words. Shadow works in up to 10 workspaces at once — pause, resume or step in anytime." />
          </div>
        </section>

        <section className="py-16 border-t border-[#DADCE0] grid md:grid-cols-2 gap-10" data-testid="landing-install-help">
          <div>
            <h2 className="text-base md:text-lg font-semibold flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-[#1E8E3E]" />Installing for the first time</h2>
            <p className="mt-2 text-sm text-[#5F6368] leading-relaxed">Shadow is new, so your computer may warn that it comes from an unknown publisher. It's safe to continue:</p>
          </div>
          <div className="grid sm:grid-cols-2 gap-6 text-sm">
            <div className="rounded-xl border border-[#DADCE0] p-5">
              <p className="font-semibold flex items-center gap-2"><Monitor className="h-4 w-4" />Windows</p>
              <ol className="mt-3 list-decimal pl-4 space-y-1.5 text-[#5F6368]"><li>Open the downloaded file</li><li>If blue "Windows protected your PC" appears, click <b>More info</b></li><li>Click <b>Run anyway</b></li></ol>
            </div>
            <div className="rounded-xl border border-[#DADCE0] p-5">
              <p className="font-semibold flex items-center gap-2"><Apple className="h-4 w-4" />Mac</p>
              <ol className="mt-3 list-decimal pl-4 space-y-1.5 text-[#5F6368]"><li>Open the .dmg and drag Shadow Helper to Applications</li><li>Right-click the app and choose <b>Open</b></li><li>If blocked: System Settings → Privacy &amp; Security → <b>Open Anyway</b></li></ol>
            </div>
          </div>
        </section>

        <section className="py-16 border-t border-[#DADCE0] flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div><h2 className="text-base md:text-lg font-semibold">Already installed?</h2><p className="text-sm text-[#5F6368] mt-1">Sign in to see your workspaces, skills and reports.</p></div>
          <Link to={isSignedIn ? "/" : "/sign-in"} className="inline-flex items-center gap-2 text-sm px-5 py-2.5 rounded-full border border-[#DADCE0] text-[#1A73E8] hover:bg-[#F1F3F4]" data-testid="landing-open-app">{isSignedIn ? "Open Shadow" : "Open Shadow on the web"}<ArrowRight className="h-4 w-4" /></Link>
        </section>
      </main>
      <footer className="border-t border-[#DADCE0] py-8 text-center text-xs text-[#80868B]">© {new Date().getFullYear()} Shadow · shddw.com</footer>
    </div>
  );
}
