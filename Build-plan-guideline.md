# Mobile UI Build Plan Guideline

This document outlines the strategy and specific plans for building the mobile UI of the AI Agent Builder & CRM Platform. The primary target audience is **Sales Professionals** who are non-technical and prioritize speed, simplicity, and actionable insights.

## Phase 1: Core Understanding & Value Proposition

**Target Audience:** Non-technical Sales Professionals.
**Primary Goal:** To provide a simple, "no-code" interface for hiring, training, and deploying an AI assistant to handle customer conversations, capture leads, and book meetings.

**Key Value Drivers:**
1.  **Ease of Use:** Eliminate complex prompt engineering; use intuitive UI controls (toggles, sliders).
2.  **Automation:** Auto-reply to messages, qualify leads, and schedule appointments without manual intervention.
3.  **Familiarity:** The mobile experience should mimic familiar consumer apps (like popular messaging or contacts apps) rather than complex B2B enterprise software.
4.  **Actionable Insights:** Present data simply so sales reps know exactly who to follow up with and when.

---

## Phase 2: Mobile UX & User-Friendliness Strategy

The overarching philosophy for the mobile UI is: **Large touch targets, clear status indicators, minimal text entry, and guided workflows.**

### Page-by-Page UX Improvements (Mobile View)

#### 1. Login (`/login`)
*   **Design Focus:** Eliminate typing.
*   **Helpful Features:**
    *   Prominent Single Sign-On (SSO) buttons (Google, Microsoft).
    *   Clear, persistent "Remember Me" functionality.

#### 2. Inbox / Inbound (`/inbox`) - *Highest Priority*
*   **Design Focus:** Needs to feel exactly like a native messaging app (e.g., WhatsApp, iMessage).
*   **Helpful Features:**
    *   **"AI vs. Human" Toggle:** A highly visible button within a chat to seamlessly pause the AI and allow the human rep to take over.
    *   **Quick Filters:** Swipeable top tabs/pills for filtering chats (e.g., `Unread`, `Needs Attention`, `Resolved`).

#### 3. Leads / Contact Book (`/leads`)
*   **Design Focus:** Card-based layout instead of dense, horizontal data tables which are unreadable on mobile.
*   **Helpful Features:**
    *   **Swipe Actions:** Swipe left on a lead card to quick-message; swipe right to easily update status (e.g., mark "Hot").
    *   **AI Context Summaries:** A brief, 1-2 sentence AI-generated summary at the top of a lead profile so the rep grasps context instantly without reading the full chat history.

#### 4. Agents / Teammate Profile (`/agents`)
*   **Design Focus:** Avoid long-form text entry for prompt generation.
*   **Helpful Features:**
    *   **Visual Configuration:** Replace text prompts with sliders (e.g., Tone: Professional <---> Casual) and easy-to-understand Apple-style toggle switches for enabling skills (like Catalog or Calendar access).

#### 5. Knowledge (`/knowledge`)
*   **Design Focus:** Leverage native device capabilities for friction-free data entry.
*   **Helpful Features:**
    *   **Quick Capture:** A prominent button to open the phone's camera, allowing users to take photos of documents (price lists, menus) and upload them directly.
    *   Clear, simple visual status icons showing if a document is fully processed/learned by the AI.

#### 6. Catalog (`/catalog`)
*   **Design Focus:** Image-centric list/grid view optimized for quick browsing and adding items.
*   **Helpful Features:**
    *   **Floating Action Button (FAB):** A permanent `+` button for quickly adding new products.
    *   **Streamlined Add Flow:** Tap `+`, snap a product photo, enter the price and name, and save. The AI can optionally auto-generate descriptions later.

#### 7. Playground (`/playground`)
*   **Design Focus:** A chat interface identical to `/inbox`, but clearly themed as a safe testing zone (perhaps a slightly different background color).
*   **Helpful Features:**
    *   **"X-Ray Specs" / Explainability:** A toggle allowing users to see *why* the AI gave a specific response (e.g., showing which knowledge document it referenced).
    *   A prominent "Reset Chat" FAB to quickly restart testing scenarios.

#### 8. Channel Setup (`/channels`)
*   **Design Focus:** Simple status cards with one-click connection flows.
*   **Helpful Features:** For integrations like WhatsApp, provide a visual, step-by-step guide explaining how to scan a QR code using a secondary device, keeping in mind they might be viewing the instructions on their primary phone.

#### 9. Calendar (`/calendar`)
*   **Design Focus:** A clean, standard mobile timeline/agenda view.
*   **Helpful Features:** A massive, unavoidable "Sync with Google/Apple Calendar" button to automate availability management.

#### 10. Analytics (`/analytics`)
*   **Design Focus:** A vertical dashboard emphasizing top-level metrics over complex, multi-variable charts.
*   **Helpful Features:** Focus on actionable Sales KPIs at the top (e.g., "Leads Captured", "Meetings Booked", "Messages Handled"). Use simple sparklines for trends.

#### 11. Strategy (`/strategy`)
*   **Design Focus:** Template selection over custom configuration.
*   **Helpful Features:** A carousel or list of 3-4 predefined, clickable strategy templates (e.g., "Aggressive Lead Capture", "Soft Support") that instantly configure the overarching AI behavior.

---

## Phase 3: Theme and Design Execution

**Selected Theme:** Option 1 (Onyx & Aurora - Premium Dark Mode)

**Design System Foundation (Implemented in `frontend/src/style.css`):**
*   **Typography:** Added Google Font `Inter` for modern, clean, geometric text.
*   **Background (`.bg-onyx`):** Deep Onyx Black (`#0F172A`) base to reduce eye strain and give a premium feel.
*   **Accents (`.text-aurora`, `.bg-aurora-gradient`):** Vibrant purple-to-blue neon gradients used strictly for primary action areas (like the "AI vs. Human" toggle).
*   **Cards (`.glass-panel`):** Glassmorphism style with semi-transparent dark slates and blurred backdrops to make structural elements visually float above the dark canvas.

**Moving into Phase 4:** We will begin implementing the mobile UI starting with the highest-priority screen: **The Inbox (`/inbox`)**.
