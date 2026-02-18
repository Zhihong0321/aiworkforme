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
    <div class="flex h-[calc(100vh-64px)] overflow-hidden bg-[#0a0a0c] text-slate-300">
        <!-- Main: Chat -->
        <main class="flex-1 flex flex-col min-w-0 border-r border-white/5">
            <header class="h-16 border-b border-white/5 px-8 flex items-center justify-between bg-white/[0.02]">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-green-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-green-500/20">
                        <svg class="w-5 h-5 text-[#0a0a0c]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                    </div>
                    <div>
                       <h1 class="text-sm font-bold text-white uppercase tracking-widest">{{ currentAgent?.name || 'Select Agent' }}</h1>
                       <div class="flex items-center gap-1.5">
                           <span class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                           <p class="text-[10px] text-white/40 font-medium">Ready to test</p>
                       </div>
                    </div>
                </div>
                <div class="hidden md:flex gap-4 items-center">
                    <TuiBadge variant="success" size="sm" class="!rounded-full px-4 border-green-500/20 bg-green-500/5 text-green-400">ONLINE</TuiBadge>
                </div>
            </header>

            <div class="flex-1 overflow-y-auto p-8 flex flex-col gap-6 max-w-4xl mx-auto w-full">
                <div v-if="messages.length === 0" class="flex-1 flex flex-col items-center justify-center text-center">
                    <div class="w-20 h-20 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center mb-6">
                        <svg class="w-10 h-10 text-white/20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                    </div>
                    <h2 class="text-white font-bold mb-2">Start a conversation</h2>
                    <p class="text-white/40 text-sm max-w-xs">Simulate a message from a lead to see how your agent responds.</p>
                </div>
                
                <div v-for="msg in messages" :key="msg.id" 
                    :class="['max-w-[85%] rounded-[2rem] px-6 py-4 text-sm flex flex-col gap-1 shadow-sm', 
                    msg.role === 'user' ? 'bg-white/5 ml-auto border border-white/10 rounded-tr-sm text-slate-200' : 'bg-green-500/10 border border-green-500/10 text-green-50 text-slate-200 rounded-tl-sm']">
                    <p class="whitespace-pre-wrap leading-relaxed">{{ msg.content }}</p>
                    <span class="text-[8px] opacity-20 self-end mt-1">{{ new Date(msg.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}</span>
                </div>
                
                <div v-if="isSending" class="bg-green-500/10 border border-green-500/10 text-green-100/50 rounded-[2rem] rounded-tl-sm px-6 py-4 text-sm mr-auto animate-pulse flex items-center gap-2 shadow-sm">
                    <div class="flex gap-1">
                        <span class="w-1 h-1 rounded-full bg-green-500/40 animate-bounce"></span>
                        <span class="w-1 h-1 rounded-full bg-green-500/40 animate-bounce [animation-delay:0.2s]"></span>
                        <span class="w-1 h-1 rounded-full bg-green-500/40 animate-bounce [animation-delay:0.4s]"></span>
                    </div>
                    <span>Agent is thinking...</span>
                </div>
            </div>

            <footer class="p-8 pt-4">
                <div class="max-w-4xl mx-auto relative">
                    <textarea 
                        v-model="newMessage"
                        placeholder="Type a message as if you were the customer..."
                        class="w-full bg-white/5 border border-white/10 rounded-[2rem] px-8 py-5 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-green-500/30 focus:bg-white/[0.07] transition-all resize-none shadow-2xl"
                        rows="2"
                        @keydown.enter.prevent="sendMessage"
                    ></textarea>
                    <div class="absolute right-6 bottom-5 flex items-center gap-4">
                        <span class="text-[9px] text-white/10 uppercase tracking-[0.2em] font-black hidden sm:block">Press Enter</span>
                        <button @click="sendMessage" :disabled="isSending" 
                            class="bg-green-500 hover:bg-green-400 disabled:opacity-50 text-[#0a0a0c] font-black uppercase text-[10px] tracking-widest px-6 py-2.5 rounded-full transition-all shadow-lg shadow-green-500/20 active:scale-95">
                            Send
                        </button>
                    </div>
                </div>
            </footer>
        </main>

        <aside class="w-96 bg-white/[0.01] p-8 hidden xl:flex flex-col gap-8 overflow-y-auto border-l border-white/5">
             <div class="space-y-6">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-[10px] font-black uppercase tracking-[0.2em] text-white/20">Chat Configuration</h2>
                    <TuiButton 
                        v-if="messages.length > 0"
                        variant="ghost" 
                        size="sm" 
                        class="!text-[9px] !px-2 !py-1 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                        @click="resetThread"
                    >
                        RESET
                    </TuiButton>
                </div>
                <TuiSelect 
                    label="Test Agent" 
                    v-model="selectedAgentId" 
                    :options="agentOptions"
                    dark
                />
             </div>

             <div class="pt-8 border-t border-white/5">
                <h2 class="text-[10px] font-black uppercase tracking-[0.2em] text-white/20 mb-6">Agent Reflection</h2>
                
                <div v-if="latestDecisions.length > 0" class="space-y-8">
                   <div v-for="decision in [latestDecisions[0]]" :key="decision.id" class="space-y-6">
                       <div class="p-6 rounded-3xl bg-white/5 border border-white/10 shadow-sm relative overflow-hidden group">
                           <div class="absolute top-0 left-0 w-1 h-full bg-green-500/30 group-hover:bg-green-500/60 transition-colors"></div>
                           <p class="text-[9px] font-bold text-white/40 mb-3 uppercase tracking-widest">Decision Outcome</p>
                           <div class="flex items-center gap-3">
                               <div :class="['w-2 h-2 rounded-full', decision.allow_send ? 'bg-green-500 shadow-lg shadow-green-500/50' : 'bg-red-500 shadow-lg shadow-red-500/50']"></div>
                               <span :class="['text-xs font-black uppercase tracking-widest', decision.allow_send ? 'text-green-500' : 'text-red-500']">
                                   {{ decision.allow_send ? 'Ready to Respond' : 'Paused for Review' }}
                               </span>
                           </div>
                           <p class="mt-4 text-[11px] leading-relaxed text-white/60 italic">
                               "{{ decision.reason_code }}"
                           </p>
                       </div>

                       <div class="space-y-4">
                           <p class="text-[9px] font-bold text-white/20 mb-2 uppercase tracking-widest">Internal Context</p>
                           <div class="p-5 rounded-2xl bg-white/[0.02] border border-white/5 text-[10px] space-y-3">
                               <div class="flex justify-between items-center">
                                   <span class="text-white/30 uppercase tracking-tighter font-medium">Confidence Score</span>
                                   <span class="text-white/80 font-mono">HIGH</span>
                               </div>
                               <div class="flex justify-between items-center">
                                   <span class="text-white/30 uppercase tracking-tighter font-medium">Policy Check</span>
                                   <span class="text-green-500/80 font-mono">PASSED</span>
                               </div>
                           </div>
                       </div>
                   </div>
                </div>
                
                <div v-else class="flex-1 flex flex-col items-center justify-center text-center py-20 opacity-40">
                    <div class="w-12 h-12 rounded-full border border-white/10 flex items-center justify-center mb-4">
                        <svg class="w-6 h-6 text-white/20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.364-6.364l-.707-.707M6.343 17.657l-.707.707m12.728 0l-.707-.707M12 7a5 5 0 015 5 5 5 0 01-5 5 5 5 0 01-5-5 5 5 0 015-5z" />
                        </svg>
                    </div>
                    <p class="text-[10px] text-white/40 uppercase tracking-widest font-black">Waiting for insight</p>
                </div>
             </div>
        </aside>
    </div>
</template>

<style scoped>
/* Custom scrollbar for dark theme */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
