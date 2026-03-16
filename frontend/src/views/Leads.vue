<script setup>
import { onMounted, ref, watch, computed } from 'vue'
import { store } from '../store'
import { request } from '../services/api'
import TuiInput from '../components/ui/TuiInput.vue'

const leads = ref([])
const isLoading = ref(false)

// UI State
const activeTab = ref('all') // 'all', 'working', 'on_hold', 'closed'
const isAddingForm = ref(false)
const chatOpen = ref(false)

// Action state
const isCreating = ref(false)
const createError = ref('')
const actionError = ref('')
const actionMessage = ref('')
const processingLeadId = ref(null)

// New Lead Form
const newLeadName = ref('')
const newLeadExternalId = ref('')

// Chat Viewer
const chatLoading = ref(false)
const chatError = ref('')
const chatLead = ref(null)
const chatMessages = ref([])

const fetchLeads = async () => {
  if (!store.activeAgentId) {
    leads.value = []
    return
  }
  isLoading.value = true
  try {
    const data = await request(`/agents/${store.activeAgentId}/leads`)
    leads.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('Failed to fetch leads', e)
  } finally {
    isLoading.value = false
  }
}

const getModeLabel = (lead) => {
  const tags = Array.isArray(lead.tags) ? lead.tags : []
  if (tags.includes('WORKING')) return 'working'
  if (tags.includes('ON_HOLD')) return 'on_hold'
  return 'on_hold' // Default
}

// Computed lists based on tab
const filteredLeads = computed(() => {
  if (activeTab.value === 'all') return leads.value
  if (activeTab.value === 'closed') {
      return leads.value.filter(l => l.stage === 'CLOSED_LOST' || l.stage === 'OUTCOME_PURCHASE' || l.stage === 'OUTCOME_APPOINTMENT')
  }
  return leads.value.filter(l => {
      // Don't show closed items in active working tabs
      if (l.stage === 'CLOSED_LOST' || l.stage === 'OUTCOME_PURCHASE' || l.stage === 'OUTCOME_APPOINTMENT') return false;
      return getModeLabel(l) === activeTab.value
  })
})

const getFollowUpText = (lead) => {
    if (!lead.next_followup_at) return 'No follow-up scheduled'
    const now = new Date()
    const next = new Date(lead.next_followup_at)
    const diffMs = next - now
    if (diffMs < 0) return 'Overdue'
    
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    if (diffHours < 1) return 'Within an hour'
    if (diffHours < 24) return `In ${diffHours} hours`
    const diffDays = Math.floor(diffHours / 24)
    if (diffDays === 1) return 'Tomorrow'
    return `In ${diffDays} days`
}

const createLead = async () => {
  createError.value = ''
  if (!store.activeAgentId) {
    createError.value = 'No active agent selected.'
    return
  }
  if (!newLeadExternalId.value.trim()) {
    createError.value = 'Phone / external ID is required.'
    return
  }

  isCreating.value = true
  try {
    await request(`/agents/${store.activeAgentId}/leads`, {
      method: 'POST',
      body: JSON.stringify({
        agent_id: Number(store.activeAgentId),
        external_id: newLeadExternalId.value.trim(),
        name: newLeadName.value.trim() || null,
        stage: 'NEW'
      })
    })
    newLeadName.value = ''
    newLeadExternalId.value = ''
    isAddingForm.value = false
    await fetchLeads()
  } catch (e) {
    createError.value = e.message || 'Failed to create lead'
  } finally {
    isCreating.value = false
  }
}

const setLeadMode = async (lead, mode) => {
  actionError.value = ''
  actionMessage.value = ''
  processingLeadId.value = lead.id
  try {
    if (mode === 'working') {
      await request(`/messaging/leads/${lead.id}/start-work`, {
        method: 'POST',
        body: JSON.stringify({
          channel: 'whatsapp',
          channel_session_id: store.activeAgent?.preferred_channel_session_id || null,
        })
      })
      actionMessage.value = `Work started on ${lead.name || lead.external_id}.`
    } else {
      await request(`/leads/${lead.id}/mode`, {
        method: 'POST',
        body: JSON.stringify({ mode })
      })
      actionMessage.value = `${lead.name || lead.external_id} placed on hold.`
    }
    await fetchLeads()
  } catch (e) {
    actionError.value = e.message || 'Failed to update mode'
  } finally {
    processingLeadId.value = null
    setTimeout(() => { actionMessage.value = ''; actionError.value = '' }, 3000)
  }
}

const reviewLeadChat = async (lead) => {
  chatOpen.value = true
  chatLoading.value = true
  chatError.value = ''
  chatLead.value = lead
  chatMessages.value = []
  try {
    const data = await request(`/messaging/leads/${lead.id}/thread?channel=whatsapp`)
    chatMessages.value = Array.isArray(data?.messages) ? data.messages : []
  } catch (e) {
    chatError.value = e.message || 'Failed to load conversation'
  } finally {
    chatLoading.value = false
  }
}

onMounted(() => {
  if (store.activeAgentId) fetchLeads()
})

watch(() => store.activeAgentId, fetchLeads)
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-64px)] w-full max-w-md mx-auto relative text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-900">
    
    <!-- Action Toast -->
    <div v-if="actionMessage || actionError" class="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 px-4 py-2 rounded-full shadow-lg text-sm font-semibold flex items-center gap-2 animate-in slide-in-from-top-2" :class="actionError ? 'bg-red-500 text-white' : 'bg-emerald-500 text-white'">
        <span class="material-symbols-outlined text-sm">{{ actionError ? 'error' : 'check_circle' }}</span>
        {{ actionError || actionMessage }}
    </div>

    <!-- Active Agent Required -->
    <div v-if="!store.activeAgentId" class="flex flex-col items-center justify-center flex-1 p-6 text-center">
        <span class="material-symbols-outlined text-6xl text-slate-300 dark:text-slate-700 mb-4">contacts</span>
        <h3 class="text-lg font-bold">No Agent Linked</h3>
        <p class="text-sm text-slate-500 mt-2">Please select or create an agent from the sidebar drawer to view their Contact Book.</p>
    </div>

    <template v-else>
        <!-- Header & Tabs -->
        <div class="sticky top-0 z-10 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md pt-2 border-b border-slate-200 dark:border-slate-800">
            <!-- Scrollable Tabs per Stitch Design -->
            <div class="flex px-4 overflow-x-auto gap-6 scrollbar-none [scrollbar-width:none]">
                <button 
                  v-for="tab in [{id: 'all', label: 'All'}, {id: 'working', label: 'Working'}, {id: 'on_hold', label: 'On Hold'}, {id: 'closed', label: 'Closed'}]"
                  :key="tab.id"
                  @click="activeTab = tab.id"
                  class="flex flex-col items-center border-b-2 pb-3 pt-2 shrink-0 transition-colors"
                  :class="activeTab === tab.id ? 'border-primary text-primary font-semibold' : 'border-transparent text-slate-500 hover:text-slate-700 font-medium'"
                >
                  <span class="text-sm whitespace-nowrap">{{ tab.label }}</span>
                </button>
            </div>
        </div>

        <!-- Main Content Area -->
        <main class="flex-1 overflow-y-auto p-4 space-y-4 pb-24">
            
            <div v-if="isLoading" class="flex justify-center p-8">
                <span class="material-symbols-outlined animate-spin text-primary">sync</span>
            </div>
            
            <div v-else-if="filteredLeads.length === 0" class="text-center p-8 border border-slate-100 dark:border-slate-800 rounded-xl bg-slate-50 dark:bg-slate-800/20 w-full box-border mt-10">
                <span class="material-symbols-outlined text-4xl text-slate-300 mb-2">person_off</span>
                <h3 class="text-sm font-bold">No Contacts Found</h3>
                <p class="text-xs text-slate-500 mt-1">Add a new contact to see them appear here.</p>
            </div>

            <!-- Lead Cards -->
            <div 
              v-else 
              v-for="lead in filteredLeads" 
              :key="lead.id" 
              class="bg-white dark:bg-slate-800 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 flex items-start gap-4 transition-opacity"
              :class="{'opacity-75': activeTab === 'all' && (getModeLabel(lead) === 'on_hold' || lead.stage.includes('CLOSED'))}"
            >
                <!-- Avatar -->
                <div class="size-14 rounded-full flex items-center justify-center shrink-0" :class="getModeLabel(lead) === 'working' ? 'bg-primary/10 text-primary' : 'bg-slate-100 dark:bg-slate-700 text-slate-400'">
                    <span class="material-symbols-outlined text-2xl" :class="lead.stage.includes('CLOSED') ? 'person_off' : (getModeLabel(lead) === 'working' ? 'corporate_fare' : 'person')">
                        {{ lead.stage.includes('CLOSED') ? 'person_off' : (getModeLabel(lead) === 'working' ? 'corporate_fare' : 'person') }}
                    </span>
                </div>
                
                <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between mb-1">
                        <h3 class="font-bold text-base truncate">{{ lead.name || 'Unknown' }}</h3>
                        <span 
                            class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider whitespace-nowrap shrink-0 ml-2"
                            :class="
                                lead.stage.includes('CLOSED') ? 'bg-slate-100 dark:bg-slate-900/50 text-slate-500' :
                                (getModeLabel(lead) === 'working' ? 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400' : 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400')
                            "
                        >
                            {{ lead.stage.includes('CLOSED') ? 'Archived' : (getModeLabel(lead) === 'working' ? 'Working' : 'On Hold') }}
                        </span>
                    </div>
                    
                    <div class="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 text-xs mb-3">
                        <span class="material-symbols-outlined text-sm">schedule</span>
                        <span v-if="lead.stage.includes('CLOSED')">Last contacted recently</span>
                        <span v-else>
                            Follow-up <span class="text-primary font-semibold">{{ getFollowUpText(lead) }}</span>
                        </span>
                    </div>
                    
                    <div class="flex items-center gap-1.5 text-slate-400 dark:text-slate-500 text-[10px] mb-3 font-mono">
                        <span class="material-symbols-outlined text-[12px] align-text-bottom">phone_iphone</span> {{ lead.external_id }}
                    </div>

                    <!-- Actions -->
                    <div class="flex gap-2">
                        <button 
                            v-if="!lead.stage.includes('CLOSED')"
                            @click="setLeadMode(lead, getModeLabel(lead) === 'working' ? 'on_hold' : 'working')"
                            :disabled="processingLeadId === lead.id"
                            class="flex-1 text-white py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
                            :class="getModeLabel(lead) === 'working' ? 'bg-amber-500 hover:bg-amber-600' : 'bg-primary hover:bg-primary/90'"
                        >
                            <span class="material-symbols-outlined text-sm">{{ getModeLabel(lead) === 'working' ? 'pause_circle' : 'play_circle' }}</span>
                            {{ getModeLabel(lead) === 'working' ? 'Hold Mode' : 'Start Working' }}
                        </button>
                        
                        <button 
                            @click="reviewLeadChat(lead)"
                            class="px-3 py-2 rounded-lg text-xs font-semibold shrink-0 transition-colors flex items-center gap-1"
                            :class="lead.stage.includes('CLOSED') ? 'flex-1 bg-primary text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300'"
                        >
                            <span class="material-symbols-outlined text-sm pr-0.5">forum</span>
                            {{ lead.stage.includes('CLOSED') ? 'Review History' : 'Chat' }}
                        </button>
                    </div>
                </div>
            </div>

        </main>

        <!-- Floating Action Button -->
        <div class="fixed bottom-8 right-6 z-30">
            <button 
                @click="isAddingForm = true"
                class="flex items-center justify-center size-14 rounded-full bg-primary text-white shadow-lg shadow-primary/30 hover:scale-105 active:scale-95 transition-transform"
            >
                <span class="material-symbols-outlined text-3xl">add</span>
            </button>
        </div>

        <!-- Add Lead Modal (Sliding Drawer) -->
        <div v-if="isAddingForm" class="fixed inset-0 z-50 flex flex-col justify-end">
            <!-- Backdrop -->
            <div class="absolute inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity" @click="isAddingForm = false"></div>
            
            <div class="relative w-full max-w-md mx-auto bg-white dark:bg-slate-900 rounded-t-2xl shadow-2xl flex flex-col animate-in slide-in-from-bottom duration-300 z-10 box-border p-6 pb-8">
                <div class="flex justify-between items-center mb-6">
                    <h3 class="font-bold text-lg">Add New Contact</h3>
                    <button @click="isAddingForm = false" class="text-slate-400 hover:text-slate-600 p-1">
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </div>
                
                <div class="space-y-4">
                    <div class="flex flex-col gap-1.5">
                        <label class="text-sm font-semibold text-slate-700 dark:text-slate-300">Name</label>
                        <TuiInput v-model="newLeadName" placeholder="e.g. John Doe" class="!rounded-xl !bg-slate-50 dark:!bg-slate-800" />
                    </div>
                    <div class="flex flex-col gap-1.5">
                        <label class="text-sm font-semibold text-slate-700 dark:text-slate-300">Phone / ID</label>
                        <TuiInput v-model="newLeadExternalId" placeholder="e.g. 60123456789" class="!rounded-xl !bg-slate-50 dark:!bg-slate-800" />
                    </div>
                    <p v-if="createError" class="text-xs text-red-500 font-medium">{{ createError }}</p>
                    
                    <button 
                        @click="createLead"
                        :disabled="isCreating"
                        class="w-full bg-primary hover:bg-primary/90 text-white font-bold h-12 rounded-xl mt-4 flex items-center justify-center transition-transform active:scale-[0.98] disabled:opacity-50"
                    >
                        {{ isCreating ? 'Saving...' : 'Add Contact' }}
                    </button>
                </div>
            </div>
        </div>

        <!-- Chat History Modal (Sliding Drawer) -->
        <div v-if="chatOpen" class="fixed inset-0 z-50 flex flex-col justify-end">
            <div class="absolute inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity" @click="chatOpen = false"></div>
            
            <div class="relative w-full max-w-md mx-auto bg-white dark:bg-slate-900 h-[85vh] rounded-t-2xl shadow-2xl flex flex-col animate-in slide-in-from-bottom duration-300 z-10 box-border">
                
                <!-- Drag Handle -->
                <div class="w-full flex justify-center pt-3 pb-1">
                    <div class="w-12 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full"></div>
                </div>

                <header class="px-6 pb-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
                    <div class="min-w-0 pr-4">
                        <h3 class="font-bold text-lg truncate">{{ chatLead?.name || 'Contact History' }}</h3>
                        <p class="text-xs text-slate-500 font-mono">{{ chatLead?.external_id }}</p>
                    </div>
                    <button @click="chatOpen = false" class="p-2 shrink-0 bg-slate-100 dark:bg-slate-800 rounded-full transition-colors text-slate-500">
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </header>

                <div class="flex-1 overflow-y-auto p-4 space-y-4 pb-20 bg-slate-50 dark:bg-slate-900/50">
                    <div v-if="chatLoading" class="flex flex-col items-center justify-center h-full text-slate-600 space-y-3">
                        <span class="material-symbols-outlined animate-spin text-primary">sync</span>
                        <p class="text-xs font-semibold uppercase tracking-widest text-primary">Loading Transcript...</p>
                    </div>
                    <p v-else-if="chatError" class="text-sm font-semibold text-red-500 text-center mt-10">{{ chatError }}</p>
                    <div v-else-if="chatMessages.length === 0" class="flex flex-col items-center justify-center h-full text-slate-400">
                        <span class="material-symbols-outlined text-4xl mb-2 opacity-50">forum</span>
                        <p class="text-sm font-medium">No conversation history yet.</p>
                    </div>
                    
                    <template v-else>
                        <div v-for="msg in chatMessages" :key="msg.id" 
                            class="max-w-[85%] p-3.5 rounded-2xl text-[14px] leading-relaxed relative"
                            :class="msg.direction === 'outbound' ? 'bg-primary text-white ml-auto rounded-tr-sm shadow-sm' : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm mr-auto rounded-tl-sm'">
                            
                            <p class="whitespace-pre-wrap">{{ msg.text_content || '(media attached)' }}</p>
                            
                            <div class="flex items-center justify-between mt-2 pt-1.5 text-xs opacity-70">
                                <span class="uppercase tracking-wider font-semibold">{{ msg.direction === 'outbound' ? 'Agent' : 'Lead' }}</span>
                                <span>{{ new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</span>
                            </div>
                        </div>
                    </template>
                </div>
            </div>
        </div>

    </template>
  </div>
</template>
