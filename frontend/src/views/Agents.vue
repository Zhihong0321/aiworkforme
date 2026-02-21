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
  <div class="min-h-[calc(100vh-64px)] w-full bg-white font-inter text-slate-700 flex flex-col pb-20 relative overflow-hidden">
    <!-- Aurora Background Effect -->
    <div class="absolute inset-0 hidden z-0 pointer-events-none opacity-50"></div>

    <!-- Header -->
    <div class="p-5 border-b border-slate-200 bg-white border border-slate-200 shadow-sm rounded-b-[2rem] sticky top-0 z-30 mb-4 relative">
      <div class="flex justify-between items-end">
        <div>
          <h1 class="text-3xl font-semibold text-slate-900 tracking-tight mb-1">AI Agents</h1>
          <p class="text-[10px] text-blue-600 font-bold uppercase tracking-widest mt-1">Hire & Train AI</p>
        </div>
        <button @click="resetForm()" class="h-10 w-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-900 border border-slate-200 shadow-lg active:scale-95 transition-all">
          <svg class="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        </button>
      </div>

      <!-- Quick Actions / Loading State -->
      <div class="mt-4 flex items-center justify-between">
        <span v-if="isLoading" class="text-xs font-semibold text-purple-400 animate-pulse">Syncing agents...</span>
        <span v-else class="text-xs font-semibold text-slate-600">{{ agents.length }} Active Agents</span>
        
        <button @click="loadAgents" class="text-[10px] font-bold uppercase tracking-wider text-slate-600 hover:text-slate-900 flex items-center gap-1 active:scale-95">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          Refresh
        </button>
      </div>
    </div>

    <!-- Main Content Area -->
    <div class="px-4 space-y-6 relative z-10 w-full lg:flex lg:gap-6 lg:space-y-0 box-border">
      
      <!-- ==================== AGENTS LIST (Mobile: Stacked, Desktop: Left Col) ==================== -->
      <div v-if="!form.id || (agents.length && form.id === agents[0]?.id)" class="w-full lg:w-1/3 flex flex-col gap-4">
        <h2 class="text-sm font-bold text-slate-900 uppercase tracking-wider pl-2 lg:hidden">Active Agents</h2>
        
        <div v-if="!agents.length && !isLoading" class="bg-white border border-slate-200 shadow-sm rounded-3xl p-8 text-center border border-slate-200">
          <div class="w-16 h-16 rounded-full bg-white flex items-center justify-center mx-auto mb-4 border border-slate-200">
             <svg class="w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
          </div>
          <p class="text-slate-600 text-sm">No agents hired yet. Click the + button above to create your first AI agent.</p>
        </div>

        <div 
          v-for="agent in agents" 
          :key="agent.id"
          class="bg-white border border-slate-200 shadow-sm p-5 rounded-3xl border transition-all cursor-pointer relative overflow-hidden group"
          :class="form.id === agent.id ? 'border-purple-500 shadow-lg shadow-purple-500/20' : 'border-slate-200 hover:border-slate-300'"
          @click="selectAgent(agent)"
        >
          <!-- Active dot indicator -->
          <div v-if="form.id === agent.id" class="absolute top-0 right-0 w-24 h-24 bg-blue-600 text-white shadow-sm hover:bg-blue-700 rounded-bl-full opacity-20 blur-2xl"></div>

          <div class="flex items-start gap-4">
            <!-- Avatar -->
            <div class="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center text-lg font-bold text-slate-900 shadow-inner border border-slate-200 shrink-0 relative overflow-hidden">
               <span class="relative z-10">{{ agent.name.slice(0, 2).toUpperCase() }}</span>
               <div v-if="agent.status === 'ready'" class="absolute inset-0 bg-blue-600 text-white shadow-sm hover:bg-blue-700 opacity-20"></div>
            </div>
            
            <div class="flex-grow min-w-0">
               <div class="flex justify-between items-center mb-1">
                 <h3 class="font-bold text-slate-900 text-lg truncate">{{ agent.name }}</h3>
                 <span class="w-2.5 h-2.5 rounded-full" :class="agent.status === 'ready' ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]' : 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]'"></span>
               </div>
               
               <div class="flex items-center gap-3 text-xs text-slate-600 font-medium">
                  <span class="flex items-center gap-1">
                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                    {{ formatTokens(agent.tokenCountToday) }}
                  </span>
                  <span class="flex items-center gap-1">
                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                    {{ agent.linkedMcpCount || 0 }} skills
                  </span>
               </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ==================== AGENT CONFIGURATION FORM ==================== -->
      <div v-if="form.id || Object.keys(form).length > 0" class="w-full lg:w-2/3 space-y-5">
        
        <div class="flex items-center justify-between pl-2 pb-1 border-b border-slate-200">
           <h2 class="text-sm font-bold text-slate-900 uppercase tracking-wider">{{ form.id ? 'Edit Profile' : 'New Agent' }}</h2>
           <router-link v-if="form.id" :to="`/chat/${form.id}`" class="text-[11px] font-bold text-blue-600 uppercase tracking-wider flex items-center gap-1 bg-purple-500/10 px-3 py-1 rounded-full border border-purple-500/20 active:scale-95 transition-all">
             <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
             Run Test
           </router-link>
        </div>

        <div class="bg-white border border-slate-200 shadow-sm p-5 rounded-3xl border border-slate-200 flex flex-col gap-5">
          
          <!-- Name Input -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-bold uppercase tracking-wider text-slate-600 ml-1">Agent Name</label>
            <input 
              v-model="form.name" 
              type="text" 
              placeholder="e.g. Atlas, Sarah" 
              class="w-full bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3 text-slate-900 placeholder-slate-600 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500/50 transition-all text-[15px] font-medium" 
            />
          </div>

          <!-- System Prompt / Persona -->
          <div class="space-y-1.5 focus-within">
            <div class="flex justify-between items-center ml-1">
              <label class="text-[11px] font-bold uppercase tracking-wider text-slate-600">Persona & Guidelines</label>
              <span class="text-[9px] text-slate-600 uppercase font-mono">system_prompt</span>
            </div>
            <div class="relative group">
              <!-- Glowing border effect on focus -->
              <div class="absolute -inset-[1px] bg-blue-600 text-white shadow-sm hover:bg-blue-700 rounded-2xl opacity-0 group-focus-within:opacity-50 blur-sm transition-opacity duration-300"></div>
              <textarea
                v-model="form.system_prompt"
                rows="5"
                placeholder="Give your agent a personality and set of rules. E.g. 'You are a helpful sales rep. Be concise and polite.'"
                class="relative z-10 w-full bg-slate-50 border border-slate-200 rounded-2xl p-4 text-slate-900 placeholder-slate-600 focus:outline-none focus:border-purple-500 transition-all text-sm leading-relaxed resize-none scrollbar-none"
              ></textarea>
            </div>
          </div>

          <!-- Skills Selection -->
          <div class="space-y-1.5">
             <label class="text-[11px] font-bold uppercase tracking-wider text-slate-600 ml-1">Active Skills (MCP)</label>
             <div class="flex items-center gap-2">
               <select 
                 v-model="form.linkedMcpId" 
                 class="flex-grow bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3 text-slate-900 focus:outline-none focus:border-purple-500 transition-all text-sm appearance-none"
               >
                 <option value="" disabled>{{ mcpLoading ? 'Loading skills...' : 'Select a skill to teach...' }}</option>
                 <option v-for="server in mcpServers" :key="server.id" :value="server.id">
                   Access: {{ server.name }}
                 </option>
               </select>
               <button 
                 @click="linkMcp" 
                 :disabled="!form.id || !form.linkedMcpId"
                 class="h-11 w-11 rounded-2xl bg-slate-100 text-slate-900 flex items-center justify-center shrink-0 border border-slate-200 disabled:opacity-50 disabled:cursor-not-allowed active:bg-slate-200 transition-all hover:border-purple-500/50 hover:text-purple-400"
               >
                 <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
               </button>
             </div>
          </div>

           <!-- Knowledge Upload -->
          <div class="space-y-2 mt-2 border-t border-slate-200 pt-5">
             <div class="flex items-center justify-between ml-1 mb-1">
               <label class="text-[11px] font-bold uppercase tracking-wider text-slate-600">Knowledge Base</label>
               <router-link v-if="form.id" :to="`/agents/${form.id}/knowledge`" class="text-[10px] text-purple-400 hover:text-slate-900 transition-colors">Manage All &rarr;</router-link>
             </div>
             
             <!-- Unified Upload Button via hidden input -->
             <div class="relative">
               <input
                 type="file"
                 class="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
                 :disabled="!form.id || isUploading"
                 @change="handleFileUpload"
               />
               <div 
                 class="w-full bg-slate-50 border border-dashed border-slate-300 rounded-2xl py-4 flex flex-col items-center justify-center transition-all"
                 :class="!form.id ? 'opacity-50' : 'hover:border-purple-500 hover:bg-slate-50'"
               >
                 <svg class="w-6 h-6 text-slate-600 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                 <span class="text-sm font-medium" :class="!form.id ? 'text-slate-600' : 'text-purple-400'">
                   {{ isUploading ? 'Uploading...' : form.id ? 'Tap to upload document' : 'Save agent to enable uploads' }}
                 </span>
               </div>
             </div>

             <!-- File List (Mini View) -->
             <div v-if="form.id && knowledgeFiles.length" class="mt-3 space-y-2">
                <div v-for="file in knowledgeFiles.slice(0,3)" :key="file.id" class="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
                  <div class="flex items-center gap-3 overflow-hidden">
                    <svg class="h-5 w-5 text-purple-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                    <span class="text-[13px] text-slate-700 truncate font-medium">{{ file.filename }}</span>
                  </div>
                  <button @click.stop="deleteKnowledgeFile(file.id)" class="text-red-400 p-1.5 active:scale-95 transition-transform" title="Delete">
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                  </button>
                </div>
                <p v-if="knowledgeFiles.length > 3" class="text-center text-xs text-slate-600 pt-1">
                  +{{ knowledgeFiles.length - 3 }} more files attached
                </p>
             </div>
          </div>

          <!-- Form Actions -->
          <div class="flex gap-3 pt-4 border-t border-slate-200 mt-2">
            <button 
              @click="saveAgent" 
              :disabled="isSaving"
              class="flex-grow bg-blue-600 text-white shadow-sm hover:bg-blue-700 font-bold text-sm py-3.5 rounded-xl shadow-lg shadow-purple-500/20 active:scale-[0.98] transition-transform flex justify-center items-center h-12"
            >
              <div v-if="isSaving" class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              <span v-else>{{ form.id ? 'Save Updates' : 'Train Agent' }}</span>
            </button>
            <button 
              v-if="form.id"
              @click="deleteAgent(form.id)"
              :disabled="deletingAgentId === form.id"
              class="h-12 w-12 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-500 shrink-0 active:scale-95 transition-transform disabled:opacity-50"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
          </div>
          
          <p v-if="message" class="text-center text-xs font-semibold" :class="message.includes('failed') ? 'text-red-400' : 'text-emerald-400'">
            {{ message }}
          </p>
          
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
/* Only keep custom scrollbar styling if needed, removed complex glowing borders in favor of tailwind utilities */
::-webkit-scrollbar {
  display: none;
}
</style>