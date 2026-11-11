import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

export default function WorkspaceDialog({ open, workspace, onClose, onSave }) {
  const [name, setName] = useState("");
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  useEffect(() => { if (open) { setName(workspace?.name || ""); setLabel(workspace?.label || ""); setUrl(""); } }, [open, workspace]);
  const editing = !!workspace;
  const submit = (e) => { e.preventDefault(); onSave({ name: name.trim(), label: label.trim(), url: url.trim() }); };
  const field = "w-full bg-[#F1F3F4] border border-[#DADCE0] rounded-lg px-3 py-2 text-sm outline-none focus:border-[#1A73E8]/50 transition-colors";
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-white border-[#DADCE0] text-[#202124]" data-testid="workspace-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">{editing ? "Edit workspace" : "New workspace"}</DialogTitle>
          <DialogDescription className="text-[#5F6368]">Each workspace has its own website logins, cookies, tabs and task. Signing in to a site here does not sign you in anywhere else.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-xs text-[#5F6368]">Name
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Client A — invoices" maxLength={40} className={`${field} mt-1`} data-testid="workspace-name-input" />
          </label>
          <label className="block text-xs text-[#5F6368]">Client or company
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Acme Corp — Shadow keeps this workspace on this client" maxLength={80} className={`${field} mt-1`} data-testid="workspace-label-input" />
          </label>
          {!editing && (
            <label className="block text-xs text-[#5F6368]">Start page (optional)
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="e.g. example.com" className={`${field} mt-1 font-mono`} data-testid="workspace-url-input" />
            </label>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="text-sm px-4 py-2 rounded-lg border border-[#DADCE0] text-[#3C4043] hover:bg-[#F1F3F4]" data-testid="workspace-cancel-button">Cancel</button>
            <button type="submit" className="text-sm px-4 py-2 rounded-lg bg-[#1A73E8] text-white font-semibold" data-testid="workspace-save-button">{editing ? "Save" : "Open workspace"}</button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
