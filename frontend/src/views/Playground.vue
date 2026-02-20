<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiSelect from '../components/ui/TuiSelect.vue'
import { request } from '../services/api'

const workspaces = ref([])
const agents = ref([])
const selectedAgentId = ref(null)
const messages = ref([])
const newMessage = ref('')
const isSending = ref(false)
const isLoadingThread = ref(false)
const latestDecisions = ref([])

// We'll track the active lead/workspace for this session
const activeLeadId = ref(null)
const activeWorkspaceId = ref(null)

const fetchAgents = async () => {
    try {
        const data = await request('/agents/')
        agents.value = data
        if (agents.value.length > 0 && !selectedAgentId.value) {
            selectedAgentId.value = agents.value[0].id
        }
    } catch (e) {
        console.error("Failed to fetch agents", e)
    }
}

const fetchThread = async () => {
    // If we don't have a lead ID yet, we fetch it by attempting an empty chat or a dedicated endpoint
    // For now, we'll use the chat endpoint to auto-provision if needed, or stick to the message send.
    if (!activeLeadId.value) {
        // We'll wait for the first message to establish context, or we can fetch the 'Playground' lead.
        try {
            const data = await request('/playground/leads') // This returns leads for the tenant
            const testerLead = data.find(l => l.external_id?.startsWith('playground_'))
            if (testerLead) {
                activeLeadId.value = testerLead.id
                activeWorkspaceId.value = testerLead.workspace_id
                
                const threadData = await request(`/playground/thread/${activeLeadId.value}`)
                messages.value = threadData
            }
        } catch (e) {
            console.error("Failed to fetch tester context", e)
        }
        return
    }

    isLoadingThread.value = true
    try {
        const data = await request(`/playground/thread/${activeLeadId.value}`)
        messages.value = data
    } catch (e) {
        console.error("Failed to fetch thread", e)
    } finally {
        isLoadingThread.value = false
    }
}

const sendMessage = async () => {
    if (!newMessage.value.trim()) return
    if (!selectedAgentId.value) {
        alert("Please select an Agent first!")
        return
    }
    
    const text = newMessage.value
    newMessage.value = ''
    isSending.value = true
    
    // Add optimistic message
    messages.value.push({
        id: Date.now(),
        role: 'user',
        content: text,
        created_at: new Date().toISOString()
    })

    try {
        const data = await request('/playground/chat', {
            method: 'POST',
            body: JSON.stringify({
                message: text,
                agent_id: selectedAgentId.value,
                workspace_id: activeWorkspaceId.value,
                lead_id: activeLeadId.value
            })
        })
        
        if (data.result && data.result.status === 'error') {
            console.error("Backend returned error:", data.result.message)
            messages.value.push({
                id: Date.now(),
                role: 'system',
                content: `Error: ${data.result.message}`,
                created_at: new Date().toISOString()
            })
            // Force alert just in case UI is stuck
            alert(`Chat Error: ${data.result.message}`)
        } else {
            // Only re-fetch thread if successful
            await fetchThread()
        }
        latestDecisions.value = data.decisions
    } catch (e) {
        console.error("Failed to send message", e)
        const errMsg = e.detail || e.message || 'Unknown error'
        messages.value.push({
                id: Date.now(),
                role: 'system',
                content: `System Error: ${errMsg}`,
                created_at: new Date().toISOString()
        })
        alert(`System Error: ${errMsg}`)
    } finally {
        isSending.value = false
    }
}

onMounted(() => {
    fetchAgents()
    fetchThread() // Try to find existing tester lead
})

const currentAgent = computed(() => agents.value.find(a => a.id === selectedAgentId.value))
const agentOptions = computed(() => agents.value.map(a => ({ label: a.name, value: a.id })))

const resetThread = async () => {
    if (!messages.value.length) return
    if (!confirm("Are you sure you want to clear this conversation?")) return
    
    try {
        await request(`/playground/thread/${activeLeadId.value}/reset`, { method: 'POST' })
        messages.value = []
        // Optional: Re-fetch thread to get new empty thread if needed, or just clear UI
    } catch (e) {
        console.error("Failed to reset thread", e)
        alert("Failed to reset thread")
    }
}

</script>

<template>
  <div class="flex flex-col h-[calc(100vh-64px)] w-full overflow-hidden bg-onyx font-inter text-slate-200">
    
    <!-- Header -->
    <div class="p-4 border-b border-indigo-500/30 glass-panel-light z-30 shadow-[0_4px_30px_rgba(99,102,241,0.1)] relative">
      <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>
      
      <div class="flex justify-between items-center mb-4 mt-2">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-slate-900 flex items-center justify-center shadow-inner border border-slate-700 relative overflow-hidden text-indigo-400">
             <span class="absolute inset-0 bg-indigo-500/20 blur-xl"></span>
             <svg class="w-6 h-6 relative z-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
          </div>
          <div>
            <h1 class="text-xl font-bold text-white tracking-tight leading-tight">Test Lab</h1>
            <div class="flex items-center gap-1.5 mt-0.5">
               <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse"></span>
               <p class="text-[10px] text-indigo-300 font-bold uppercase tracking-widest">Safe Zone</p>
            </div>
          </div>
        </div>

        <button @click="resetThread" v-if="messages.length > 0" class="h-9 px-3 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 text-xs font-bold uppercase tracking-wider active:scale-95 transition-all">
          Reset
        </button>
      </div>

      <!-- Agent Selection Dropdown -->
      <div class="bg-slate-900/60 border border-slate-700/50 rounded-xl p-1 relative">
        <select 
          v-model="selectedAgentId" 
          class="w-full bg-transparent text-white px-3 py-2 text-sm font-medium outline-none appearance-none cursor-pointer"
        >
          <option value="" disabled>Select an agent to test...</option>
          <option v-for="agent in agents" :key="agent.id" :value="agent.id">Agent: {{ agent.name }}</option>
        </select>
        <div class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
           <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
        </div>
      </div>
    </div>

    <!-- Main Chat Area -->
    <div class="flex-grow p-4 overflow-y-auto space-y-5 flex flex-col bg-mobile-aurora scrollbar-none pb-6 relative">
      
      <!-- Empty State -->
      <div v-if="messages.length === 0" class="flex-grow flex flex-col items-center justify-center text-center opacity-60">
          <div class="w-20 h-20 rounded-full border-2 border-dashed border-slate-600 flex items-center justify-center mb-6 text-slate-500">
              <svg class="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
          </div>
          <h2 class="text-white font-bold mb-2">Simulate a Conversation</h2>
          <p class="text-slate-400 text-sm max-w-xs leading-relaxed">Type a message below to see how your agent responds to customers without affecting real data.</p>
      </div>

      <!-- Messages -->
      <div v-for="msg in messages" :key="msg.id" class="w-full flex-col flex">
        <div 
          :class="[
            'max-w-[85%] p-4 rounded-3xl shadow-sm text-[15px] leading-relaxed relative',
            msg.role === 'user' ? 'bg-slate-800 text-slate-200 self-end rounded-tr-sm border border-slate-700/50' : 'glass-panel text-white self-start rounded-tl-sm border-indigo-500/30 shadow-indigo-500/5'
          ]"
        >
          <!-- Agent Label Indicator -->
          <div v-if="msg.role !== 'user'" class="absolute -top-3 -left-2 bg-indigo-500 text-white text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full shadow-md">
            Agent
          </div>

          <p class="whitespace-pre-wrap">{{ msg.content }}</p>
          <div class="mt-1 flex justify-end">
            <span class="text-[10px] opacity-50 font-medium">{{ new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</span>
          </div>

        </div>

        <!-- Inline reflection/decision for the LAST agent message -->
        <div v-if="msg.role !== 'user' && latestDecisions.length > 0 && msg === messages[messages.length - 1]" class="mx-2 mt-2 self-start max-w-[85%]">
           <details class="group bg-slate-900/60 border border-slate-700/50 rounded-xl overflow-hidden [&_summary::-webkit-details-marker]:hidden">
             <summary class="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-3 py-2 cursor-pointer flex items-center justify-between hover:bg-slate-800/50 transition-colors">
               <span class="flex items-center gap-1.5 text-indigo-400">
                 <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                 Agent Reflection (Why?)
               </span>
               <svg class="w-4 h-4 transition-transform group-open:rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
             </summary>
             <div class="p-3 border-t border-slate-700/50 text-xs text-slate-400 bg-slate-900/80 space-y-2">
                <div v-for="decision in [latestDecisions[0]]" :key="decision.id">
                  <p class="mb-1"><span class="font-semibold text-slate-300">Action:</span> <span :class="decision.allow_send ? 'text-emerald-400' : 'text-amber-400'">{{ decision.allow_send ? 'Respond' : 'Hold' }}</span></p>
                  <p class="italic leading-relaxed text-[11px] opacity-80">"{{ decision.reason_code }}"</p>
                </div>
             </div>
           </details>
        </div>
      </div>

      <!-- Thinking Indicator -->
      <div v-if="isSending" class="max-w-[85%] glass-panel rounded-3xl rounded-tl-sm px-6 py-4 text-sm self-start flex items-center gap-3 border-indigo-500/30">
        <div class="w-6 h-6 rounded-full bg-indigo-500/20 flex items-center justify-center shrink-0">
          <svg class="w-4 h-4 text-indigo-400 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        </div>
        <span class="text-indigo-300 font-medium text-xs uppercase tracking-widest animate-pulse">Analyzing...</span>
      </div>

      <!-- Spacer -->
      <div class="h-4 shrink-0"></div>
    </div>

    <!-- Composer -->
    <div class="p-3 glass-panel border-t border-slate-700/50 rounded-t-[32px] z-20 pb-safe">
      <div class="flex items-end gap-2 bg-slate-900/50 rounded-3xl border border-slate-700/50 p-2 focus-within:ring-1 focus-within:ring-indigo-500/50 transition-all">
        <textarea 
          v-model="newMessage"
          class="flex-grow bg-transparent p-2 text-sm text-white placeholder-slate-500 outline-none resize-none max-h-32 min-h-[40px] scrollbar-none"
          placeholder="Act as a customer..."
          rows="1"
          @keyup.enter.exact.prevent="sendMessage"
        ></textarea>
        <button 
          @click="sendMessage"
          :disabled="isSending || !newMessage.trim() || !selectedAgentId"
          class="h-10 w-10 shrink-0 rounded-full bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20 disabled:opacity-50 disabled:grayscale transition-all active:scale-95"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5 ml-1"><path d="M3.478 2.404a.75.75 0 00-.926.941l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.404z" /></svg>
        </button>
      </div>
      <p class="text-center text-[9px] text-slate-500 mt-2 font-medium uppercase tracking-widest hidden sm:block">Press Enter to simulate</p>
    </div>
  </div>
</template>

<style scoped>
/* Scoped overrides if needed */
</style>
