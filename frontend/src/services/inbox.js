const API_BASE = '/api/v1';

export const InboxService = {
    async getDueLeads(workspaceId) {
        // This will eventually call the CRMAgent's "due" endpoint
        // For now, we fetch leads from the M1 schemas
        const resp = await fetch(`${API_BASE}/workspaces/${workspaceId}/leads`);
        return await resp.json();
    },

    async getMessages(threadId) {
        const resp = await fetch(`${API_BASE}/threads/${threadId}/messages`);
        return await resp.json();
    },

    async sendMessage(leadId, workspaceId, content) {
        const resp = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lead_id: leadId, workspace_id: workspaceId, message: content })
        });
        return await resp.json();
    },

    async getPolicyAudit(workspaceId, leadId) {
        const resp = await fetch(`${API_BASE}/workspaces/${workspaceId}/policy/decisions?lead_id=${leadId}`);
        return await resp.json();
    }
};
