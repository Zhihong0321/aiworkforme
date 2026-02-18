<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiSelect from '../components/ui/TuiSelect.vue'
import TuiCard from '../components/ui/TuiCard.vue'

const API_BASE = '/api/v1/playground'

const workspaces = ref([])
const leads = ref([])
const selectedWorkspaceId = ref(null)
const selectedLeadId = ref(null)
const messages = ref([])
const newMessage = ref('')
const isSending = ref(false)
const isLoadingThread = ref(false)
const latestDecisions = ref([])

const fetchWorkspaces = async () => {
    try {
        const res = await fetch(`${API_BASE}/workspaces`)
        workspaces.value = await res.json()
        if (workspaces.value.length > 0) {
            selectedWorkspaceId.value = workspaces.value[0].id
        }
    } catch (e) {
        console.error("Failed to fetch workspaces", e)
    }
}

const fetchLeads = async () => {
    if (!selectedWorkspaceId.value) return
    try {
        const res = await fetch(`${API_BASE}/leads?workspace_id=${selectedWorkspaceId.value}`)
        leads.value = await res.json()
        if (leads.value.length > 0) {
            selectedLeadId.value = leads.value[0].id
        } else {
            selectedLeadId.value = null
            messages.value = []
        }
    } catch (e) {
        console.error("Failed to fetch leads", e)
    }
}

const fetchThread = async () => {
    if (!selectedLeadId.value) return
    isLoadingThread.value = true
    try {
        const res = await fetch(`${API_BASE}/thread/${selectedLeadId.value}`)
        messages.value = await res.json()
    } catch (e) {
        console.error("Failed to fetch thread", e)
    } finally {
        isLoadingThread.value = false
    }
}

const sendMessage = async () => {
    if (!newMessage.value.trim() || !selectedLeadId.value || !selectedWorkspaceId.value) return
    
    const text = newMessage.value
    newMessage.value = ''
    isSending.value = true
    
    try {
        const res = await fetch(`${API_BASE}/chat?lead_id=${selectedLeadId.value}&workspace_id=${selectedWorkspaceId.value}&message=${encodeURIComponent(text)}`, {
            method: 'POST'
        })
        const data = await res.json()
        
        // Refresh thread and decisions
        await fetchThread()
        latestDecisions.value = data.decisions
    } catch (e) {
        console.error("Failed to send message", e)
    } finally {
        isSending.value = false
    }
}

watch(selectedWorkspaceId, fetchLeads)
watch(selectedLeadId, fetchThread)

onMounted(() => {
    fetchWorkspaces()
})

const currentLead = computed(() => leads.value.find(l => l.id === selectedLeadId.value))
const currentWorkspace = computed(() => workspaces.value.find(w => w.id === selectedWorkspaceId.value))

const workspaceOptions = computed(() => workspaces.value.map(w => ({ label: w.name, value: w.id })))
const leadOptions = computed(() => leads.value.map(l => ({ label: `${l.name || 'Lead'} (${l.external_id})`, value: l.id })))

</script>

<template>
    <div class="flex h-[calc(100vh-64px)] overflow-hidden bg-[#0e0e10] text-slate-300">
        <!-- Sidebar: Config -->
        <aside class="w-80 border-r border-white/10 p-6 flex flex-col gap-6 overflow-y-auto">
            <div>
                <h2 class="text-[10px] font-black uppercase tracking-[0.2em] text-white/40 mb-4">System Configuration</h2>
                <div class="space-y-4">
                    <TuiSelect 
                        label="Workspace" 
                        v-model="selectedWorkspaceId" 
                        :options="workspaceOptions"
                        dark
                    />
                    <TuiSelect 
                        label="Active Lead" 
                        v-model="selectedLeadId" 
                        :options="leadOptions"
                        dark
                    />
                </div>
            </div>

            <div v-if="currentLead" class="space-y-4">
                <h2 class="text-[10px] font-black uppercase tracking-[0.2em] text-white/40 mb-2">Lead Context</h2>
                <TuiCard p="3" class="bg-white/5 border-white/10">
                    <div class="space-y-2 text-xs">
                        <div class="flex justify-between">
                            <span class="text-white/40">Stage</span>
                            <TuiBadge variant="info">{{ currentLead.stage }}</TuiBadge>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-white/40">Tags</span>
                            <div class="flex gap-1 flex-wrap justify-end">
                                <TuiBadge v-for="tag in currentLead.tags" :key="tag" size="xs" variant="muted">{{ tag }}</TuiBadge>
                            </div>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-white/40">Tier</span>
                            <TuiBadge :variant="currentWorkspace?.budget_tier === 'RED' ? 'danger' : 'success'">{{ currentWorkspace?.budget_tier }}</TuiBadge>
                        </div>
                    </div>
                </TuiCard>
            </div>

            <div v-if="latestDecisions.length > 0">
                <h2 class="text-[10px] font-black uppercase tracking-[0.2em] text-white/40 mb-2">Latest Decisions</h2>
                <div class="space-y-2">
                    <div v-for="decision in latestDecisions" :key="decision.id" class="p-2 rounded bg-white/5 border border-white/10 text-[10px]">
                        <div class="flex justify-between mb-1">
                            <span :class="decision.allow_send ? 'text-green-500' : 'text-red-500 font-bold'">
                                {{ decision.allow_send ? 'ALLOW' : 'BLOCK' }}
                            </span>
                            <span class="text-white/20">{{ new Date(decision.created_at).toLocaleTimeString() }}</span>
                        </div>
                        <div class="text-white/60 font-mono">{{ decision.reason_code }}</div>
                    </div>
                </div>
            </div>
        </aside>

        <!-- Main: Chat -->
        <main class="flex-1 flex flex-col min-w-0">
            <header class="h-16 border-b border-white/10 px-8 flex items-center justify-between">
                <div>
                   <h1 class="text-sm font-bold text-white uppercase tracking-widest">{{ currentLead?.name || 'Select a Lead' }}</h1>
                   <p class="text-[10px] text-white/40">{{ currentLead?.external_id }}</p>
                </div>
                <div class="flex gap-2">
                    <TuiBadge v-if="isLoadingThread" variant="muted">Syncing...</TuiBadge>
                </div>
            </header>

            <div class="flex-1 overflow-y-auto p-8 flex flex-col gap-4">
                <div v-if="messages.length === 0" class="flex-1 flex items-center justify-center text-white/20 uppercase text-xs tracking-widest italic">
                    No conversion history. Send a message to start.
                </div>
                <div v-for="msg in messages" :key="msg.id" 
                    :class="['max-w-[80%] rounded-2xl px-4 py-3 text-sm flex flex-col gap-1', 
                    msg.role === 'user' ? 'bg-white/10 ml-auto border border-white/10 rounded-tr-none' : 'bg-green-500/10 border border-green-500/20 text-green-100 rounded-tl-none mr-auto']">
                    <span class="text-[9px] uppercase tracking-widest opacity-40 font-bold">
                        {{ msg.role === 'user' ? 'Lead' : 'System Agent' }}
                    </span>
                    <p class="whitespace-pre-wrap leading-relaxed">{{ msg.content }}</p>
                    <span class="text-[8px] opacity-30 self-end">{{ new Date(msg.created_at).toLocaleTimeString() }}</span>
                </div>
                <div v-if="isSending" class="bg-green-500/10 border border-green-500/20 text-green-100/50 rounded-2xl px-4 py-3 text-sm rounded-tl-none mr-auto animate-pulse w-32">
                    Thinking...
                </div>
            </div>

            <footer class="p-8 pt-0">
                <div class="relative group">
                    <textarea 
                        v-model="newMessage"
                        placeholder="Simulate WhatsApp message from lead..."
                        class="w-full bg-white/5 border border-white/10 rounded-2xl px-6 py-4 text-sm text-white focus:outline-none focus:border-green-500/50 transition-all resize-none shadow-2xl"
                        rows="2"
                        @keydown.enter.prevent="sendMessage"
                    ></textarea>
                    <div class="absolute right-4 bottom-4 flex items-center gap-3">
                        <span class="text-[9px] text-white/20 uppercase tracking-widest font-bold">Press Enter to send</span>
                        <TuiButton @click="sendMessage" :loading="isSending" size="sm" class="!rounded-xl shadow-lg">Send</TuiButton>
                    </div>
                </div>
            </footer>
        </main>

        <!-- Inspector (Optional Right Side) -->
        <aside class="w-96 border-l border-white/10 bg-white/[0.02] p-6 hidden lg:flex flex-col gap-6 overflow-y-auto">
             <h2 class="text-[10px] font-black uppercase tracking-[0.2em] text-white/40">Execution Inspector</h2>
             
             <div v-if="latestDecisions.length > 0" class="space-y-6">
                <div v-for="decision in [latestDecisions[0]]" :key="decision.id" class="space-y-4">
                    <div>
                        <p class="text-[9px] font-bold text-white/60 mb-2 uppercase tracking-widest">Policy Trace</p>
                        <TuiCard p="4" class="bg-white/5 border-white/10 font-mono text-[10px]">
                            <pre class="text-green-400 overflow-x-auto">{{ JSON.stringify(decision.rule_trace, null, 2) }}</pre>
                        </TuiCard>
                    </div>
                    
                    <div v-if="decision.next_allowed_at">
                         <p class="text-[9px] font-bold text-white/60 mb-2 uppercase tracking-widest">Next Allowed Turn</p>
                         <p class="text-xs text-white/40">{{ new Date(decision.next_allowed_at).toLocaleString() }}</p>
                    </div>
                </div>
             </div>
             
             <div v-else class="flex-1 flex flex-col items-center justify-center text-center px-4">
                 <div class="w-12 h-12 rounded-full border border-white/10 flex items-center justify-center mb-4">
                     <svg class="w-6 h-6 text-white/10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                         <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                     </svg>
                 </div>
                 <p class="text-xs text-white/20 uppercase tracking-widest font-bold">No decision trace available</p>
                 <p class="text-[10px] text-white/10 mt-2">Send a message to see the internal policy engine in action.</p>
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
