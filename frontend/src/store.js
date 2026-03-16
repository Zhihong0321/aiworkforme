import { reactive } from 'vue'
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
            if (this.agents.length === 0) {
                this.clearActiveAgent()
                return
            }

            const activeAgent = this.agents.find((agent) => String(agent.id) === String(this.activeAgentId))
            if (activeAgent) {
                this.setActiveAgent(activeAgent.id)
                return
            }

            this.setActiveAgent(this.agents[0].id)
        } catch (e) {
            console.error('Failed to fetch agents', e)
        } finally {
            this.isLoading = false
        }
    },

    setActiveAgent(id) {
        const agent = this.agents.find((item) => String(item.id) === String(id))
        if (!agent) {
            return false
        }

        this.activeAgentId = agent.id
        this.activeAgent = agent
        localStorage.setItem('activeAgentId', String(agent.id))
        return true
    },

    clearActiveAgent() {
        this.activeAgentId = null
        this.activeAgent = null
        localStorage.removeItem('activeAgentId')
    },
})
