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

## Backlog
- P1: Phase 2 remainder: scheduled skills; code-signing (Windows certificate, Apple notarization) for installers without warnings; helper auto-update
- P1: Move files to object storage for multi-instance production
- P2: Phase 3 virtual-desktop control of other apps; richer iframe support; parallel runs per user
