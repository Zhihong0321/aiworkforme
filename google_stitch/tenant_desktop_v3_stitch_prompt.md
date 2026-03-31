# Tenant Desktop UX v3 - Stitch Prompt Pack

## Global Direction

Create a **desktop-first SaaS workspace** for a tenant managing many AI sales agents on WhatsApp.

The visual theme must closely follow this reference:
`E:\AIworkforMe\dev_reference\new_ui_3-0.jpg`

Translate the reference into a new product UI with these characteristics:

- Light mode only
- Premium enterprise dashboard feel
- White cards on a very pale cool gray / blue background
- Soft sky-blue accents and subtle blue gradients
- Rounded large cards and panels
- Very gentle shadows, no heavy borders
- Calm, polished, data-dense layout
- Minimal visual noise
- Feels modern, expensive, and easy to understand

Typography and styling:

- Headlines: Manrope or Plus Jakarta Sans, semibold
- Body: Inter, regular to medium
- Text color: deep slate, never pure black
- Accent color: medium enterprise blue, plus very pale blue tints
- Do not use purple accents
- Do not use dark mode
- Do not make the UI look experimental or futuristic

Core UX rule:

- Inside each agent dashboard, the inbox and conversation experience must feel immediately familiar to **WhatsApp Web on desktop**
- Users should not need to learn a new chat mental model
- Preserve the familiar pattern of conversation list, active chat thread, timestamps, unread badges, message composer, and contact context
- The look is upgraded and premium, but the interaction pattern is familiar

Navigation items inside agent dashboard:

- Inbox
- Instruction Setting
- Add New Contact
- CRM Setting
- Calendar
- Optimizer
- Connected WhatsApp Channel
- Playground
- Catalog
- Sales Material

Product workflow to reflect:

1. Tenant dashboard shows all agent status cards
2. Clicking an agent card enters that agent dashboard
3. Agent dashboard home is the inbox
4. Inbox behaves like WhatsApp Web on desktop
5. New agent creation flow uses these steps:
   - Agent Name
   - Setup WhatsApp Channel
   - Instruction Setting
   - Sales Material Upload (optional / skippable)
   - Playground

Desktop layout guidance:

- Use a wide 1440px style composition
- Left sidebar for global product navigation
- Main content area with spacious card grid
- In agent dashboard, use a second-level navigation or integrated workspace shell
- Keep outer spacing generous, around 24px to 32px
- Cards should have 18px to 24px rounding
- Use subtle chart widgets, status chips, metadata rows, and small helper text
- Avoid mobile proportions or stacked mobile cards

## Screen 1 - Tenant Dashboard

Create a **desktop tenant dashboard** that acts as the landing page for a tenant managing multiple AI agents.

This screen must include:

- A left sidebar navigation for the platform
- A top header with page title, search, filter or date tools, and tenant profile area
- Main hero title such as "Agents" or "Tenant Dashboard"
- A responsive-looking desktop grid of agent status cards

Each agent card should show:

- Agent name
- Agent avatar or icon
- Status badge: Active, Idle, Needs Attention, Offline
- Last activity timestamp
- WhatsApp channel indicator
- Quick performance summary such as conversations today, response time, conversion, or tasks completed
- Subtle visual emphasis for active agents

Also include:

- A compact summary row with total agents, active now, conversations today, and alerts
- A right-side or top-area quick insight panel if it helps composition
- A clear affordance that clicking a card enters that agent's dashboard

Visual direction:

- Follow the exact softness, spacing, and color mood of the reference image
- Make it feel like a polished operations center
- Use elegant white cards with pale blue highlights and gentle shadows

## Screen 2 - Agent Dashboard / Inbox Home

Create a **desktop agent dashboard home screen** where the default page is the inbox.

This screen must feel like a premium enterprise version of **WhatsApp Web desktop** while preserving familiarity.

Layout:

- Leftmost global or agent navigation rail
- Secondary navigation for this agent workspace with these items:
  Inbox, Instruction Setting, Add New Contact, CRM Setting, Calendar, Optimizer, Connected WhatsApp Channel, Playground, Catalog, Sales Material
- Main content area dedicated to inbox home

Inbox home composition:

- Left panel: inbox conversation list
- Center panel: either selected conversation preview or inbox overview empty state
- Right panel: compact CRM / contact / conversation context summary

Conversation list items should include:

- Avatar
- Contact name
- Last message preview
- Timestamp
- Unread badge
- Assigned label or AI / Human handoff chip when useful

Also include small agent summary widgets such as:

- Agent status
- Connected WhatsApp number
- Today's conversations
- Pending replies

Important:

- The UX must read instantly as familiar chat software
- The screen should not feel like a generic CRM table
- Preserve the speed and simplicity of WhatsApp Web mental model

## Screen 3 - Agent Dashboard / Active Conversation

Create a **desktop active conversation screen** inside the same agent dashboard shell.

The structure should strongly resemble WhatsApp Web on desktop:

- Left panel with conversation list
- Large center panel with active chat thread
- Right panel with customer profile and CRM context

Center chat panel must include:

- Contact name and status in the header
- Message history with clear differentiation between customer messages and agent messages
- AI assistant participation indicator when relevant
- Human takeover or handoff control
- Message composer fixed at bottom
- Attachment / template / send actions

Right CRM context panel should include:

- Contact details
- Tags
- Recent activities
- Order or lead status
- Notes
- Quick actions such as assign, schedule, update lead stage

Visual requirement:

- Keep it minimal, soft, and familiar
- The conversation thread should feel like something users already know how to use
- The styling must still match the blue-white premium reference image

## Screen 4 - New Agent Creation Flow

Create a **desktop multi-step new agent creation flow**.

This should feel guided, calm, and premium. Use a wide desktop wizard layout with a stepper and helpful summaries.

The required steps are:

1. Agent Name
2. Setup WhatsApp Channel
3. Instruction Setting
4. Sales Material Upload
5. Playground

Requirements:

- Show the flow as a clear step-based wizard
- Make Sales Material Upload visibly optional with a skip action
- Include helper text under each form section
- Use a right-side summary panel showing completion progress and agent preview
- Use clean form cards, toggles, upload areas, and action buttons

Per-step hints:

- Agent Name: agent display name, internal label, avatar/icon, role summary
- Setup WhatsApp Channel: phone number connection, QR or channel status, verification state
- Instruction Setting: brand tone, response rules, escalation rules, business objective
- Sales Material Upload: drag-and-drop files, catalog docs, PDFs, scripts, FAQ, optional skip
- Playground: test message simulation and prompt preview before publishing

Visual style:

- Must remain inside the same desktop design language as the dashboard and inbox
- Soft cards, blue accents, premium enterprise feel
- Avoid bland default form-builder styling

## Generated Stitch Outputs

Project:

- `projects/15199232417745207862` - Tenant Desktop UX v3 - WhatsApp Agent Workflow

Successful desktop screens:

- Tenant dashboard: `projects/15199232417745207862/screens/a602e952b4e049c6907eedba40dc06e8`
- Active conversation: `projects/15199232417745207862/screens/7c5b6fbc6ae3441ab6a6be45ed0c6818`
- Inbox home: `projects/15199232417745207862/screens/aceb1fe8d4fc4019a289896f79210247`
- New agent setup wizard: `projects/15199232417745207862/screens/53aab2e994d5473992236ae0d656900b`

Generation note:

- Direct `generate_screen_from_text` for the inbox-home screen timed out multiple times with `deviceType=DESKTOP`.
- The successful workaround was to use `edit_screens` on the active conversation screen and convert it into the inbox home state.
- For similar screens, prefer editing an existing shell instead of generating a brand new screen from scratch.

## Safe Stitch Workflow

Use this workflow to reduce Stitch MCP timeouts on desktop generations.

Rules:

- Generate one screen at a time
- Always set `deviceType=DESKTOP`
- Keep the first prompt under roughly 120 to 180 words
- Focus the first prompt on layout and core UX only
- Add visual refinement in a second pass with `edit_screens`
- Avoid asking for too many widgets, side cases, or long requirement lists in the first generation
- Prefer reusing an existing screen and editing it into the next state when the shells are similar

Recommended sequence:

1. Generate tenant dashboard
2. Generate inbox home with only the essential WhatsApp-style shell
3. Edit inbox home into active conversation
4. Generate new agent wizard
5. Use `edit_screens` for polish, denser widgets, and brand details

### Safe Prompt 1 - Tenant Dashboard

Create a desktop tenant dashboard for managing multiple AI WhatsApp agents. Use light mode, a pale cool gray background, white rounded cards, subtle blue accents, soft shadows, and deep slate text. Layout: left sidebar, top header, and wide main content area. Show a summary row with Total Agents, Active Now, Conversations Today, and Alerts. The main content should be a grid of clickable agent cards. Each card needs agent avatar, name, status badge, WhatsApp connection status, last activity, and one quick metric like conversations today or response time. Make active cards slightly blue-tinted. Keep it calm, premium, and desktop-first.

### Safe Prompt 2 - Inbox Home

Create a desktop inbox home screen for an AI WhatsApp agent workspace. The UX should feel familiar to WhatsApp Web on desktop. Use light mode, pale gray-blue background, white rounded panels, subtle blue accents, soft shadows, and deep slate text. Layout: left sidebar plus a three-column inbox shell. Column 1 is conversation list with avatar, name, preview, timestamp, and unread badge. Column 2 is inbox home or selected preview. Column 3 is compact customer CRM context. Include nav items for Inbox, Instruction Setting, Add New Contact, CRM Setting, Calendar, Optimizer, Connected WhatsApp Channel, Playground, Catalog, and Sales Material. Keep it simple and clearly desktop.

### Safe Prompt 3 - Active Conversation

Create a desktop active conversation screen in the same agent workspace shell. Keep the UX familiar to WhatsApp Web on desktop. Use the same light premium blue-white style. Layout: left conversation list, center active chat thread, right customer CRM context. The center should have contact header, inbound and outbound message bubbles, AI assistant indicator, human takeover action, and bottom message composer. The right panel should include contact details, tags, status, and notes. Keep the shell consistent with the inbox home screen.

### Safe Prompt 4 - New Agent Wizard

Create a desktop multi-step wizard for setting up a new WhatsApp sales agent. Use light mode, white rounded cards, soft blue accents, subtle shadows, and a spacious desktop layout. Show these steps: Agent Name, Setup WhatsApp Channel, Instruction Setting, Sales Material Upload, and Playground. Make Sales Material Upload optional with a skip action. Use a clear stepper, main form area, and a right-side setup summary. Keep the flow calm, guided, and premium.

## Safe Edit Prompts

Use these only after the base screen exists.

### Edit Prompt A - Add Premium Visual Detail

Refine this desktop screen to better match the soft blue-white enterprise reference style. Increase the sense of polish with calmer spacing, better card hierarchy, more subtle blue tints, cleaner typography, and gentler shadows. Keep the same layout and UX structure.

### Edit Prompt B - Add Secondary Widgets

Add compact secondary widgets and metadata without changing the core layout. Keep the screen uncluttered. Use small status chips, helper text, and one or two supporting insight modules only.

### Edit Prompt C - Strengthen WhatsApp Familiarity

Refine the inbox and conversation UI so it feels even closer to WhatsApp Web on desktop. Keep the premium visual style, but make the list, chat thread, timestamps, unread badges, and composer more immediately familiar.
