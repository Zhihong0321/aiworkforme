DATE  : Mar 16, 2026
REPO NAME : AIworkforMe

- Added and validated a WhatsApp voice-note debug script that generates TTS, converts it to WhatsApp format, uploads it publicly, and verifies Baileys delivery.
- Integrated the working WhatsApp voice-note send path into the shared messaging runtime so audio sends use UniAPI TTS generation, OGG/Opus conversion, public upload, and verified Baileys delivery.
- Delivered WhatsApp sales-material attachments with per-agent upload management and duplicate-send tracking.
- Added a toggleable built-in Voice Note Follow-Up skill that seeds as an MCP option, enables live agent voice-note decisions in the conversation runtime, enqueues WhatsApp audio replies with 15-second guardrails, and fixes multi-skill toggling in the agent UI.
- Fixed agent-scoped CRM AI routes and delivered dormant-lead follow-up logic with verified backend tests and frontend build.
- Patched messaging helper facade to restore WhatsApp channel identity imports and verified router startup/tests.
- Patched messaging helper facade to restore WhatsApp provider session identifier export and verified startup imports.
- Delivered one-page agent management UI with stable selector dropdown and CRUD flow.
- Shipped backend sales-material upload APIs and public file serving for agent management.
- Added file-or-URL sales materials with YouTube link support and verified backend/frontend checks.
- Fixed backend deploy crash from Voice Note Follow-Up seeding import mismatch.
- Raised agent sales-material upload limit to 30 MB with backend/frontend validation and regression coverage.
- Restructured agent UX into per-agent dashboards with WhatsApp routing and agent-scoped contacts, knowledge, and inbox flows
- Clarified channel setup UI with explicit Add New Channel actions and verified frontend build
- Added Start Working and On Hold controls to agent dashboard contacts and verified frontend build
- Fixed per-agent WhatsApp routing so manual starts and AI CRM follow-ups use the assigned channel, with backend regression tests and frontend build
- Fixed customer-reply auto-response regressions by hardening inbound runtime compatibility and AI CRM state recovery, then validated with targeted tests.
- Fixed agent deletion by cleaning up dependent CRM, workspace, lead, thread, and MCP link records before removing the agent, then validated with router regression tests.

=====================
