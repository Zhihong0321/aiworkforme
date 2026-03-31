# Aiworkfor.me - V2 UI/UX Redesign System Prompt
**Target**: Google Stitch (or any generative UI creation tool)

## 1. Project Context & Audience
**Product Objective:** Aiworkfor.me is a B2B SaaS platform that enables Small and Medium Business (SMB) operators to launch autonomous AI agents. These agents conduct persistent WhatsApp outreach, engaging leads to schedule appointments or close sales. 
**The Vibe (UX Goal):** "Operator Control Plane." The user should feel like a manager overseeing highly capable digital employees. The UI must be highly trustworthy, heavily data-driven but not visually overwhelming. It needs to reflect "Cost-first" and "Intent-first" principles—meaning the operator should always know *what* the AI is doing, *why* it's doing it, and *how much it costs*.

*Note to Google Stitch: You are fully empowered to decide the typography, micro-interactions, layout paradigms (e.g., sidebars vs. top nav), and overall aesthetic. Focus on making it look stunning, premium, modern, and highly functional. The instructions below dictate structural UX, purpose, and necessary components.*

**MANDATORY DESIGN PREFERENCES:**
1. **Theming & Vibe:** Dark Mode is mandatory. The color palette should heavily feature deep, dark backgrounds with vibrant purple gradients for primary actions and accents.
2. **Navigation & Usability:** User-friendliness is the #1 priority. Navigation must be highly intuitive, with easy ways to jump between agents.
3. **Data Density:** Medium-to-low density. Prefer card-based layouts, prominent avatars, and comfortable whitespace over cramped, financial-terminal style spreadsheet tables.
4. **Empty States:** No complex onboarding tutorials for now. If a view is empty (e.g., the Tenant Home has no agents), simply show a clean, welcoming empty state with a clear "Create New Agent" or equivalent button.

---

## 2. Core UX Principles to Follow
1. **Safety & Trust Floor:** Whenever the AI takes an action (or is blocked from taking one), the UI must surface the "Reasoning." Use prominent badging for policy alerts (e.g., "Send Blocked: Quiet Hours").
2. **Action-Oriented:** Operators shouldn't just stare at data; they should be prompted to intervene only when necessary (e.g., "Strategy Review Required" queues).
3. **Minimal Fatigue:** Consolidate settings so the operator isn't jumping between 10 tiny pages to configure one agent.
4. **Agent Persona Identity:** When configuring an agent, the UI should feel like you are building a "teammate."

---

## 3. Global Navigation & Page Hierarchy

### 3.1. Authentication
**Page:** `Login / Registration`
*   **Purpose:** Secure entry for Tenant Operators.
*   **Key Elements:** Email/Password gating, OAuth (Google/Microsoft), "Forgot Password". 
*   **UX Note:** Clean, professional, minimal friction.

### 3.2. Global Tenant Dashboard
**Page:** `Tenant Home (Agent List)`
*   **Purpose:** The 30,000-foot view of the user's entire workforce (all active AI agents).
*   **Key Elements:**
    *   **Agent Cards/Table:** A list of active agents displaying their name, assigned channel (e.g., WhatsApp number), current status (Active, Paused, Error), and high-level stats (e.g., 24h Messages Sent, Active Leads).
    *   **Quick Action:** "Create New Agent" button.
    *   **Global Overview:** High-level metrics (Total cost this month, Total qualified appointments).

### 3.3. **The Agent Dashboard** (Core Workspace)
*When a user clicks on an Agent from the Tenant Home, they enter this dedicated Agent Workspace. It should have a unified sub-navigation (tabs or nested sidebar) containing the following sections:*

#### A. Inbox (Communication Hub)
*   **Purpose:** Resolve live conversations and manage exceptions fast and safely. The operator steps in when the AI needs help.
*   **Key Elements:**
    *   **Thread List:** Left/Side panel of active conversations (filterable by "Requires Attention", "Unread", "Qualified").
    *   **Conversation Timeline:** The main chat view. Crucially, AI messages must be visually distinct from Human Operator messages and Lead messages.
    *   **AI Policy Badges:** Inline indicators showing if a message was "Auto-Sent", "Suggested (Draft)", or "Blocked (Safety Rule)".
    *   **Lead Context Card:** A collapsible or side-panel view showing the current Lead's Stage, Tags, Next Scheduled Follow-up, and AI Memory snapshot.
    *   **Action Bar:** Buttons for the human to "Take Over", "Suppress/Mute", or "Approve AI Draft".

#### B. Leads (CRM & Pipeline)
*   **Purpose:** Control the pipeline at the list level with bulk-safe operations.
*   **Key Elements:**
    *   **Data Table / Kanban:** View leads filtered by Stage (New, Contacted, Engaged, Qualified, Won, Lost) and Tags (Positive, Resistive, No Response).
    *   **Priority Queue:** A highlighted section for leads marked "Strategy Review Required" (where the AI got stuck).
    *   **Bulk Actions:** Checkboxes to select leads and apply bulk tags, pause AI follow-ups, or assign new strategies.
    *   **Import/Export Wizard:** Interface for uploading CSVs of new contacts.

#### C. Agent Settings (Configuration)
*   **Purpose:** The "Brain" configuration. Building the core identity of the agent.
*   **Key Elements:**
    *   **Identity:** Agent Name, Avatar, and Emoji Usage settings.
    *   **System Prompt / Instructions:** A large, rich-text or code-style area to define the AI's core behavior.
    *   **Connected Channel:** A module to select which WhatsApp number this agent controls.
    *   **Pacing & Behavior:** Sliders or dropdowns for "Mimic Human Typing Delay" and "Outreach Aggressiveness".

#### D. Knowledge Vault (RAG Setup)
*   **Purpose:** Feed the Agent with company data so it doesn't hallucinate.
*   **Key Elements:**
    *   **Upload Area:** Drag-and-drop zone for PDFs, TXT, and Word docs.
    *   **Knowledge List:** A table showing ingested documents, processing status, token size, and "Freshness" (last updated).
    *   **Chunk/Test Viewer (Optional but cool):** A quick way to see how the AI parses the uploaded text.

#### E. Sales Materials (Collateral)
*   **Purpose:** Manage specific files, brochures, or URLs the Agent is authorized to proactively send to clients.
*   **Key Elements:**
    *   **Material Matrix:** Cards or rows showing the Asset Name, Asset File/URL, and the "Trigger Description" (when the AI should use it).
    *   **Add New Material:** A modal to upload a file (e.g., Pricing_PDF) and attach an instruction ("Send this when they ask about bulk pricing").

#### F. Strategy & Optimizer
*   **Purpose:** Author, analyze, and refine the AI's conversation playbook.
*   **Key Elements:**
    *   **Instruction Optimizer:** An interface where the operator can flag a "Bad Conversation," provide feedback ("You sounded too robotic"), and instantly generate a revised System Prompt.
    *   **Safety Polices:** Toggle hard boundaries (e.g., "Do not message between 9 PM and 9 AM").

#### G. Testing Lab (Playground)
*   **Purpose:** A safe sandbox to simulate chatting with the Agent before turning it loose on real customers.
*   **Key Elements:**
    *   **Mock Chat Interface:** Looks like a mobile phone frame or standard chat box.
    *   **Debug Panel:** Alongside the chat, show a live feed of *why* the AI answered the way it did (e.g., "Retrieved Fact X from Document Y", "Cost: $0.002").

#### H. Agent Catalog & Calendar
*   **Purpose:** Connect the agent to what you sell and when you are free.
*   **Key Elements:**
    *   **Product List:** Simple CMS table for Items, Prices, and Descriptions.
    *   **Calendar Integration:** View of connected schedules (Google Calendar sync status) so the AI knows when to book appointments.

#### I. Analytics & Performance
*   **Purpose:** Prove the AI is saving money and making money.
*   **Key Elements:**
    *   **North-Star Scorecards:** Large metrics for "Qualified Outcomes", "Negative Signal Rate" (Spam reports), and "AI Cost per Conversion".
    *   **Charts:** Message volume over time, conversion funnels (Leads -> Engaged -> Booked).

### 3.4. Account Settings (Global)
**Page:** `Tenant Settings`
*   **Purpose:** Manage the tenant's exact platform footprint.
*   **Key Elements:**
    *   **Billing & Usage:** Token consumption, subscription tier, credit card management.
    *   **User Profile:** Name, Email, Password resets.
    *   **Global Integrations:** Setting up the overarching WhatsApp Business Accounts (Baileys configurations) and MCP tools.

---

## 4. Stitch Implementation Instructions
*   **Creativity is Yours:** Read the above intent for each component, but construct the UI however you see fit. You can use cards, modals, slide-overs, tables, or innovative new UX paradigms. 
*   **Feedback Loops:** Ensure every interactive element (buttons, toggles, uploads) has clear, modern state indicators (hover, disabled, loading, success toast).
*   **Responsiveness:** Assume the dashboard will be primarily used on Desktop/Laptop, but the "Inbox" thread view must be comprehensible if a user checks it on a tablet.
*   **The "Wow" Factor:** This is a next-generation AI platform. Use subtle glassmorphism, precise shadows, and clean modern typography. Make the data look beautiful, not just functional.
