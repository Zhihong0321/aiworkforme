<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { store } from '../store'
import { request } from '../services/api'

// State
const threads = ref([])
const messages = ref([])
const activeThread = ref(null) // Holds selected thread object
const isLoadingList = ref(false)
const isLoadingChat = ref(false)
const composer = ref('')
const activeTab = ref('all') // 'all', 'unread', 'archived'

// Fetch List
const fetchThreads = async () => {
  if (!store.activeAgentId) {
    threads.value = []
    return
  }
  isLoadingList.value = true
  try {
    const data = await request(`/agents/${store.activeAgentId}/ai-crm/threads`)
    if (Array.isArray(data)) {
        threads.value = data
    }
  } catch (e) {
    console.error('Failed to fetch threads:', e)
  } finally {
    isLoadingList.value = false
  }
}

// Derived Filters
const filteredThreads = computed(() => {
    if (activeTab.value === 'all') return threads.value
    if (activeTab.value === 'unread') return threads.value.filter(t => t.pending_scan || t.status === 'NEEDS_REVIEW')
    if (activeTab.value === 'archived') return threads.value.filter(t => t.status === 'ARCHIVED')
    return threads.value
})

// Avatar text helper
const getAvatarText = (name) => {
    if (!name) return '?'
    return name.substring(0, 2).toUpperCase()
}

// Fetch Messages
const openChat = async (thread) => {
  activeThread.value = thread
  isLoadingChat.value = true
  messages.value = []
  
  try {
    // Reusing the same endpoint used in Leads.vue for WhatsApp threads
    const data = await request(`/messaging/leads/${thread.lead_id}/thread?channel=whatsapp`)
    messages.value = Array.isArray(data?.messages) ? data.messages : []
  } catch (e) {
    console.error('Failed to load conversation transcript:', e)
  } finally {
    isLoadingChat.value = false
  }
}

// Send Message
const sendMessage = async () => {
    // This serves as a conceptual UI placeholder based on designs since human takeover logic might need specific backend hookups
    if (!composer.value.trim() || !activeThread.value) return
    console.warn(`Dispatching manual message to Lead ${activeThread.value.lead_id}: ${composer.value}`)
    
    // Simulate optimistic UI update
    messages.value.push({
        id: Date.now(),
        direction: 'outbound',
        text_content: composer.value,
        created_at: new Date().toISOString()
    })
    
    composer.value = ''
    setTimeout(() => {
        const d = document.getElementById('chat-scroll-container')
        if (d) d.scrollTop = d.scrollHeight
    }, 50)
}

onMounted(() => {
  if (store.activeAgentId) fetchThreads()
})

watch(() => store.activeAgentId, () => {
    activeThread.value = null
    fetchThreads()
})
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-64px)] w-full max-w-md mx-auto relative text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-900 overflow-hidden">
    
    <!-- ==================== LEAD LIST VIEW ==================== -->
    <div v-if="!activeThread" class="flex flex-col h-full w-full animate-in fade-in duration-200">
      
      <!-- Missing Agent Fallback -->
      <div v-if="!store.activeAgentId" class="flex flex-col items-center justify-center flex-1 p-6 text-center">
        <span class="material-symbols-outlined text-6xl text-slate-300 dark:text-slate-700 mb-4">forum</span>
        <h3 class="text-lg font-bold">No Agent Connected</h3>
        <p class="text-sm text-slate-500 mt-2">Connect an agent to view active inbound conversations and AI CRM threads.</p>
      </div>

      <template v-else>
          <!-- Navigation Tabs -->
          <nav class="flex border-b border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md sticky top-0 z-10 shrink-0">
              <button 
                  v-for="tab in [{id: 'all', label: 'All'}, {id: 'unread', label: 'Unread'}, {id: 'archived', label: 'Archived'}]" 
                  :key="tab.id"
                  @click="activeTab = tab.id"
                  class="flex-1 flex flex-col items-center justify-center pt-3 pb-2 border-b-2 transition-colors"
                  :class="activeTab === tab.id ? 'border-primary text-primary' : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700'"
              >
                  <span class="text-sm font-semibold uppercase tracking-wider">{{ tab.label }}</span>
              </button>
          </nav>

          <!-- Main Conversation List -->
          <main class="flex-1 overflow-y-auto scrollbar-none pb-24">
              
              <div v-if="isLoadingList" class="flex justify-center p-8">
                  <span class="material-symbols-outlined animate-spin text-primary">sync</span>
              </div>
              
              <div v-else-if="filteredThreads.length === 0" class="flex flex-col items-center justify-center h-full p-8 text-center text-slate-500">
                  <span class="material-symbols-outlined text-4xl mb-2 opacity-50">chat_bubble</span>
                  <p class="text-sm font-medium">No conversations found.</p>
              </div>

              <!-- List Items -->
              <div 
                  v-else 
                  v-for="thread in filteredThreads" 
                  :key="thread.thread_id"
                  @click="openChat(thread)"
                  class="flex items-center gap-4 px-4 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer border-b border-slate-100 dark:border-slate-800/50"
              >
                  <!-- Avatar -->
                  <div class="relative shrink-0">
                      <div class="size-14 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-lg border-2 border-primary/20">
                          {{ getAvatarText(thread.lead_name) }}
                      </div>
                      <div v-if="thread.pending_scan || thread.status === 'NEEDS_REVIEW'" class="absolute bottom-0 right-0 size-3.5 bg-green-500 border-2 border-white dark:border-slate-900 rounded-full"></div>
                  </div>
                  
                  <div class="flex-1 min-w-0">
                      <div class="flex justify-between items-baseline mb-0.5">
                          <h3 class="text-base font-bold text-slate-900 dark:text-slate-100 truncate">{{ thread.lead_name || thread.lead_external_id || 'Unknown' }}</h3>
                          <span class="text-xs font-semibold" :class="thread.pending_scan ? 'text-primary' : 'text-slate-500'">
                              {{ thread.last_message_at ? new Date(thread.last_message_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'No Activity' }}
                          </span>
                      </div>
                      
                      <div class="flex justify-between items-start">
                          <p class="text-sm font-medium text-slate-600 dark:text-slate-400 line-clamp-1">
                              {{ thread.last_message_preview || 'New thread initiated.' }}
                          </p>
                          <!-- Notification Badge -->
                          <span v-if="thread.pending_scan" class="ml-2 flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-primary text-white text-[10px] font-bold">New</span>
                          <span v-else-if="thread.status === 'ARCHIVED'" class="ml-2 material-symbols-outlined text-sm text-slate-400">inventory_2</span>
                          <span v-else class="ml-2 material-symbols-outlined text-sm text-slate-400">done_all</span>
                      </div>
                  </div>
              </div>
          </main>

          <!-- Floating Action Button -->
          <button class="absolute bottom-6 right-6 size-14 bg-primary text-white rounded-full shadow-lg shadow-primary/30 flex items-center justify-center hover:scale-105 active:scale-95 transition-transform z-20">
              <span class="material-symbols-outlined text-2xl">add_comment</span>
          </button>
      </template>
    </div>

    <!-- ==================== CHAT VIEW (SLIDING OVERLAY) ==================== -->
    <div 
        v-if="activeThread" 
        class="absolute inset-0 z-30 flex flex-col bg-background-light dark:bg-background-dark animate-in slide-in-from-right duration-200"
    >
      <!-- TopAppBar -->
      <header class="flex items-center justify-between bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 p-4 shrink-0 shadow-sm z-10">
          <button @click="activeThread = null" class="flex size-10 items-center justify-center rounded-full text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors active:scale-95">
              <span class="material-symbols-outlined">arrow_back</span>
          </button>
          
          <div class="flex flex-col items-center text-center max-w-[60%]">
              <h2 class="text-slate-900 dark:text-slate-100 text-base font-bold leading-tight truncate w-full">{{ activeThread.lead_name || activeThread.lead_external_id }}</h2>
              <div class="flex items-center gap-1.5 mt-0.5">
                  <span class="size-1.5 bg-emerald-500 rounded-full animate-pulse"></span>
                  <span class="text-slate-500 dark:text-slate-400 text-[10px] font-medium uppercase tracking-wider">
                      {{ activeThread.status === 'ARCHIVED' ? 'Archived' : 'Active Channel' }}
                  </span>
              </div>
          </div>
          
          <button class="flex items-center justify-center rounded-full size-10 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
              <span class="material-symbols-outlined">more_vert</span>
          </button>
      </header>
      
      <!-- Chat Content -->
      <main id="chat-scroll-container" class="flex-1 overflow-y-auto p-4 space-y-6 bg-slate-50 dark:bg-slate-900/50">
          
          <div v-if="isLoadingChat" class="flex flex-col items-center justify-center py-10 opacity-70">
              <span class="material-symbols-outlined animate-spin text-primary text-3xl mb-2">sync</span>
              <span class="text-xs uppercase tracking-widest font-bold">Syncing Transcript...</span>
          </div>
          
          <div v-else-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center p-6 text-slate-500">
              <span class="material-symbols-outlined text-4xl mb-3 opacity-30">history</span>
              <p class="text-sm font-medium">No conversational history downloaded yet.</p>
          </div>
          
          <template v-else>
              <!-- Timeline Marker -->
              <div class="flex flex-col items-center py-2">
                  <span class="text-slate-400 dark:text-slate-500 text-[10px] font-semibold uppercase tracking-widest px-3 py-1 bg-slate-200/50 dark:bg-slate-800 rounded-full">Transcript History</span>
              </div>

              <!-- Messages List -->
              <div 
                  v-for="(msg, index) in messages" 
                  :key="msg.id || index"
                  class="flex items-end gap-3 max-w-[85%]"
                  :class="msg.direction === 'outbound' ? 'justify-end ml-auto' : 'justify-start mr-auto'"
              >
                  <!-- Inbound Avatar -->
                  <div v-if="msg.direction === 'inbound'" class="bg-primary/10 flex items-center justify-center rounded-full size-8 shrink-0 border border-primary/20 text-primary text-xs font-bold">
                      {{ getAvatarText(activeThread.lead_name) }}
                  </div>
                  
                  <!-- Bubble Stack -->
                  <div class="flex flex-col gap-1" :class="msg.direction === 'outbound' ? 'items-end' : 'items-start'">
                      
                      <!-- AI Sender Tag (Outbound) -->
                      <div v-if="msg.direction === 'outbound'" class="flex items-center gap-1 mb-0.5 mr-1 text-primary opacity-80">
                          <span class="material-symbols-outlined text-[12px]">smart_toy</span>
                          <p class="text-[9px] font-bold uppercase tracking-widest">Agent System</p>
                      </div>
                      
                      <!-- Main Label (Inbound) -->
                      <p v-if="msg.direction === 'inbound'" class="text-slate-500 dark:text-slate-400 text-[10px] font-medium ml-1">
                          {{ activeThread.lead_name || 'Customer' }}
                      </p>

                      <!-- Bubble payload -->
                      <div 
                          class="text-sm font-normal leading-relaxed rounded-2xl px-4 py-2.5 shadow-sm break-words relative"
                          :class="[
                              msg.direction === 'outbound' 
                                  ? 'rounded-br-none bg-primary text-white shadow-primary/20 border border-primary/50' 
                                  : 'rounded-bl-none bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700'
                          ]"
                      >
                          <p class="whitespace-pre-wrap">{{ msg.text_content || msg.content || '(Attachment Layout TBD)' }}</p>
                          <div 
                              class="text-[9px] mt-1 text-right block" 
                              :class="msg.direction === 'outbound' ? 'text-white/70' : 'text-slate-400'"
                          >
                              {{ new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}
                          </div>
                      </div>
                  </div>

                  <!-- Outbound Avatar / Bolt -->
                  <div v-if="msg.direction === 'outbound'" class="bg-primary flex items-center justify-center rounded-full size-8 shrink-0 border-2 border-primary/20 shadow-sm">
                      <span class="material-symbols-outlined text-white text-sm">bolt</span>
                  </div>
              </div>
          </template>
      </main>

      <!-- Bottom Action & Input -->
      <footer class="bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 p-4 space-y-3 shrink-0 pb-safe">
          
          <!-- Take Over Prompt Context (Mockup visual) -->
          <div v-if="activeThread.status !== 'ARCHIVED'" class="flex items-center justify-between bg-primary/5 dark:bg-primary/10 rounded-xl px-4 py-2 border border-primary/10">
              <div class="flex items-center gap-2">
                  <span class="material-symbols-outlined text-primary text-sm animate-pulse">auto_awesome</span>
                  <span class="text-xs font-semibold text-primary">AI is handling this lead</span>
              </div>
              <button class="text-[10px] font-bold text-white bg-primary px-3 py-1.5 rounded-lg shadow-sm hover:bg-primary/90 transition-all active:scale-95 uppercase tracking-wider">
                  Take Over
              </button>
          </div>
          
          <!-- Input Bar -->
          <div class="flex items-center gap-2 bg-slate-100 dark:bg-slate-800 rounded-full p-1 focus-within:ring-2 focus-within:ring-primary/50 transition-shadow transition-all">
              <button class="flex items-center justify-center size-10 shrink-0 rounded-full text-slate-400 dark:text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
                  <span class="material-symbols-outlined">add_circle</span>
              </button>
              
              <div class="flex-1 relative">
                  <input 
                      v-model="composer"
                      @keyup.enter="sendMessage"
                      class="w-full bg-transparent border-none py-2 px-2 text-sm focus:ring-0 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 outline-none" 
                      placeholder="Type a message..." 
                      type="text"
                  />
              </div>
              
              <button 
                  @click="sendMessage"
                  :disabled="!composer.trim()"
                  class="flex items-center justify-center size-10 shrink-0 rounded-full text-white shadow-sm transition-transform bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:grayscale"
                  :class="{'active:scale-90': composer.trim()}"
              >
                  <span class="material-symbols-outlined text-sm">send</span>
              </button>
          </div>
      </footer>
    </div>
  </div>
</template>

<style scoped>
/* Optional: Make specific thread transition slightly smoother */
.slide-in-from-right {
  animation: slideInFromRight 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes slideInFromRight {
  from {
    transform: translateX(100%);
    opacity: 0.5;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
</style>
