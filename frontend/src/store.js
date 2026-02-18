import { reactive, watch } from 'vue'
import { request } from './services/api'

export const store = reactive({
    workspaces: [],
    activeWorkspaceId: localStorage.getItem('activeWorkspaceId') || null,
    activeWorkspace: null,
    isLoading: false,

    async fetchWorkspaces() {
        this.isLoading = true
        try {
            const data = await request('/workspaces/')
            this.workspaces = Array.isArray(data) ? data : []
            if (this.workspaces.length > 0 && !this.activeWorkspaceId) {
                this.setActiveWorkspace(this.workspaces[0].id)
            } else if (this.activeWorkspaceId) {
                this.activeWorkspace = this.workspaces.find(w => w.id == this.activeWorkspaceId)
            }
        } catch (e) {
            console.error('Failed to fetch workspaces', e)
        } finally {
            this.isLoading = false
        }
    },

    setActiveWorkspace(id) {
        this.activeWorkspaceId = id
        this.activeWorkspace = this.workspaces.find(w => w.id == id)
        localStorage.setItem('activeWorkspaceId', id)
    }
})
