DATE  : Mar 19, 2026
REPO NAME : AIworkforMe

- Built and validated a UniAPI Gemini self-play conversation skill test harness with customer simulation and A/B transcript comparison output.
- Updated UniAPI Gemini defaults and validation to use gemini-3.1-flash-lite-preview and removed old gemini-3-flash naming.
- Integrated a default human conversation skill layer across live agent runtimes with reusable skill files, debug trace, tests, and self-play harness alignment.
- Shipped missing agent tooling runtime module to fix production startup import error
- Shipped lead deletion reset flow that removes a lead and its chat memory with regression coverage
- Shipped Leads UI delete button for zero-reset lead cleanup
- Shipped lead delete action on the agent dashboard contacts tab
- Fixed lead deletion 500 by deleting AI CRM thread state before unified threads and added FK-enforced regression coverage
- Fixed live inbound WhatsApp trigger and patched unified messaging schema SQL to restore AI replies
- Built an internal prompt optimizer for agents with feedback intake, thread analysis, and a reviewed prompt rewrite flow, then verified it with tests and a frontend build.
- Moved the new prompt optimizer into the live agent dashboard with an accessible Optimizer tab and direct launch from System Instructions, then verified the frontend build.
- Added non-blocking storage health checks for persistent sales-material storage
- Fixed sales-material storage startup crash by removing import-time directory creation
- Fixed AI CRM thread-state workspace repair to stop null workspace deploy failures
- Added frontend API timeout guard to prevent deployed pages from hanging on stalled backend requests
- Improved optimizer UX to use Inbox threads directly with one-click thread selection
- Reworked sales material handling so uploads save public URLs, WhatsApp sends URL-only materials, and agent saves no longer hang on refresh.

=====================
