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

=====================
