<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { store } from '../store'
import { request } from '../services/api'

// State
const messages = ref([
    {
        id: 'welcome',
        role: 'system',
        content: "Hello! I'm your active Agent. Start typing to test my responses in this safe isolated environment.",
        created_at: new Date().toISOString()
    }
])
const newMessage = ref('')
const isSending = ref(false)
const latestDecisions = ref([])

// Active Testing Lead (Conceptual placeholder for session)
const activeLeadId = ref(null)
const activeWorkspaceId = ref(null)

const fetchThread = async () => {
    // Attempt to get a playground tester lead context
    try {
        const data = await request(`/workspaces/${store.activeWorkspaceId || 1}/leads`) 
        const testerLead = data?.find(l => l.external_id?.startsWith('playground_'))
        
        if (testerLead) {
            activeLeadId.value = testerLead.id
            activeWorkspaceId.value = testerLead.workspace_id
            
            // Try fetching existing thread if backend supports it without 410
            try {
                const threadData = await request(`/playground/thread/${activeLeadId.value}`)
                if (Array.isArray(threadData) && threadData.length > 0) {
                     messages.value = threadData
                }
            } catch (ignore) {}
        }
    } catch (e) {
        // Silent catch for playground provision
    }
}

const scrollToBottom = () => {
    nextTick(() => {
        const d = document.getElementById('playground-scroll-container')
        if (d) d.scrollTop = d.scrollHeight
    })
}

const sendMessage = async () => {
    if (!newMessage.value.trim()) return
    if (!store.activeAgentId) {
        alert("Please select and activate an Agent first!")
        return
    }
    
    const text = newMessage.value
    newMessage.value = ''
    isSending.value = true
    
    // Optimistic UI
    messages.value.push({
        id: Date.now(),
        role: 'user',
        content: text,
        created_at: new Date().toISOString()
    })
    scrollToBottom()

    try {
        const data = await request('/playground/chat', {
            method: 'POST',
            body: JSON.stringify({
                message: text,
                agent_id: store.activeAgentId,
                workspace_id: activeWorkspaceId.value,
                lead_id: activeLeadId.value
            })
        })
        
        if (data.result && data.result.status === 'error') {
            messages.value.push({
                id: Date.now(),
                role: 'system',
                isError: true,
                content: `Chat Error: ${data.result.message}`,
                created_at: new Date().toISOString()
            })
        } else {
             // Let fetchThread pull the latest state or just append the AI response if backend supported raw returns
             await fetchThread() 
        }
        latestDecisions.value = data.decisions || []
    } catch (e) {
        console.error("Failed to send message", e)
        const errMsg = e.detail || e.message || 'Legacy messaging writes are disabled (410).'
        
        // Push a simulated fallback response so UI can be tested despite API deprecation
        setTimeout(() => {
             messages.value.push({
                id: Date.now() + 1,
                role: 'system',
                content: `(API 410 Mock): I process that as a simulated response to "${text}".`,
                created_at: new Date().toISOString()
             })
             
             if(errMsg.includes('disabled') || errMsg.includes('410')) {
                latestDecisions.value = [{
                    allow_send: true,
                    reason_code: "Mock reasoning triggered because playground backend is in refactor phase."
                }]
             } else {
                 messages.value.push({
                    id: Date.now() + 2,
                    role: 'system',
                    isError: true,
                    content: `System Error: ${errMsg}`,
                    created_at: new Date().toISOString()
                })
             }
             scrollToBottom()
             isSending.value = false
        }, 1200)
        return // handled by mock flow
    } 
    
    isSending.value = false
    scrollToBottom()
}

const resetThread = async () => {
    if (!messages.value.length || messages.value.length === 1) return
    messages.value = [messages.value[0]] // Keep welcome message
    latestDecisions.value = []
    
    try {
        if (activeLeadId.value) {
            await request(`/playground/thread/${activeLeadId.value}/reset`, { method: 'POST' })
        }
    } catch (e) {
        // Ignored, might be disabled
    }
}

onMounted(() => {
    fetchThread()
})

watch(() => store.activeAgentId, () => {
    resetThread() // Reset playground when switching agents
})
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-64px)] w-full max-w-md mx-auto relative text-slate-900 dark:text-slate-100 bg-background-light dark:bg-background-dark overflow-hidden">
    
    <!-- Active Agent Required -->
    <div v-if="!store.activeAgentId" class="flex flex-col items-center justify-center flex-1 p-6 text-center z-10">
        <span class="material-symbols-outlined text-6xl text-slate-300 dark:text-slate-700 mb-4">sports_esports</span>
        <h3 class="text-lg font-bold">No Agent Linked</h3>
        <p class="text-sm text-slate-500 mt-2">Please select an agent from the sidebar drawer to test its behavior in the Playground.</p>
    </div>

    <!-- Playground Container -->
    <template v-else>
        <!-- TopAppBar -->
        <header class="flex items-center justify-between bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 p-4 shrink-0 shadow-sm z-10 relative">
            
            <div class="flex items-center gap-3">
                <div class="size-10 rounded-xl bg-primary/20 flex items-center justify-center text-primary relative overflow-hidden backdrop-blur-sm border border-primary/20">
                    <span class="absolute inset-0 bg-primary/10 blur-xl"></span>
                    <span class="material-symbols-outlined relative z-10 text-xl">biotech</span>
                </div>
                
                <div class="flex flex-col text-left">
                    <h2 class="text-slate-900 dark:text-slate-100 text-base font-bold leading-tight truncate">Test Lab</h2>
                    <div class="flex items-center gap-1.5 mt-0.5">
                        <span class="size-1.5 bg-primary rounded-full animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]"></span>
                        <span class="text-primary text-[10px] font-bold uppercase tracking-wider">Safe Zone</span>
                    </div>
                </div>
            </div>
            
            <button @click="resetThread" v-if="messages.length > 1" class="h-8 px-3 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 active:scale-95 transition-all text-[10px] font-bold uppercase tracking-wider">
                Reset
            </button>
        </header>

        <!-- Main Chat Content -->
        <main id="playground-scroll-container" class="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth bg-slate-50 dark:bg-slate-900/50">
            
            <div class="flex flex-col items-center py-2 opacity-50">
                <span class="text-slate-400 dark:text-slate-500 text-[10px] font-semibold uppercase tracking-widest px-3 py-1 bg-slate-200 dark:bg-slate-800 rounded-full">Simulated Environment</span>
            </div>

            <div v-for="(msg, index) in messages" :key="msg.id || index" class="w-full flex-col flex">
                
                <!-- System/AI Bubble -->
                <div v-if="msg.role !== 'user'" class="flex items-start gap-3 w-full animate-in fade-in duration-300">
                    <div class="bg-primary/10 rounded-full size-10 shrink-0 flex items-center justify-center text-primary border border-primary/20 shadow-sm relative overflow-hidden">
                        <span class="absolute inset-0 bg-primary/5 blur-md"></span>
                        <span class="material-symbols-outlined text-lg relative z-10">smart_toy</span>
                    </div>
                    
                    <div class="flex flex-1 flex-col gap-1 items-start max-w-[85%]">
                        <div class="flex items-center gap-2">
                            <p class="text-slate-500 dark:text-slate-400 text-[11px] font-bold uppercase tracking-wider ml-1">AI Assistant</p>
                            <span v-if="msg.isError" class="text-[10px] bg-red-500/20 text-red-500 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider border border-red-500/20">Error</span>
                        </div>
                        
                        <div 
                            class="text-sm font-normal leading-relaxed rounded-2xl rounded-tl-none px-4 py-3 shadow-sm"
                            :class="msg.isError ? 'bg-red-50 text-red-700 border border-red-200 dark:bg-red-900/20 dark:border-red-500/30' : 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 border border-slate-200 dark:border-slate-700'"
                        >
                            <p class="whitespace-pre-wrap">{{ msg.content }}</p>
                        </div>

                        <!-- Chain of Thought reflection for the latest real AI message -->
                        <div v-if="latestDecisions.length > 0 && index === messages.length - 1 && !msg.isError" class="mt-2 w-full">
                            <details class="group bg-blue-50/50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-800/50 rounded-xl overflow-hidden [&_summary::-webkit-details-marker]:hidden w-full max-w-[280px]">
                                <summary class="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider px-3 py-2 cursor-pointer flex items-center justify-between hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors select-none">
                                    <span class="flex items-center gap-1.5 text-primary">
                                        <span class="material-symbols-outlined text-[14px]">psychology</span>
                                        Chain of Thought
                                    </span>
                                    <span class="material-symbols-outlined text-[16px] transition-transform group-open:rotate-180">expand_more</span>
                                </summary>
                                <div class="p-3 border-t border-blue-100 dark:border-blue-800/50 text-xs text-slate-600 dark:text-slate-400 space-y-2 bg-white/50 dark:bg-slate-900/50">
                                    <div v-for="(decision, dIdx) in latestDecisions.slice(0, 1)" :key="dIdx">
                                        <p class="mb-1.5 font-mono text-[10px]">
                                            Status: 
                                            <span class="px-1.5 py-0.5 rounded-sm ml-1 text-[9px] font-bold" :class="decision.allow_send ? 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-400' : 'bg-amber-500/20 text-amber-600 dark:text-amber-400'">
                                                {{ decision.allow_send ? 'ALLOWED' : 'BLOCKED' }}
                                            </span>
                                        </p>
                                        <p class="italic leading-relaxed opacity-90 font-mono text-[10px] border-l-2 border-primary/30 pl-2">"{{ decision.reason_code }}"</p>
                                    </div>
                                </div>
                            </details>
                        </div>
                    </div>
                </div>

                <!-- User Bubble -->
                <div v-else class="flex items-start gap-3 justify-end w-full animate-in fade-in duration-300">
                    <div class="flex flex-1 flex-col gap-1 items-end max-w-[85%]">
                        <p class="text-slate-500 dark:text-slate-400 text-[11px] font-bold uppercase tracking-wider mr-1">You</p>
                        <div class="text-sm font-normal leading-relaxed rounded-2xl rounded-tr-none px-4 py-3 bg-primary text-white shadow-md shadow-primary/20">
                            <p class="whitespace-pre-wrap">{{ msg.content }}</p>
                        </div>
                        <span class="text-[9px] font-medium text-slate-400 opacity-70 block mt-0.5">{{ new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</span>
                    </div>
                    
                    <div class="bg-slate-200 dark:bg-slate-700 rounded-full size-10 shrink-0 flex items-center justify-center text-slate-600 dark:text-slate-300 border border-slate-300 dark:border-slate-600 relative overflow-hidden">
                        <span class="material-symbols-outlined text-xl relative z-10">person</span>
                    </div>
                </div>
            </div>

            <!-- Loader Indicator -->
            <div v-if="isSending" class="flex items-start gap-3 w-full animate-in fade-in duration-200">
                <div class="bg-primary/5 rounded-full size-10 shrink-0 flex items-center justify-center text-primary/50 border border-primary/10">
                    <span class="material-symbols-outlined text-lg">smart_toy</span>
                </div>
                <div class="flex flex-1 flex-col gap-1 items-start max-w-[85%]">
                    <div class="bg-white dark:bg-slate-800 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm border border-slate-200 dark:border-slate-700 flex items-center gap-2">
                        <div class="flex gap-1">
                            <div class="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.3s]"></div>
                            <div class="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.15s]"></div>
                            <div class="w-1.5 h-1.5 rounded-full bg-primary animate-bounce"></div>
                        </div>
                    </div>
                </div>
            </div>
            
        </main>

        <!-- Bottom Input Bar -->
        <footer class="bg-white dark:bg-slate-900 p-4 border-t border-slate-200 dark:border-slate-800 shrink-0 pb-safe z-10 relative">
            <div class="flex items-center gap-3 bg-slate-100 dark:bg-slate-800 focus-within:ring-2 focus-within:ring-primary/50 transition-shadow transition-all rounded-full p-1.5 border border-slate-200 dark:border-slate-700">
                
                <input 
                    v-model="newMessage"
                    @keyup.enter.exact.prevent="sendMessage"
                    :disabled="isSending"
                    class="flex-1 bg-transparent border-none focus:ring-0 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 text-sm px-3 outline-none disabled:opacity-50" 
                    placeholder="Type a scenario parameter or message..." 
                    type="text"
                />
                
                <button 
                    @click="sendMessage"
                    :disabled="isSending || !newMessage.trim()"
                    class="bg-primary text-white size-10 rounded-full flex items-center justify-center shadow-lg shadow-primary/30 hover:bg-primary/90 transition-all disabled:opacity-50 disabled:grayscale shrink-0"
                    :class="{'active:scale-90': newMessage.trim()}"
                >
                    <span v-if="isSending" class="material-symbols-outlined text-sm animate-spin">sync</span>
                    <span v-else class="material-symbols-outlined text-sm">send</span>
                </button>
            </div>
        </footer>
    </template>
  </div>
</template>

<style scoped>
/* Optional: Make scroll behavior smooth */
#playground-scroll-container {
    scroll-behavior: smooth;
}
</style>
