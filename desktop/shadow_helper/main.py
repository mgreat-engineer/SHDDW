"""Shadow Helper window (tkinter). Runs the helper's asyncio loop in a background thread."""
import asyncio
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core import VERSION, Config, Helper, app_dir, copy_chrome_logins, pair

BG, FG, MUTED, ACCENT = "#0F111A", "#F1F5F9", "#94A3B8", "#00F0FF"


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = Config()
        self.loop = asyncio.new_event_loop()
        self.helper = Helper(self.cfg, on_status=lambda s: root.after(0, self.status.set, s))
        root.title(f"Shadow Helper {VERSION}")
        root.configure(bg=BG)
        root.geometry("520x560")
        self.status = tk.StringVar(value="Starting…")
        self.build()
        threading.Thread(target=self._run_loop, daemon=True).start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.helper.run())

    def submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def label(self, parent, text, size=10, color=FG, bold=False):
        return tk.Label(parent, text=text, bg=BG, fg=color, font=("Helvetica", size, "bold" if bold else "normal"), anchor="w", justify="left")

    def build(self):
        pad = {"padx": 18, "sticky": "we"}
        self.label(self.root, "Shadow Helper", 16, ACCENT, True).grid(row=0, pady=(16, 0), **pad)
        self.label(self.root, "Lets Shadow use a hidden Chrome and the folders you pick on this computer.", 9, MUTED).grid(row=1, **pad)
        tk.Label(self.root, textvariable=self.status, bg="#181B26", fg=FG, anchor="w", padx=10, pady=8, wraplength=460, justify="left").grid(row=2, pady=12, **pad)

        link = tk.Frame(self.root, bg=BG)
        link.grid(row=3, **pad)
        self.label(link, "1. Connection code (from Shadow → Laptop panel)", 10, FG, True).pack(fill="x")
        row = tk.Frame(link, bg=BG)
        row.pack(fill="x", pady=4)
        self.code = tk.Entry(row)
        self.code.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Link", command=self.do_pair).pack(side="left", padx=4)
        ttk.Button(row, text="Unlink", command=self.do_unlink).pack(side="left")

        fr = tk.Frame(self.root, bg=BG)
        fr.grid(row=4, pady=(12, 0), **pad)
        self.label(fr, "2. Folders Shadow may use (nothing else is visible to it)", 10, FG, True).pack(fill="x")
        self.folders = tk.Listbox(fr, height=5, bg="#181B26", fg=FG, highlightthickness=0, selectbackground="#00434A")
        self.folders.pack(fill="x", pady=4)
        btns = tk.Frame(fr, bg=BG)
        btns.pack(fill="x")
        ttk.Button(btns, text="Add folder…", command=self.add_folder).pack(side="left")
        ttk.Button(btns, text="Remove", command=self.remove_folder).pack(side="left", padx=4)
        ttk.Button(btns, text="Save downloads here", command=self.set_downloads).pack(side="left")
        self.dl = tk.StringVar()
        self.label(fr, "", 9, MUTED).pack(fill="x")
        tk.Label(fr, textvariable=self.dl, bg=BG, fg=MUTED, anchor="w", font=("Helvetica", 9)).pack(fill="x")

        ch = tk.Frame(self.root, bg=BG)
        ch.grid(row=5, pady=(12, 0), **pad)
        self.label(ch, "3. Chrome logins", 10, FG, True).pack(fill="x")
        self.use_logins = tk.BooleanVar(value=bool(self.cfg["use_chrome_logins"]))
        tk.Checkbutton(ch, text="Use my Chrome logins in Shadow's hidden Chrome", variable=self.use_logins, command=self.toggle_logins,
                       bg=BG, fg=FG, selectcolor="#181B26", activebackground=BG, activeforeground=FG).pack(anchor="w")
        ttk.Button(ch, text="Copy my Chrome logins now", command=self.do_copy).pack(anchor="w", pady=4)
        self.label(ch, "Close Google Chrome first so every login can be copied.", 9, MUTED).pack(fill="x")
        self.refresh_folders()

    def refresh_folders(self):
        self.folders.delete(0, "end")
        for f in self.cfg["folders"] or []:
            self.folders.insert("end", f)
        self.dl.set(f"Downloads go to: {self.cfg['downloads_folder'] or '(first folder)'}")
        self.submit(self.helper.send_hello())

    def add_folder(self):
        d = filedialog.askdirectory(title="Choose a folder Shadow may use")
        if d and d not in (self.cfg["folders"] or []):
            self.cfg["folders"] = (self.cfg["folders"] or []) + [d]
            if not self.cfg["downloads_folder"]:
                self.cfg["downloads_folder"] = d
            self.refresh_folders()

    def remove_folder(self):
        sel = self.folders.curselection()
        if not sel:
            return
        f = self.folders.get(sel[0])
        self.cfg["folders"] = [x for x in self.cfg["folders"] if x != f]
        if self.cfg["downloads_folder"] == f:
            self.cfg["downloads_folder"] = (self.cfg["folders"] or [""])[0]
        self.refresh_folders()

    def set_downloads(self):
        sel = self.folders.curselection()
        if sel:
            self.cfg["downloads_folder"] = self.folders.get(sel[0])
            self.refresh_folders()

    def do_pair(self):
        code = self.code.get().strip()
        if not code:
            return
        try:
            res = pair(self.cfg, code)
            self.code.delete(0, "end")
            messagebox.showinfo("Shadow Helper", f"Linked as \"{res['name']}\".")
        except Exception as e:
            messagebox.showerror("Shadow Helper", f"Could not link: {e}")

    def do_unlink(self):
        self.cfg["token"] = ""
        self.submit(self._close_ws())

    async def _close_ws(self):
        if self.helper.ws:
            await self.helper.ws.close()

    def toggle_logins(self):
        self.cfg["use_chrome_logins"] = bool(self.use_logins.get())
        self.submit(self.helper.restart_browser())

    def do_copy(self):
        async def job():
            await self.helper.restart_browser()
            res = copy_chrome_logins(app_dir() / "chrome-profile")
            await self.helper.ensure_browser()
            await self.helper.send_hello()
            return res
        try:
            res = self.submit(job()).result(timeout=180)
            msg = f"Copied logins from Chrome profile \"{res['profile']}\"."
            if res["skipped"]:
                msg += f"\n{len(res['skipped'])} files were in use (close Chrome and copy again to include them)."
            messagebox.showinfo("Shadow Helper", msg)
        except Exception as e:
            messagebox.showerror("Shadow Helper", f"Could not copy logins: {e}")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
