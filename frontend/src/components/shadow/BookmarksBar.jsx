import { useCallback, useEffect, useState } from "react";
import { Globe, Star, X } from "lucide-react";
import { toast } from "sonner";
import { errMsg } from "@/lib/api";

const host = (u) => { try { return new URL(u).hostname; } catch { return ""; } };

export function useBookmarks(api) {
  const [items, setItems] = useState([]);
  const load = useCallback(() => api.get("/bookmarks").then((r) => setItems(r.data)).catch(() => {}), [api]);
  useEffect(() => { load(); }, [load]);
  const add = async (url, title) => { try { await api.post("/bookmarks", { url, title }); load(); toast.success("Bookmarked"); } catch (e) { toast.error(errMsg(e)); } };
  const remove = async (b) => { try { await api.delete(`/bookmarks/${b.id}`); load(); } catch (e) { toast.error(errMsg(e)); } };
  return { items, add, remove };
}

export function StarButton({ bm, url, title }) {
  const found = bm.items.find((b) => b.url === url);
  const web = /^https?:\/\//.test(url || "");
  if (!web) return null;
  return (
    <button type="button" data-testid="bookmark-star-button" title={found ? "Remove bookmark" : "Bookmark this tab"}
      onClick={() => (found ? bm.remove(found) : bm.add(url, title))}
      className="shrink-0 h-6 w-6 rounded-full flex items-center justify-center text-[#5F6368] hover:bg-[#DADCE0]">
      <Star className={`h-4 w-4 ${found ? "fill-[#1A73E8] text-[#1A73E8]" : ""}`} />
    </button>
  );
}

function Mark({ b, onOpen, onRemove }) {
  const [bad, setBad] = useState(false);
  const h = host(b.url);
  return (
    <div className="group/bm shrink-0 flex items-center gap-1.5 h-7 pl-2 pr-1 rounded-full hover:bg-[#F1F3F4] cursor-default max-w-[180px]" title={b.url}
      onClick={() => onOpen(b.url)} data-testid={`bookmark-${b.id}`}>
      {h && !bad ? <img src={`https://www.google.com/s2/favicons?domain=${h}&sz=32`} alt="" onError={() => setBad(true)} className="h-4 w-4 shrink-0" /> : <Globe className="h-3.5 w-3.5 shrink-0 text-[#5F6368]" />}
      <span className="text-xs text-[#3C4043] truncate">{b.title}</span>
      <button onClick={(e) => { e.stopPropagation(); onRemove(b); }} data-testid={`bookmark-remove-${b.id}`} title="Remove"
        className="opacity-0 group-hover/bm:opacity-100 p-0.5 rounded-full text-[#5F6368] hover:bg-[#DADCE0]"><X className="h-3 w-3" /></button>
    </div>
  );
}

export default function BookmarksBar({ bm, onOpen }) {
  return (
    <div className="flex items-center gap-0.5 px-2 h-8 bg-white border-b border-[#DADCE0] overflow-x-auto thin-scroll" data-testid="bookmarks-bar">
      {bm.items.length === 0 ? (
        <p className="text-[11px] text-[#80868B] px-2" data-testid="bookmarks-empty">For quick access, click the star in the address bar to bookmark a page.</p>
      ) : bm.items.map((b) => <Mark key={b.id} b={b} onOpen={onOpen} onRemove={bm.remove} />)}
    </div>
  );
}
