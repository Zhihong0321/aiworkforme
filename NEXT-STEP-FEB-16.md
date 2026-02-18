# Multi-Tenant Refactor: Gaps & Recommendations (Feb 16, 2026)

## Overview
The multi-tenant architecture has been successfully implemented at the backend and database levels. Data isolation is enforced, and the platform admin control plane is functional. However, the tenant-user interface is incomplete, preventing full self-service usage.

## Identified Gaps

### 1. Management UI Missing
- **Problem**: There are no pages or forms within the tenant dashboard to create or edit **Agents** or **Workspaces**.
- **Impact**: New tenants are stuck on an empty state ("No Workspaces Found") and cannot proceed without manual database entry.
- **Missing Routes**: `/workspaces`, `/agents`.

### 2. Broken Sample Data Import
- **Problem**: The "Import Sample Data" button on the **Leads** page does not work.
- **Impact**: Prevents rapid testing of the sales outreach and playground features for new tenants.

### 3. Weak UX Feedback
- **Problem**: Actions like "Activate Strategy" provide no visual confirmation (toasts or success messages).
- **Impact**: Poor user confidence in the system state.

### 4. Direct Linking Issues
- **Problem**: The **Knowledge** page mentions linking agents in "Settings," but the Settings page is redirected to Inbox for non-platform admins.
- **Impact**: Confusing navigation paths.

## Recommendations (Next Steps)

### High Priority: Frontend Management & Logic
- [ ] **Implement `Agents.vue`**: A view to list, create, and configure agents (Name, Prompt, Model selection).
- [ ] **Implement `Workspaces.vue`**: A view to manage workspaces and link them to specific agents.
- [ ] **Update Router**: Define routes for these management views in `frontend/src/router/index.js`.
- [ ] **Playground Decoupling**: Remove the requirement to select a lead for Playground testing. User input should be treated as an incoming "inbound" message (simulating a lead) to allow for immediate testing without pre-populated data.

### Medium Priority: Self-Service & Bootstrapping
- [ ] **Onboarding Flow**: Add an "Initialize Tenant" button or automatic prompt for new users to create their first agent and workspace.
- [ ] **Fix Lead Import**: Debug the `import-sample` API endpoint or frontend integration to ensure it successfully populates the `et_leads` table with tenant-scoped data.

### Low Priority: Polish
- [ ] **Notifications System**: Implement a global toast or notification system (e.g., using a store) to provide feedback on successful API actions.
- [ ] **Status Indicators**: Improve the "Green Tier" indicator to show actual tenant usage metrics or limits.

## Verification Checklist
- [ ] Tenant A cannot see Tenant B's agents (Verified ✅)
- [ ] Platform Admin can manage all tenants (Verified ✅)
- [ ] Tenant Admin can create Agents (NOT IMPLEMENTED ❌)
- [ ] Playground responds using Tenant-specific prompt (Verified via DB Injection ✅)
