# Shadow — a browser that learns how you work and does it for you

An AI-driven Chrome browser that watches you perform a task once, turns what you did into a reusable skill, remembers it, and repeats it on command, by typing or by voice.
It works in its own separate browser, so you keep using your laptop while it runs.

## Who it's for
One person (or a small number of individual users, each with a private workspace) who repeats web tasks every day, such as filling forms, downloading reports, uploading files, or checking dashboards, and wants to hand those tasks off.

## Core features and experience
- **Its own Chrome browser.** A real Chrome browser runs separately from yours. You watch it live in the app, with multiple tabs, and can take over with your mouse and keyboard at any time.
- **"Watch me" learning.** Press Record and do the task yourself in the browser. It captures every click, entry, page, tab switch, upload and download, plus a short note you can add at each step ("pick the latest invoice"). ChatGPT turns the recording into a named skill written in plain steps that you can read and edit.
- **Do it like me.** Ask "do my Monday report" and it runs the skill. ChatGPT looks at each screen and decides what to click, so small changes on a website don't break the task. It also takes new instructions it has never seen ("open three tabs and compare these prices").
- **Handles complete, complex jobs, not just simple ones.** Built from the start for long, multi-stage work:
  - **Plans big goals.** Give it a large goal ("reconcile this month's invoices across the bank portal, the supplier site and my spreadsheet") and it breaks it into a checklist of sub-tasks that you can see. It ticks them off as it works.
  - **Decisions and repetition.** It learns choices ("if the status is overdue, send a reminder; otherwise skip") and repeats over lists ("do this for every row in this spreadsheet / every order on this page"), including hundreds of items.
  - **Works across many sites and tabs.** It carries data between them, such as reading a value on one site, typing it into another, and collecting results into a table or file.
  - **Chains skills.** Skills it already knows can be combined into bigger workflows ("run Download Reports, then Upload to Portal, then Email Summary").
  - **Fixes its own mistakes.** If a page changes, a click fails or an error appears, it rethinks and tries another way. It checks the result of each step before moving on and asks you only when it is truly stuck.
  - **Long runs with checkpoints.** Jobs can run for hours. Progress is saved after each step, so a stopped or failed run resumes where it left off instead of starting over.
  - **Learns from correction.** When you step in and fix something mid-run, it updates the skill so it does it your way next time.
- **Downloads and uploads.** Downloaded files go to the app's file area, where you can save them to your computer. Files you put in that area, or files it downloaded earlier, can be uploaded into websites. It handles the browser's file-picker, "save as", alert and confirm dialogs.
- **Memory.** It remembers facts and preferences you give it ("my company ID is…", "always choose PDF"), every skill it has learned, and the history of every run. Memory can be viewed, edited and deleted.
- **Voice and text commands.** Type in the command bar or hold the mic button and speak. Speech is turned into text and treated like a typed command.
- **Asks before risky actions, unless you say otherwise.** By default it pauses for your OK before paying, sending/submitting, or deleting. You can give standing permission, for example "you can pay and delete without asking", which applies to everything from then on (or only to one skill) until you turn it off on the Permissions page.
- **Live activity log.** Every step shows what it saw, what it decided, and what it did, with a screenshot, so you can check its work.
- **Stays signed in to your sites.** Logins you make in its browser are kept between sessions, so it can reuse them.

## User flow
1. Sign in with email and password. On first use, add your OpenAI key in the secure key prompt.
2. The home screen shows the live browser, a command bar, your skills, and recent runs.
3. Press **Watch me**, do the task, then press **Stop**. Review the generated skill, rename it, adjust steps, and save it.
4. Later, type or say the command. It runs in its own browser while you do other work. You get a notification when it finishes or needs your OK.
5. Approve or reject paused risky steps, or grant standing permission from that prompt.
6. Collect downloaded files from the Files panel.

## UI/UX feel
Calm, focused workspace that looks like a pro tool: the live browser takes up most of the screen, with a slim side panel for skills, memory and files, and a bottom command bar with the mic. Recording mode has a clear red indicator. Approval prompts are clear and hard to miss.

## Implementation phases
**Phase 1 — MVP (built now): web version**
- Email/password sign-in, your own OpenAI key (GPT-5.5)
- Separate Chrome browser with a live view, multiple tabs, and take-over control
- Watch-me recording → editable skills → replay by command
- Free-form commands, using screen understanding to click, type, navigate, upload, download, and handle dialogs
- Complex-task engine: goal → visible checklist, if/then decisions, repeating over lists and spreadsheet rows, data passed between sites and tabs, chained skills, self-correction, step-by-step checks, resumable long runs, learning from your corrections
- Memory, run history with step screenshots, voice commands
- Approval for pay/send/delete, with standing permissions you can revoke

**Phase 2 — Downloadable desktop app (Windows and Mac)**
- The same app packaged as an installable program. It runs its own hidden Chrome on your laptop, separate from yours, so it never takes your mouse or keyboard
- Direct access to folders you choose on your computer for uploads and downloads
- Scheduled skills (e.g. every morning at 8)

**Phase 3 — Beyond the browser**
- Control of other desktop apps (Excel, file explorer, etc.) inside a separate virtual desktop, so it still doesn't interfere with you
- Skills that span the browser and desktop apps (e.g. pull data from a website into Excel, then upload the file)

## Assumptions
- Phase 1 runs on our servers, not on your laptop. It cannot reach files or apps on your computer. Files move through the app's Files panel. Full computer access comes in phases 2–3.
- Full desktop control of other apps while you keep working is the hardest part and isn't fully reliable on any platform yet. It is planned last.
- Complex tasks are handled by planning, checking each step, retrying and resuming, not by guessing in one go. Very complex jobs may sometimes need a second demonstration or one correction from you. After that, it keeps the improved version.
- Very long jobs (hundreds of items) cost more AI usage on your OpenAI account and take longer. The checklist shows progress the whole time.
- CAPTCHAs, bank security checks and 2-step logins on websites will pause the run and ask you to complete them yourself.
- Your OpenAI account pays for all AI use, including voice. Costs depend on how much it runs.
- Each signed-in user has a private workspace. There is no admin or team sharing.
- Standing permissions apply to everything unless you limit them to one skill. You can turn them off at any time.
- Product name "Shadow" is a placeholder and can be changed.
