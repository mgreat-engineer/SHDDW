import re
import sys
from pathlib import Path

PAIRS = [
    ("bg-[#00F0FF] text-black", "bg-[#1A73E8] text-white"),
    ("bg-[#00E676] text-black", "bg-[#1E8E3E] text-white"),
    ("bg-[#FFB000] text-black", "bg-[#F9AB00] text-[#202124]"),
    ("text-black", "text-white"),
    ("#00F0FF", "#1A73E8"),
    ("#00E676", "#1E8E3E"),
    ("#FFB000", "#B06000"),
    ("#FF3B30", "#D93025"),
    ("#ff5247", "#B3261E"),
    ("bg-[#0A0B10]", "bg-[#F8F9FA]"),
    ("bg-[#08090E]", "bg-[#F8F9FA]"),
    ("bg-[#0C0E15]", "bg-[#F8F9FA]"),
    ("bg-[#0F111A]", "bg-[#F1F3F4]"),
    ("bg-[#12141C]", "bg-white"),
    ("bg-[#181B26]", "bg-white"),
    ("#262B3D", "#DADCE0"),
    ("hover:bg-white/5", "hover:bg-[#F1F3F4]"),
    ("hover:bg-white/10", "hover:bg-[#E8EAED]"),
    ("bg-white/5", "bg-[#F1F3F4]"),
    ("bg-white/10", "bg-[#E8EAED]"),
    ("bg-black/60", "bg-[#F8F9FA]"),
    ("bg-black/50", "bg-black/30"),
    ("bg-black/40", "bg-[#F1F3F4]"),
    ("text-slate-100", "text-[#202124]"),
    ("text-slate-200", "text-[#202124]"),
    ("text-slate-300", "text-[#3C4043]"),
    ("text-slate-400", "text-[#5F6368]"),
    ("text-slate-500", "text-[#80868B]"),
    ("text-slate-600", "text-[#9AA0A6]"),
    ("bg-slate-600", "bg-[#BDC1C6]"),
    ("bg-slate-400", "bg-[#80868B]"),
    ("hover:text-slate-100", "hover:text-[#202124]"),
    ("[color-scheme:dark]", "[color-scheme:light]"),
]

for root in sys.argv[1:]:
    for f in Path(root).rglob("*.jsx"):
        if "/ui/" in str(f):
            continue
        s = o = f.read_text()
        for a, b in PAIRS:
            s = s.replace(a, b)
        # bg-[#1A73E8] buttons previously had text-black -> now text-white; text-white on red/green stays
        s = re.sub(r"hover:text-\[#202124\]", "hover:text-[#202124]", s)
        if s != o:
            f.write_text(s)
            print("updated", f)
