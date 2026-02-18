<script setup>
import { onMounted, reactive, ref } from 'vue'
import { request } from '../services/api'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import TuiSelect from '../components/ui/TuiSelect.vue'

const agents = ref([])
const mcpServers = ref([])
const knowledgeFiles = ref([])
const isLoading = ref(true)
const mcpLoading = ref(true)
const isSaving = ref(false)
const isUploading = ref(false)
const deletingAgentId = ref(null)
const message = ref('')

const form = reactive({
  id: null,
  name: '',
  system_prompt: '',
  linkedMcpId: '',
})

const statusVariant = (status) => {
  const normalized = (status || '').toLowerCase()
  if (normalized === 'live' || normalized === 'active' || normalized === 'ready') return 'success'
  if (normalized === 'watch' || normalized === 'syncing' || normalized === 'cooldown') return 'warning'
  return 'muted'
}

const formatTokens = (value) => {
  const num = Number(value)
  if (Number.isNaN(num)) return value || '—'
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`
  return `${num}`
}

const extractLinkedMcpIds = (agent) => {
  if (!agent) return []
  if (Array.isArray(agent.linked_mcp_ids)) return agent.linked_mcp_ids
  if (Array.isArray(agent.linkedMcpIds)) return agent.linkedMcpIds
  if (agent.linkedMcpId) return [agent.linkedMcpId]
  if (agent.linked_mcp_id) return [agent.linked_mcp_id]
  return []
}

const loadKnowledgeFiles = async (agentId) => {
  console.log('loadKnowledgeFiles called for agent:', agentId)
  if (!agentId) {
    knowledgeFiles.value = []
    return
  }
  try {
    const data = await request(`/agents/${agentId}/knowledge`)
    console.log('Knowledge files loaded:', data)
    knowledgeFiles.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('Failed to load knowledge files', error)
    knowledgeFiles.value = []
  }
}

const resetForm = (agent) => {
  console.log('resetForm called with:', agent)
  const linkedIds = extractLinkedMcpIds(agent)
  form.id = agent?.id ?? null
  form.name = agent?.name ?? ''
  form.system_prompt = agent?.system_prompt ?? agent?.systemPrompt ?? ''
  form.linkedMcpId = linkedIds[0] ?? ''
  
  console.log('Form ID set to:', form.id)
  if (form.id) {
    loadKnowledgeFiles(form.id)
  } else {
    knowledgeFiles.value = []
  }
}

const loadAgents = async () => {
  isLoading.value = true
  message.value = ''
  try {
    const data = await request('/agents/')
    agents.value = Array.isArray(data)
      ? data.map((agent) => {
          const linkedIds = extractLinkedMcpIds(agent)
          return {
            id: agent.id,
            name: agent.name ?? 'Unknown Agent',
            status: (agent.status ?? 'ready').toLowerCase(),
            lastActive: agent.lastActive ?? agent.last_active ?? '—',
            tokenCountToday: agent.tokenCountToday ?? agent.token_count_today ?? 0,
            linkedMcpIds: linkedIds,
            linkedMcpId: linkedIds[0] ?? '',
            linkedMcpCount: agent.linked_mcp_count ?? agent.linkedMcpCount ?? linkedIds.length,
            system_prompt: agent.system_prompt ?? '',
          }
      })
      : []
  } catch (error) {
    console.error('Failed to load agents', error)
    message.value = 'Failed to load agents from API.'
    agents.value = []
  } finally {
    isLoading.value = false
  }
}

const loadMcpServers = async () => {
  mcpLoading.value = true
  try {
    const data = await request('/mcp/servers')
    mcpServers.value = Array.isArray(data)
      ? data.map((server, index) => ({
          id: server.id ?? index,
          name: server.name ?? 'server',
          status: (server.status ?? 'online').toLowerCase(),
          endpoint: server.endpoint ?? server.script ?? ''
      }))
      : []
  } catch (error) {
    console.error('Failed to load mcp servers', error)
    mcpServers.value = []
  } finally {
    mcpLoading.value = false
  }
}

const saveAgent = async () => {
  isSaving.value = true
  message.value = ''
  try {
    const method = form.id ? 'PUT' : 'POST'
    const path = form.id ? `/agents/${form.id}` : `/agents/`
    const payload = {
      name: form.name,
      system_prompt: form.system_prompt,
    }

    const savedData = await request(path, {
      method,
      body: JSON.stringify(payload)
    })

    message.value = form.id ? 'Agent updated' : 'Agent created'
    await loadAgents()
    
    // Auto-select the saved agent to enable file uploads immediately
    const reloadedAgent = agents.value.find(a => a.id === savedData.id)
    if (reloadedAgent) {
      selectAgent(reloadedAgent)
    }
  } catch (error) {
    console.error('Save agent failed', error)
    message.value = `Save failed: ${error.message}`
  } finally {
    isSaving.value = false
  }
}

const deleteAgent = async (agentId) => {
  if (!agentId) return
  const confirmDelete = window.confirm('Delete this agent? This action cannot be undone.')
  if (!confirmDelete) return

  deletingAgentId.value = agentId
  message.value = ''
  try {
    await request(`/agents/${agentId}`, { method: 'DELETE' })
    message.value = 'Agent deleted.'
    await loadAgents()
    if (form.id === agentId) resetForm()
  } catch (error) {
    console.error('Delete agent failed', error)
    message.value = `Delete failed: ${error.message}`
  } finally {
    deletingAgentId.value = null
  }
}

const linkMcp = async () => {
  if (!form.id || !form.linkedMcpId) {
    message.value = 'Select an agent and MCP to link.'
    return
  }

  try {
    await request(`/agents/${form.id}/link-mcp/${form.linkedMcpId}`, {
      method: 'POST'
    })
    message.value = 'MCP linked to agent.'
    await loadAgents()
  } catch (error) {
    console.error('Link MCP failed', error)
    message.value = `Link failed: ${error.message}`
  }
}

const handleFileUpload = async (event) => {
  const file = event.target.files?.[0]
  if (!file || !form.id) {
    message.value = 'Select an agent before uploading.'
    event.target.value = ''
    return
  }

  isUploading.value = true
  message.value = ''
  try {
    const formData = new FormData()
    formData.append('file', file)
    
    // Using fetch directly for FormData as request helper is optimized for JSON
    // But we still need the headers
    const res = await fetch(`${window.location.origin}/api/v1/agents/${form.id}/knowledge`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-Tenant-Id': localStorage.getItem('tenant_id') || ''
      },
      body: formData
    })
    
    if (!res.ok) {
       const err = await res.json().catch(() => ({}))
       throw new Error(err.detail || 'Upload failed')
    }
    
    message.value = 'File uploaded to agent knowledge.'
    await loadKnowledgeFiles(form.id)
  } catch (error) {
    console.error('Upload failed', error)
    message.value = `Upload failed: ${error.message}`
  } finally {
    isUploading.value = false
    event.target.value = ''
  }
}

const deleteKnowledgeFile = async (fileId) => {
  if (!confirm('Delete this file?')) return
  try {
    await request(`/agents/${form.id}/knowledge/${fileId}`, {
      method: 'DELETE'
    })
    await loadKnowledgeFiles(form.id)
  } catch (error) {
    console.error('Delete file failed', error)
    message.value = `Failed to delete file: ${error.message}`
  }
}

const selectAgent = (agent) => {
  resetForm(agent)
}

onMounted(() => {
  loadAgents()
  loadMcpServers()
})

</script>

<template>
  <div class="relative min-h-screen">
    <main class="relative z-10 mx-auto w-full max-w-none px-5 lg:px-10 py-10 space-y-8">
      <header class="tui-surface rounded-3xl border border-slate-200 p-8 shadow-sm">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div class="space-y-2">
            <p class="text-[10px] uppercase font-black tracking-[0.32em] text-indigo-600">Pillar 1</p>
            <h1 class="text-3xl font-black text-slate-900 tracking-tight">My AI Agent</h1>
            <p class="text-sm text-slate-500 max-w-xl">
              Create your AI agent, define their personality, and give them the "Keys" to your business skills like products and appointments.
            </p>
          </div>
        </div>
      </header>

      <section class="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <TuiCard title="Agents" subtitle="list">
          <div class="mb-4 flex items-center justify-between gap-3 text-xs text-slate-600">
            <span v-if="message">{{ message }}</span>
            <TuiButton size="sm" variant="outline" @click="loadAgents">refresh</TuiButton>
          </div>
          <div class="divide-y divide-slate-200">
            <div
              v-for="agent in agents"
              :key="agent.id"
              class="flex flex-col gap-3 py-4"
            >
              <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                <div class="flex items-start gap-3 flex-1 min-w-0">
                  <div class="h-10 w-10 shrink-0 rounded-md border border-slate-300 bg-white text-center text-sm font-semibold leading-10 uppercase text-slate-800">
                    {{ agent.name.slice(0, 2) }}
                  </div>
                  <div class="min-w-0 flex-1">
                    <p class="text-base font-semibold text-slate-900 break-words leading-tight">{{ agent.name }}</p>
                  </div>
                </div>

                <div class="flex shrink-0 gap-6 sm:text-right">
                   <div class="flex flex-col gap-1 text-sm text-slate-700">
                    <p class="text-[11px] uppercase tracking-[0.18em] text-slate-500">tokens today</p>
                    <p class="font-semibold tabular-nums">{{ formatTokens(agent.tokenCountToday) }}</p>
                  </div>
                  <div class="flex flex-col gap-1 text-sm text-slate-700">
                    <p class="text-[11px] uppercase tracking-[0.18em] text-slate-500">last active</p>
                    <p class="font-semibold tabular-nums">{{ agent.lastActive || '—' }}</p>
                  </div>
                </div>
              </div>
              
              <div class="flex items-center justify-between sm:justify-end gap-4 border-t border-slate-50 pt-2 sm:border-t-0 sm:pt-0">
                 <div class="flex items-center gap-2">
                     <span class="text-[11px] uppercase tracking-[0.18em] text-slate-500 sm:hidden">Status</span>
                     <TuiBadge :variant="statusVariant(agent.status)" class="w-24 justify-center">
                      {{ agent.status || 'ready' }}
                    </TuiBadge>
                 </div>

                 <div class="flex flex-wrap items-center gap-2 text-xs text-slate-700">
                    <TuiButton size="sm" variant="outline" @click="selectAgent(agent)">edit</TuiButton>
                    <router-link :to="`/chat/${agent.id}`" class="inline-flex items-center">
                      <TuiButton size="sm" variant="ghost">tester</TuiButton>
                    </router-link>
                    <router-link :to="`/agents/${agent.id}/knowledge`" class="inline-flex items-center">
                      <TuiButton size="sm" variant="ghost">knowledge</TuiButton>
                    </router-link>
                    <TuiButton
                      size="sm"
                      variant="ghost"
                      class="text-red-600"
                      :loading="deletingAgentId === agent.id"
                      @click="deleteAgent(agent.id)"
                    >
                      delete
                    </TuiButton>
                    <TuiBadge variant="muted">
                      mcp: {{ agent.linkedMcpCount || 0 }} linked
                    </TuiBadge>
                 </div>
              </div>
            </div>
            <div v-if="!agents.length" class="py-6 text-sm text-slate-600">
              No agents yet. Create one using the form.
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Agent Form" subtitle="create / edit">
          <div class="space-y-4">
            <TuiInput label="Agent Name" placeholder="Atlas" v-model="form.name" />
            <label class="flex flex-col gap-2 text-sm text-slate-800">
              <div class="flex items-center justify-between">
                <span class="text-[11px] uppercase tracking-[0.2em] text-slate-600">Instruction</span>
                <span class="text-[11px] text-slate-500">system_prompt</span>
              </div>
              <div class="relative breathing-ring">
                <textarea
                  v-model="form.system_prompt"
                  rows="4"
                  placeholder="Set concise operating instructions for the agent."
                  class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-[inset_0_1px_1px_rgba(15,23,42,0.06)] focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-200"
                ></textarea>
              </div>
            </label>

            <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
              <TuiSelect
                label="Agent Skills"
                :options="mcpServers.map((server) => ({ label: `Access: ${server.name}`, value: server.id }))"
                v-model="form.linkedMcpId"
                placeholder="Select a Skill"
                :hint="mcpLoading ? 'loading...' : 'Product Catalog, Calendar, etc.'"
              />
              <div class="flex items-end">
                <TuiButton class="w-full" variant="outline" :loading="false" @click="linkMcp">Give Skill Access</TuiButton>
              </div>
            </div>
            <div class="space-y-2">
              <p class="text-[11px] uppercase tracking-[0.2em] text-slate-600">Attach File</p>
              <input
                type="file"
                class="w-full rounded-md border border-dashed border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="!form.id || isUploading"
                @change="handleFileUpload"
              />
              <p class="text-xs text-slate-600">
                {{ form.id ? 'Uploads will POST to /agents/{id}/knowledge' : 'Save the agent before uploading.' }}
              </p>
              
              <!-- Knowledge Files List -->
              <div v-if="form.id" class="mt-2 rounded-md border border-slate-100 bg-slate-50 p-2 text-sm">
                <p class="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Attached Knowledge</p>
                <ul v-if="knowledgeFiles.length" class="space-y-1">
                  <li v-for="file in knowledgeFiles" :key="file.id" class="flex items-center gap-2 text-slate-700">
                    <svg class="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span class="truncate flex-1">{{ file.filename }}</span>
                    <button @click="deleteKnowledgeFile(file.id)" class="ml-auto text-red-400 hover:text-red-600 cursor-pointer p-1" title="Delete file">
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </li>
                </ul>
                <p v-else class="text-xs text-slate-400 italic">No files attached.</p>
              </div>
            </div>
            <div class="flex flex-wrap gap-3">
              <TuiButton :loading="isSaving" @click="saveAgent">
                {{ form.id ? 'Save changes' : 'Create agent' }}
              </TuiButton>
              <TuiButton variant="outline" @click="resetForm()">Reset</TuiButton>
              <TuiButton
                v-if="form.id"
                variant="ghost"
                class="text-red-600 ml-auto"
                :loading="deletingAgentId === form.id"
                @click="deleteAgent(form.id)"
              >
                Delete Agent
              </TuiButton>
            </div>
          </div>
        </TuiCard>
      </section>
    </main>
  </div>
</template>

<style scoped>
.breathing-ring {
  position: relative;
  border-radius: 0.5rem;
}

.breathing-ring::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: inherit;
  background: linear-gradient(120deg, #16f2b3, #7c3aed, #06b6d4, #16f2b3);
  background-size: 220% 220%;
  opacity: 0;
  z-index: 0;
  filter: blur(0.5px);
  transition: opacity 0.3s ease;
  animation: breatheGradient 3s ease-in-out infinite;
  pointer-events: none;
}

.breathing-ring:focus-within::after {
  opacity: 0.65;
}

.breathing-ring > textarea {
  position: relative;
  z-index: 1;
}

@keyframes breatheGradient {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}
</style>