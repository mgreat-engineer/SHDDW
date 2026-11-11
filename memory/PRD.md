# Shadow — AI browser that learns how you work

## Original problem statement
Build a standalone browser like Polar browser with a mind of its own. It learns the user's process by watching how they do things. It opens websites, handles multiple tabs, downloads, uploads and dialog boxes, and acts like the user. "Watch me do this": it learns everything, no matter how complex, and handles it like the user would. Production grade for automating all tasks. Built on Chrome, with the AI built on ChatGPT. It clicks, downloads, uploads, thinks, listens to commands and has its own memory.

## Architecture (Phase 1, web)
- Backend FastAPI: `server.py` (routes), `shadow_browser.py` (Playwright persistent headless Chrome per user, profile at /app/shadow_data/profiles, recorder init-script, dialogs/filechooser/downloads), `shadow_agent.py` (GPT-5.5 tool-calling step loop with screenshot and numbered elements, plan checklist, saved data, skills chaining, risk gating, checkpoints in Mongo, correction learning). Uses emergentintegrations LlmChat with the user's OPENAI_API_KEY and OpenAI Whisper for voice.
- Auth: Emergent-managed Clerk, email/password. Each user gets a private workspace.
- Frontend React: Workspace (rail, side panels for Skills/Memory/Files/History/Permissions, live browser view with tabs/URL bar/take-over, command bar with Watch me and hold-to-talk mic, activity panel, approval modal, skill review dialog).
- Storage: Mongo collections skills, runs, run_steps, memories, permissions, files. Files and step screenshots are on local disk at /app/shadow_data.

## Implemented (2026-06)
- Live remote Chrome with multiple tabs, navigation, click, keyboard and scroll take-over, page dialogs bar, file chooser modal
- Watch-me recording with notes → GPT skill synthesis → editable skills
- Commands (text and voice) → autonomous agent: plan, self-correction, read_page/read_file/write_file (csv/xlsx), save_data, run_skill chaining, remember, ask_user
- Approvals for pay/send/delete, standing permissions (global or per skill), refused risks blocked for the rest of the run
- Pause/take over → corrections learned into the skill on finish. Resume from checkpoint, including after a restart
- Memory CRUD, Files (upload/download, browser downloads), run history with step screenshots, notifications
- Tested: iteration_1 and iteration_2 all pass

## Desktop app — Laptop helper (2026-06)
- User choices: helper linked to account; installers auto-built from GitHub; only picked folders; copy normal Chrome logins
- /app/desktop/shadow_helper (core.py + tkinter main.py) reuses backend/shadow_browser.py. It runs installed Google Chrome hidden (channel=chrome) with its own profile, LocalFolders (allowed folders only, traversal blocked) and an optional copy of the last-used Chrome profile
- Pairing: web Laptop panel → one-time connection code (base64url {u,c}, 15 min) → /api/helper/pair → device token (stored hashed) → WebSocket /api/helper/ws (Bearer header) with JSON RPC
- Backend: shadow_hub.py (HelperConn/RemoteSession), per-user target cloud|laptop (/api/target), devices list/unlink, runs pinned to a target, laptop offline → run paused, Resume continues
- Build: .github/workflows/desktop-build.yml (PyInstaller; Inno Setup .exe; .dmg for Apple Silicon and Intel; GitHub Release). Unsigned
- Tested: iteration_3 (13/13 backend, UI flows) + fixes

## Auto-update + signing-ready builds (2026-06)
- User choices: keep Mac and Windows unsigned for now; public GitHub repo; auto-install when idle
- updater.py: checks GitHub Releases latest every 6 hours (or with Check for updates), compares 1.0.<build>, downloads the installer for this OS/CPU, verifies it against checksums.txt, installs after 10 min of no task activity (Windows silent Inno install + relaunch; Mac swaps the .app bundle and relaunches)
- Workflow: version 1.0.<run_number>, build_info.json baked in, tag helper-v<version>, make_latest, checksums.txt. Signing/notarization steps run only when GitHub secrets exist (MACOS_CERT_P12…, WIN_CERT_PFX…; see desktop/README.md)
- Tested offline: tests/test_updater.py (version compare, checksum pass/fail, idle gating). The real GitHub build has not run yet

## Update banner, Skill preview, Results table, Schedules (2026-06)
- Update banner: helper_ws records upgrades only (last_update + update_history). Banner in Workspace (dismissible, localStorage). Laptop panel shows version and history
- Preview (user choice: only look and plan): run mode 'preview'. Click/type/keys/upload/dialog/files/memory/tables/ask_user are simulated as "Would …" steps with a red element highlight in the screenshot. Step-by-step viewer and a "Run it for real" button
- Results table: add_rows tool → run.tables (≤10 tables, 5000 rows, 8 MB). Live mini table + full dialog. GET /api/runs/{id}/export → xlsx (formula-escaped)
- Schedules (user choice: laptop offline → cloud): /api/schedules CRUD (days 0=Sun, quarter-hour time, IANA tz). .emergent/crons.yml calls POST /api/cron/schedules every 15 min (WEBHOOK_CRON_SECRET), atomically claims due slots and starts runs (trigger 'schedule'). Schedules panel + skill-card button
- Tested: iteration_4 (backend 100% after the delete fix, UI flows) + minor fixes

## Window groups (2026-06)
- User choices: groups share logins; tasks run in parallel; up to 10 groups; switcher + grid overview; pop out a group into its own window for another screen
- shadow_browser.py: BrowserSession = one Chrome context per user (shared cookies) holding Group objects (own tabs, dialogs, file chooser, recording, corrections, events). Popups stay in the opening group; random 8-hex group ids; "1" = Main (cannot close)
- API: every browser/record/run endpoint takes ?group= (default 1). /api/browser/groups GET/POST/PUT/DELETE. Runs store group_id; one active run per group, many in parallel. Resume recreates a closed group. Scheduled runs open a new group if Main is busy. Laptop helper supports groups (RemoteSession.group, helper GROUP_ADMIN)
- UI: GroupBar (chips with status dots, rename by double-click, pop-out, close, New group n/10), GroupGrid live tiles, solo page /?group=<id>&solo=1, per-group last run memory, toasts for background groups
- Group list is in memory (restart leaves only Main)
- Prod check: deployer saw no 500s after the Chromium auto-install redeploy; user should sign in on the live site to confirm
- Tested: iteration_5 + iteration_6 (all fixes verified)

## Isolated, persistent workspaces (2026-06)
- User choices: name stays "Shadow"; one Shadow login, but each workspace has its OWN website logins/cookies/history; after a restart workspaces and tabs reopen and tasks wait for Resume; client/company label per workspace; Pause all / Resume all
- Main workspace = persistent profile; other workspaces = separate browser contexts in a second Chromium, logins saved to <profile>-ws/<id>.json (storage_state incl. IndexedDB)
- Mongo `workspaces` {user_id, target, groups:[{id,name,label,urls,active}]}: saved every 10s, on create/edit/close/navigate/tabs, before idle reaping; restored on first access after restart. Laptop helper: restored when it reconnects
- Agent prompt gets "WORKSPACE: name for client label" so it stays on that client
- API: POST/PUT /api/browser/groups take label; POST /api/runs/pause-all, /api/runs/resume-all
- UI: WorkspaceDialog (name, client, start page), chip/tile labels, edit pencil, Pause all / Resume all
- Tested: iteration_7 (all pass, incl. real restart)

## Workspace templates + Daily report (2026-06)
- User choices: templates keep only sites + client label (no logins, fresh workspace each time); optional skill (+ instructions) starts when opened; report = task list and counts per client, in app only
- API: /api/templates CRUD, POST /api/templates/from-workspace, POST /api/templates/{id}/open → {group, run, run_error}; GET /api/reports/daily?date&tz (buckets completed/needs_you/running/failed/stopped, grouped by workspace_label)
- Runs store workspace_name/workspace_label; skill+command goals are combined; a stopped run is no longer overwritten as failed by a late engine error
- UI: Templates panel + TemplateDialog, Daily report panel (date picker, totals, per-client cards, click a task to open it)
- Tested: iteration_8 (11/11 backend, all UI flows) + minor fixes

## Light Chrome UI + live stream + adjustable layout (2026-06)
- User choices: whole app white Chrome-style; live video-like stream; always plain arrow cursor; left/right panels resizable + collapsible, workspace bar hideable (full screen)
- Backend: WS /api/browser/stream?token=&group= (Clerk token; 4401/4400 close codes) streams Chrome screencast JPEG frames (~50-60 fps on animated pages), takes input (click/dblclick/type/key/scroll/move) and {type:resize}; Group.set_viewport makes the remote page fill the browser area; laptop target falls back to picture polling
- Frontend: useLiveView hook, Chrome-replica BrowserView (grey tab strip, favicons, rounded omnibox, lock icon, live dot, panel toggles), react-resizable-panels layout (sizes remembered), light palette across all panels/dialogs/Clerk; Calendar date picker + shadcn Select
- shddw.com "unsupported protocol": Emergent side OK (SSL active); user must fix DNS (remove AAAA/extra records, Cloudflare grey cloud) / wait for propagation
- Tested: iteration_9 + iteration_10 (all fixes verified), stale first frame fixed after

## Bookmarks, copy from page, saved passwords, anti-bot fix (2026-06)
- Bookmarks (shared across workspaces): /api/bookmarks; star in omnibox + bookmarks bar
- Copy: real mouse down/move/up over the stream (drag-select, click counts), Ctrl+C + right-click menu (Copy/Paste/Select all/Reload); selection fetched over the same WS so it includes the latest drag
- Passwords (same in every workspace): CRED_JS captures logins; bubble "Save password?" only after a successful login (failed login same-URL reload discards it, 90s expiry); Fernet-encrypted in Mongo `passwords` (VAULT_KEY in backend/.env); key icon fills; agent tool sign_in fills without the AI seeing the password; Passwords side panel (list/search/delete)
- "Unusual traffic" fix: normal Chrome UA + client hints via CDP override (no HeadlessChrome), webdriver hidden, Accept-Language clean; Google /sorry/ page auto-redirects the search to Bing. Server IPs can still be flagged by Google; laptop helper uses the user's own network
- Input latency cut from ~0.33s to ~0.09s (run_guarded)
- Tested: iteration_11, 12, 13 (all pass)

## Backlog
- P1: Phase 2 remainder: buy signing certificates (Apple Developer ID $99/yr; Windows certificate or Azure Trusted Signing) and add them as GitHub secrets; email/push alert when a scheduled run waits for approval
- P1: Move files to object storage for multi-instance production
- P2: Phase 3 virtual-desktop control of other apps; richer iframe support; per-workspace Files folders
