import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, Download, Folder, Globe, MoreHorizontal, Star, X } from "lucide-react";
import { toast } from "sonner";
import { errMsg } from "@/lib/api";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

const host = (u) => { try { return new URL(u).hostname; } catch { return ""; } };
const NEW = "__new__";

export function useBookmarks(api) {
  const [items, setItems] = useState([]);
  const load = useCallback(() => api.get("/bookmarks").then((r) => setItems(r.data)).catch(() => {}), [api]);
  useEffect(() => { load(); }, [load]);
  const folders = useMemo(() => [...new Set(items.map((b) => b.folder).filter(Boolean))].sort((a, b) => a.localeCompare(b)), [items]);
  const add = async (url, title) => { try { const r = await api.post("/bookmarks", { url, title }); await load(); return r.data; } catch (e) { toast.error(errMsg(e)); } };
  const edit = async (b, body) => { try { await api.put(`/bookmarks/${b.id}`, body); load(); } catch (e) { toast.error(errMsg(e)); } };
  const remove = async (b) => { try { await api.delete(`/bookmarks/${b.id}`); load(); } catch (e) { toast.error(errMsg(e)); } };
  const renameFolder = async (old, name) => { try { await api.post("/bookmarks/folders/rename", { old, new: name }); load(); } catch (e) { toast.error(errMsg(e)); } };
  const importChrome = async () => {
    const t = toast.loading("Reading Chrome bookmarks on your laptop…");
    try { const r = await api.post("/bookmarks/import-chrome"); toast.success(`Imported ${r.data.added} new bookmark(s) of ${r.data.found} found`, { id: t }); load(); }
    catch (e) { toast.error(errMsg(e), { id: t }); }
  };
  return { items, folders, add, edit, remove, renameFolder, importChrome };
}

function Fav({ url }) {
  const [bad, setBad] = useState(false);
  const h = host(url);
  return h && !bad ? <img src={`https://www.google.com/s2/favicons?domain=${h}&sz=32`} alt="" onError={() => setBad(true)} className="h-4 w-4 shrink-0" />
    : <Globe className="h-3.5 w-3.5 shrink-0 text-[#5F6368]" />;
}

function Editor({ bm, b, isNew, onClose }) {
  const [title, setTitle] = useState(b.title);
  const [folder, setFolder] = useState(b.folder || "");
  const [fresh, setFresh] = useState("");
  const done = () => {
    if (folder === NEW && !fresh.trim()) return toast.error("Give the new folder a name");
    bm.edit(b, { title, folder: folder === NEW ? fresh : folder }); onClose();
  };
  const field = "w-full mt-1 bg-[#F1F3F4] rounded-md px-3 py-1.5 text-sm outline-none focus:bg-white focus:ring-2 focus:ring-[#1A73E8]";
  return (
    <div className="space-y-3" data-testid="bookmark-editor">
      <p className="text-sm font-semibold text-[#202124]" data-testid="bookmark-editor-title">{isNew ? "Bookmark added" : "Edit bookmark"}</p>
      <label className="block text-xs text-[#5F6368]">Name<input value={title} onChange={(e) => setTitle(e.target.value)} className={field} data-testid="bookmark-name-input" /></label>
      <label className="block text-xs text-[#5F6368]">Folder
        <select value={folder} onChange={(e) => setFolder(e.target.value)} className={field} data-testid="bookmark-folder-select">
          <option value="">Bookmarks bar</option>
          {bm.folders.map((f) => <option key={f} value={f}>{f}</option>)}
          <option value={NEW}>New folder…</option>
        </select>
      </label>
      {folder === NEW && <input autoFocus value={fresh} onChange={(e) => setFresh(e.target.value)} placeholder="Folder name, e.g. a client" className={field} data-testid="bookmark-new-folder-input" />}
      <div className="flex justify-end gap-2">
        <button onClick={() => { bm.remove(b); onClose(); }} className="text-sm px-3 py-1.5 rounded-full border border-[#DADCE0] text-[#1A73E8] hover:bg-[#F1F3F4]" data-testid="bookmark-editor-remove">Remove</button>
        <button onClick={done} className="text-sm px-4 py-1.5 rounded-full bg-[#1A73E8] text-white" data-testid="bookmark-editor-done">Done</button>
      </div>
    </div>
  );
}

export function StarButton({ bm, url, title }) {
  const [open, setOpen] = useState(false);
  const [isNew, setIsNew] = useState(false);
  const found = bm.items.find((b) => b.url === url);
  if (!/^https?:\/\//.test(url || "")) return null;
  const click = async () => { if (!found) { const b = await bm.add(url, title); if (b) { setIsNew(true); setOpen(true); } } else { setIsNew(false); setOpen(true); } };
  return (
    <Popover open={open && !!found} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" data-testid="bookmark-star-button" title={found ? "Edit bookmark" : "Bookmark this tab"} onClick={(e) => { e.preventDefault(); click(); }}
          className="shrink-0 h-6 w-6 rounded-full flex items-center justify-center text-[#5F6368] hover:bg-[#DADCE0]">
          <Star className={`h-4 w-4 ${found ? "fill-[#1A73E8] text-[#1A73E8]" : ""}`} />
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 bg-white">{found && <Editor key={found.id} bm={bm} b={found} isNew={isNew} onClose={() => setOpen(false)} />}</PopoverContent>
    </Popover>
  );
}

function Mark({ b, onOpen, onRemove, wide }) {
  return (
    <div className={`group/bm flex items-center gap-1.5 h-7 pl-2 pr-1 rounded-full hover:bg-[#F1F3F4] cursor-default ${wide ? "w-full rounded-md" : "shrink-0 max-w-[180px]"}`} title={b.url}
      onClick={() => onOpen(b.url)} data-testid={`bookmark-${b.id}`}>
      <Fav url={b.url} />
      <span className="text-xs text-[#3C4043] truncate flex-1">{b.title}</span>
      <button onClick={(e) => { e.stopPropagation(); onRemove(b); }} data-testid={`bookmark-remove-${b.id}`} title="Remove"
        className={`${wide ? "opacity-60" : "opacity-0 [@media(hover:none)]:opacity-100"} group-hover/bm:opacity-100 p-0.5 rounded-full text-[#5F6368] hover:bg-[#DADCE0]`}><X className="h-3 w-3" /></button>
    </div>
  );
}

function FolderChip({ bm, name, items, onOpen }) {
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(null);
  const rename = () => { const n = (renaming || "").trim(); if (n && n !== name) bm.renameFolder(name, n); setRenaming(null); };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button className="shrink-0 flex items-center gap-1.5 h-7 px-2 rounded-full hover:bg-[#F1F3F4] text-xs text-[#3C4043] max-w-[180px]" data-testid={`bookmark-folder-${name}`}>
          <Folder className="h-4 w-4 text-[#5F6368] shrink-0" /><span className="truncate">{name}</span><ChevronDown className="h-3 w-3 text-[#80868B]" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-1 bg-white max-h-[60vh] overflow-y-auto thin-scroll" data-testid={`bookmark-folder-menu-${name}`}>
        {items.map((b) => <Mark key={b.id} b={b} wide onOpen={(u) => { setOpen(false); onOpen(u); }} onRemove={bm.remove} />)}
        {renaming === null ? (
          <button onClick={() => setRenaming(name)} className="w-full text-left text-[11px] text-[#5F6368] px-2 py-1.5 mt-1 border-t border-[#DADCE0] hover:text-[#202124]" data-testid={`bookmark-folder-rename-${name}`}>Rename folder…</button>
        ) : (
          <form onSubmit={(e) => { e.preventDefault(); rename(); }} className="flex gap-1 px-1 pt-2 mt-1 border-t border-[#DADCE0]">
            <input autoFocus value={renaming} onChange={(e) => setRenaming(e.target.value)} maxLength={60} data-testid="bookmark-folder-rename-input"
              className="flex-1 min-w-0 bg-[#F1F3F4] rounded-md px-2 py-1 text-xs outline-none focus:bg-white focus:ring-2 focus:ring-[#1A73E8]" />
            <button type="submit" className="text-xs px-3 rounded-full bg-[#1A73E8] text-white" data-testid="bookmark-folder-rename-save">Save</button>
          </form>
        )}
      </PopoverContent>
    </Popover>
  );
}

export default function BookmarksBar({ bm, onOpen }) {
  const top = bm.items.filter((b) => !b.folder);
  return (
    <div className="flex items-center gap-0.5 px-2 h-8 bg-white border-b border-[#DADCE0]" data-testid="bookmarks-bar">
      <div className="flex-1 min-w-0 flex items-center gap-0.5 overflow-x-auto thin-scroll">
        {bm.folders.map((f) => <FolderChip key={f} bm={bm} name={f} items={bm.items.filter((b) => b.folder === f)} onOpen={onOpen} />)}
        {top.map((b) => <Mark key={b.id} b={b} onOpen={onOpen} onRemove={bm.remove} />)}
        {bm.items.length === 0 && <p className="text-[11px] text-[#80868B] px-2" data-testid="bookmarks-empty">For quick access, click the star in the address bar to bookmark a page.</p>}
      </div>
      <Popover>
        <PopoverTrigger asChild>
          <button className="shrink-0 h-7 w-7 rounded-full flex items-center justify-center text-[#5F6368] hover:bg-[#F1F3F4]" title="Bookmark options" data-testid="bookmarks-menu-button"><MoreHorizontal className="h-4 w-4" /></button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-72 p-1 bg-white">
          <button onClick={bm.importChrome} className="w-full flex items-start gap-3 px-3 py-2 rounded-md hover:bg-[#F1F3F4] text-left" data-testid="bookmarks-import-chrome">
            <Download className="h-4 w-4 mt-0.5 text-[#5F6368]" />
            <span><span className="block text-sm text-[#202124]">Import from Chrome</span><span className="block text-[11px] text-[#5F6368]">Shadow Helper reads the Chrome bookmarks on your laptop (keeps their folders)</span></span>
          </button>
        </PopoverContent>
      </Popover>
    </div>
  );
}
