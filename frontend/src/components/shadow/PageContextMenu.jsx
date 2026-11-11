import { useEffect } from "react";
import { ClipboardPaste, Copy, RotateCw, TextSelect } from "lucide-react";

export default function PageContextMenu({ menu, onClose, onCopy, onPaste, onSelectAll, onReload }) {
  useEffect(() => {
    if (!menu) return;
    const close = () => onClose();
    window.addEventListener("click", close);
    window.addEventListener("blur", close);
    return () => { window.removeEventListener("click", close); window.removeEventListener("blur", close); };
  }, [menu, onClose]);
  if (!menu) return null;
  const items = [
    ["copy", "Copy", "Ctrl+C", Copy, onCopy],
    ["paste", "Paste", "Ctrl+V", ClipboardPaste, onPaste],
    ["select-all", "Select all", "Ctrl+A", TextSelect, onSelectAll],
    ["reload", "Reload", "", RotateCw, onReload],
  ];
  return (
    <div className="fixed z-50 w-52 py-1 rounded-md bg-white border border-[#DADCE0] shadow-[0_4px_16px_rgba(60,64,67,0.25)]"
      style={{ left: Math.min(menu.x, window.innerWidth - 220), top: Math.min(menu.y, window.innerHeight - 170) }} data-testid="page-context-menu">
      {items.map(([id, label, kb, Icon, fn]) => (
        <button key={id} onClick={(e) => { e.stopPropagation(); onClose(); fn(); }} data-testid={`page-menu-${id}`}
          className="w-full flex items-center gap-3 px-3 py-1.5 text-sm text-[#202124] hover:bg-[#F1F3F4]">
          <Icon className="h-4 w-4 text-[#5F6368]" /><span className="flex-1 text-left">{label}</span><span className="text-[11px] text-[#80868B]">{kb}</span>
        </button>
      ))}
    </div>
  );
}
