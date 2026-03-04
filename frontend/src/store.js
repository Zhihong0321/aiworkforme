import { reactive, watch } from 'vue'
import { request } from './services/api'

export const store = reactive({
    agents: [],
    activeAgentId: localStorage.getItem('activeAgentId') || null,
    activeAgent: null,
    isLoading: false,

    async fetchAgents() {
        this.isLoading = true
        try {
            const data = await request('/agents/')
            this.agents = Array.isArray(data) ? data : []
            if (this.agents.length > 0 && !this.activeAgentId) {
                this.setActiveAgent(this.agents[0].id)
            } else if (this.activeAgentId) {
                this.activeAgent = this.agents.find(a => a.id == this.activeAgentId)
            }
        } catch (e) {
            console.error('Failed to fetch agents', e)
        } finally {
            this.isLoading = false
        }
    },

    setActiveAgent(id) {
        this.activeAgentId = id
        this.activeAgent = this.agents.find(a => a.id == id)
        localStorage.setItem('activeAgentId', id)
    }
})
