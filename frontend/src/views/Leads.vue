<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { store } from '../store'
import { request } from '../services/api'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiInput from '../components/ui/TuiInput.vue'

const leads = ref([])
const isLoading = ref(false)
const isCreating = ref(false)
const createError = ref('')
const actionError = ref('')
const actionMessage = ref('')
const actionLoadingLeadId = ref(null)
const newLeadName = ref('')
const newLeadExternalId = ref('')
const chatOpen = ref(false)
const chatLoading = ref(false)
const chatError = ref('')
const chatLead = ref(null)
const chatMessages = ref([])
const checkLoading = ref(false)
const mvpCheck = ref(null)
const inboundHealth = ref(null)
const simLeadId = ref('')
const simText = ref('Hi, I want to know more about your service.')
const simLoading = ref(false)
const simResult = ref('')
const csvFile = ref(null)
const csvImportLoading = ref(false)
const followupTestLoading = ref(false)
const followupCountdown = ref(0)
const followupTriggering = ref(false)
let followupCountdownTimer = null

const clearFollowupCountdown = () => {
  if (followupCountdownTimer) {
    clearInterval(followupCountdownTimer)
    followupCountdownTimer = null
  }
  followupCountdown.value = 0
}

const fetchLeads = async () => {
  if (!store.activeWorkspaceId) {
    await store.fetchWorkspaces()
  }
  if (!store.activeWorkspaceId) return
  isLoading.value = true
  try {
    const data = await request(`/workspaces/${store.activeWorkspaceId}/leads`)
    leads.value = data
    if (!simLeadId.value && Array.isArray(leads.value) && leads.value.length > 0) {
      simLeadId.value = String(leads.value[0].id)
    }
  } catch (e) {
    console.error('Failed to fetch leads', e)
  } finally {
    isLoading.value = false
  }
}

const createLead = async () => {
  createError.value = ''
  if (!store.activeWorkspaceId) {
    createError.value = 'No active workspace selected.'
    return
  }
  if (!newLeadExternalId.value.trim()) {
    createError.value = 'Phone / external ID is required.'
    return
  }

  isCreating.value = true
  try {
    await request(`/workspaces/${store.activeWorkspaceId}/leads`, {
      method: 'POST',
      body: JSON.stringify({
        workspace_id: Number(store.activeWorkspaceId),
        external_id: newLeadExternalId.value.trim(),
        name: newLeadName.value.trim() || null,
        stage: 'NEW'
      })
    })
    newLeadName.value = ''
    newLeadExternalId.value = ''
    await fetchLeads()
    await refreshOperationalChecks()
  } catch (e) {
    createError.value = e.message || 'Failed to create lead'
  } finally {
    isCreating.value = false
  }
}


const getStageVariant = (stage) => {
  if (['NEW', 'CONTACTED'].includes(stage)) return 'info'
  if (['ENGAGED', 'QUALIFIED'].includes(stage)) return 'success'
  if (['TAKE_OVER'].includes(stage)) return 'warning'
  return 'muted'
}

const getModeLabel = (lead) => {
  const tags = Array.isArray(lead.tags) ? lead.tags : []
  if (tags.includes('WORKING')) return 'WORKING'
  if (tags.includes('ON_HOLD')) return 'ON HOLD'
  return 'ON HOLD'
}

const setLeadMode = async (lead, mode) => {
  actionError.value = ''
  actionMessage.value = ''
  actionLoadingLeadId.value = lead.id
  try {
    if (mode === 'working') {
      const result = await request(`/messaging/leads/${lead.id}/start-work`, {
        method: 'POST',
        body: JSON.stringify({ channel: 'whatsapp' })
      })
      const sentLabel = result?.status === 'sent' ? 'sent' : result?.status === 'accepted' ? 'accepted (pending delivery)' : result?.status || 'queued'
      const recipient = result?.recipient ? ` to ${result.recipient}` : ''
      actionMessage.value = `Lead ${lead.name || lead.id}: ${sentLabel}${recipient}.`
    } else {
      await request(`/workspaces/${store.activeWorkspaceId}/leads/${lead.id}/mode`, {
        method: 'POST',
        body: JSON.stringify({ mode })
      })
      actionMessage.value = `Lead ${lead.name || lead.id} moved to ON HOLD.`
    }
    await fetchLeads()
    await refreshOperationalChecks()
  } catch (e) {
    actionError.value = e.message || 'Failed to update mode'
  } finally {
    actionLoadingLeadId.value = null
  }
}

const deleteLead = async (lead) => {
  actionError.value = ''
  actionMessage.value = ''
  const ok = window.confirm(`Delete lead "${lead.name || lead.external_id}" and clear all conversation history?`)
  if (!ok) return

  actionLoadingLeadId.value = lead.id
  try {
    await request(`/workspaces/${store.activeWorkspaceId}/leads/${lead.id}`, {
      method: 'DELETE'
    })
    actionMessage.value = `Lead ${lead.name || lead.id} deleted. Conversation cleared.`
    await fetchLeads()
    await refreshOperationalChecks()
    if (chatOpen.value && chatLead.value?.id === lead.id) {
      chatOpen.value = false
      chatLead.value = null
      chatMessages.value = []
    }
  } catch (e) {
    actionError.value = e.message || 'Failed to delete lead'
  } finally {
    actionLoadingLeadId.value = null
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

const runMvpCheck = async () => {
  try {
    mvpCheck.value = await request('/messaging/mvp/operational-check')
  } catch (e) {
    actionError.value = e.message || 'Failed to run operational check'
  }
}

const runInboundHealthCheck = async () => {
  try {
    inboundHealth.value = await request('/messaging/mvp/inbound-health')
  } catch (e) {
    actionError.value = e.message || 'Failed to fetch inbound health'
  }
}

const refreshOperationalChecks = async () => {
  checkLoading.value = true
  try {
    await Promise.all([
      runMvpCheck(),
      runInboundHealthCheck()
    ])
  } finally {
    checkLoading.value = false
  }
}

const simulateInbound = async () => {
  actionError.value = ''
  simResult.value = ''
  if (!simLeadId.value) {
    actionError.value = 'Pick a lead for inbound simulation.'
    return
  }
  if (!simText.value.trim()) {
    actionError.value = 'Inbound text is required.'
    return
  }
  simLoading.value = true
  try {
    const result = await request('/messaging/mvp/simulate-inbound', {
      method: 'POST',
      body: JSON.stringify({
        lead_id: Number(simLeadId.value),
        channel: 'whatsapp',
        text_content: simText.value.trim()
      })
    })
    simResult.value = result.detail || `Inbound status: ${result.inbound_status}`
    await fetchLeads()
    await refreshOperationalChecks()
  } catch (e) {
    actionError.value = e.message || 'Failed to simulate inbound'
  } finally {
    simLoading.value = false
  }
}

const onCsvFileSelected = (event) => {
  const files = event?.target?.files
  csvFile.value = files && files.length ? files[0] : null
}

const importLeadsFromCsv = async () => {
  actionError.value = ''
  actionMessage.value = ''
  if (!store.activeWorkspaceId) {
    actionError.value = 'No active workspace selected.'
    return
  }
  if (!csvFile.value) {
    actionError.value = 'Please choose a CSV file first.'
    return
  }

  csvImportLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', csvFile.value)
    formData.append('has_header', 'true')

    const result = await request(`/workspaces/${store.activeWorkspaceId}/leads/import-csv`, {
      method: 'POST',
      body: formData
    })
    actionMessage.value = `CSV imported: created ${result.leads_created}, duplicates ${result.skipped_duplicates}, invalid ${result.skipped_invalid}.`
    if (Array.isArray(result.errors) && result.errors.length > 0) {
      actionError.value = result.errors.join(' | ')
    }
    csvFile.value = null
    await fetchLeads()
    await refreshOperationalChecks()
  } catch (e) {
    actionError.value = e.message || 'CSV import failed'
  } finally {
    csvImportLoading.value = false
  }
}

const startAllLeads = async () => {
  actionError.value = ''
  if (!leads.value.length) {
    actionError.value = 'No leads available.'
    return
  }
  for (const lead of leads.value) {
    await setLeadMode(lead, 'working')
  }
}

const triggerDueFollowupsNow = async () => {
  if (!store.activeWorkspaceId) {
    throw new Error('No active workspace selected.')
  }
  followupTriggering.value = true
  try {
    const result = await request(`/workspaces/${store.activeWorkspaceId}/ai-crm/trigger-due`, {
      method: 'POST'
    })
    actionMessage.value = `Follow-up trigger finished: sent ${result.triggered}, skipped ${result.skipped}.`
    if (Array.isArray(result.errors) && result.errors.length > 0) {
      actionError.value = result.errors.join(' | ')
    }
    await fetchLeads()
    await refreshOperationalChecks()
  } finally {
    followupTriggering.value = false
  }
}

const processAllFollowupsNow = async () => {
  actionError.value = ''
  actionMessage.value = ''
  clearFollowupCountdown()
  if (!store.activeWorkspaceId) {
    actionError.value = 'No active workspace selected.'
    return
  }

  followupTestLoading.value = true
  try {
    const workspaceId = store.activeWorkspaceId
    const scanResult = await request(`/workspaces/${workspaceId}/ai-crm/scan`, {
      method: 'POST',
      body: JSON.stringify({ force_all: true })
    })

    const fastForward = await request(`/workspaces/${workspaceId}/ai-crm/fast-forward`, {
      method: 'POST',
      body: JSON.stringify({ seconds: 5, include_overdue: true })
    })
    actionMessage.value = `AI CRM forced to test mode: scanned ${scanResult.scanned_threads}, pending follow-ups moved to ${fastForward.seconds}s (${fastForward.updated_states} thread states).`

    followupCountdown.value = Number(fastForward.seconds || 5)
    followupCountdownTimer = setInterval(async () => {
      followupCountdown.value = Math.max(0, followupCountdown.value - 1)
      if (followupCountdown.value > 0) {
        return
      }
      clearFollowupCountdown()
      try {
        await triggerDueFollowupsNow()
      } catch (e) {
        actionError.value = e.message || 'Failed to trigger due follow-ups'
      }
    }, 1000)
  } catch (e) {
    clearFollowupCountdown()
    actionError.value = e.message || 'Failed to process follow-ups now'
  } finally {
    followupTestLoading.value = false
  }
}

onMounted(async () => {
  await fetchLeads()
  await refreshOperationalChecks()
})
watch(() => store.activeWorkspaceId, async () => {
  clearFollowupCountdown()
  await fetchLeads()
  await refreshOperationalChecks()
})
onBeforeUnmount(() => {
  clearFollowupCountdown()
})
</script>

<template>
  <div class="min-h-[calc(100vh-64px)] w-full bg-onyx font-inter text-slate-200 flex flex-col pb-20">
    
    <!-- Header -->
    <div class="p-5 border-b border-slate-800/50 glass-panel-light rounded-b-[2rem] sticky top-0 z-30 mb-4">
      <div class="flex justify-between items-end">
        <div>
          <h1 class="text-3xl font-semibold text-white tracking-tight mb-1">Contacts</h1>
          <p class="text-sm text-purple-300 font-medium tracking-wide">
            {{ leads.length }} Leads Ready
          </p>
        </div>
        <button class="h-12 w-12 rounded-full bg-aurora-gradient flex items-center justify-center text-white shadow-lg shadow-purple-500/30 active:scale-95 transition-all">
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        </button>
      </div>

      <!-- Quick Actions -->
      <div class="flex gap-3 mt-5 overflow-x-auto pb-2 scrollbar-none [scrollbar-width:none]">
        <button @click="startAllLeads" class="px-5 py-2.5 rounded-full text-sm font-semibold bg-aurora-gradient text-white shadow-lg shadow-purple-500/25 shrink-0 active:scale-95 transition-transform flex items-center gap-2">
           <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
           Send Agent to Work
        </button>
        <button @click="processAllFollowupsNow" :disabled="followupTestLoading || followupTriggering" class="px-5 py-2.5 rounded-full text-sm font-semibold glass-panel border border-amber-500/30 text-amber-300 hover:text-amber-200 shrink-0 active:scale-95 transition-transform">
           Process Follow-ups
        </button>
      </div>
      <p v-if="followupCountdown > 0" class="mt-3 text-xs font-bold text-amber-400">
        Test countdown: {{ followupCountdown }}s
      </p>
    </div>

    <!-- Lead List -->
    <div v-if="isLoading" class="flex-grow flex flex-col items-center justify-center space-y-4 p-10">
      <div class="flex gap-2">
        <div class="w-2.5 h-2.5 rounded-full bg-purple-500 animate-bounce"></div>
        <div class="w-2.5 h-2.5 rounded-full bg-purple-500 animate-bounce [animation-delay:0.2s]"></div>
        <div class="w-2.5 h-2.5 rounded-full bg-purple-500 animate-bounce [animation-delay:0.4s]"></div>
      </div>
      <p class="text-xs text-slate-500 font-bold tracking-widest uppercase">Syncing Contacts</p>
    </div>

    <div v-else-if="leads.length === 0" class="flex-grow flex flex-col items-center justify-center p-10 text-center">
      <div class="w-20 h-20 rounded-full glass-panel flex items-center justify-center mb-6 ring-1 ring-white/10">
        <svg class="w-10 h-10 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
      </div>
      <h3 class="text-lg font-bold text-white mb-2">No Contacts Yet</h3>
      <p class="text-sm text-slate-400">Add a contact to let your AI start chatting and capturing leads.</p>
    </div>

    <!-- Contact Cards (Mobile Replacement for Table) -->
    <div v-else class="px-4 space-y-4 relative z-10 box-border">
      <div 
        v-for="lead in leads" 
        :key="lead.id" 
        class="glass-panel p-5 rounded-3xl relative overflow-hidden group border border-slate-700/50"
      >
        <!-- Top Row: Name & Status -->
        <div class="flex justify-between items-start mb-3">
          <div>
            <h3 class="text-lg font-bold text-white leading-tight break-words">{{ lead.name || 'Unknown' }}</h3>
            <p class="text-xs text-slate-400 font-medium mt-1 uppercase tracking-wider">{{ lead.external_id || 'No Number' }}</p>
          </div>
          <span 
            class="px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-lg shrink-0 w-max"
            :class="getStageVariant(lead.stage) === 'success' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : getStageVariant(lead.stage) === 'warning' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'"
          >
            {{ lead.stage }}
          </span>
        </div>

        <!-- AI Summary Context (Mock/Placeholder styled nicely) -->
        <div class="mb-4 text-sm text-slate-300 leading-relaxed max-w-full">
          <span class="text-purple-400 font-semibold mr-1">AI Context:</span>
          Interaction active. Current mode: {{ getModeLabel(lead) }}.
        </div>

        <!-- Meta info -->
        <div class="mb-4">
           <div v-if="lead.next_followup_at" class="flex items-center gap-2">
               <span class="w-2 h-2 rounded-full bg-purple-500 animate-pulse shrink-0"></span>
               <span class="text-xs text-slate-400">
                 Follow-up due <span class="text-white font-medium">{{ new Date(lead.next_followup_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}</span>
               </span>
           </div>
           <div v-else class="flex items-center gap-2">
               <span class="w-2 h-2 rounded-full bg-slate-600 shrink-0"></span>
               <span class="text-xs text-slate-500 font-medium uppercase tracking-tight">On Hold</span>
           </div>
        </div>

        <!-- Action Row -->
        <div class="flex items-center justify-between border-t border-slate-700/50 pt-4 w-full">
           <!-- Mode Toggles -->
           <div class="flex bg-slate-900/50 rounded-full p-1 border border-slate-700/50">
             <button 
               @click="setLeadMode(lead, 'on_hold')"
               class="px-3 py-1.5 rounded-full text-[11px] font-bold uppercase transition-all whitespace-nowrap"
               :class="getModeLabel(lead) !== 'WORKING' ? 'bg-slate-700 text-white shadow-sm' : 'text-slate-500'"
             >Hold</button>
             <button 
               @click="setLeadMode(lead, 'working')"
               class="px-3 py-1.5 rounded-full text-[11px] font-bold uppercase transition-all whitespace-nowrap"
               :class="getModeLabel(lead) === 'WORKING' ? 'bg-purple-600 text-white shadow-sm shadow-purple-500/30' : 'text-slate-500'"
             >Work</button>
           </div>
           
           <div class="flex gap-2">
             <!-- Review Chat Button -->
             <button @click="reviewLeadChat(lead)" class="h-9 w-9 rounded-full bg-slate-800 text-purple-300 flex items-center justify-center border border-slate-700 hover:bg-slate-700 shrink-0">
               <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
             </button>
             <!-- Delete Button -->
             <button @click="deleteLead(lead)" class="h-9 w-9 rounded-full bg-red-500/10 text-red-400 flex items-center justify-center border border-red-500/20 active:bg-red-500/20 shrink-0">
               <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
             </button>
           </div>
        </div>
      </div>
    </div>

    <!-- Utility Blocks (Add Lead, Import, Check) - Collapsed vertically at bottom -->
    <div class="px-4 mt-8 space-y-4">
      <!-- Create Lead Card -->
      <div class="glass-panel p-5 rounded-[2rem] border border-slate-700/50">
        <h3 class="text-white font-semibold mb-1">Add Contact</h3>
        <p class="text-xs text-slate-400 mb-4">Manually create a contact for the AI.</p>
        <div class="space-y-3">
          <input v-model="newLeadName" type="text" placeholder="Contact Name" class="w-full bg-slate-900/60 border border-slate-700/50 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors placeholder:text-slate-600" />
          <input v-model="newLeadExternalId" type="text" placeholder="Phone Number (e.g. 60123...)" class="w-full bg-slate-900/60 border border-slate-700/50 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors placeholder:text-slate-600" />
          <button @click="createLead" :disabled="isCreating" class="w-full bg-aurora-gradient text-white font-bold text-sm py-3 rounded-xl shadow-lg shadow-purple-500/20 active:scale-[0.98] transition-all flex justify-center mt-2">
            {{ isCreating ? 'Adding...' : 'Save Contact' }}
          </button>
          <p v-if="createError" class="text-xs text-red-400 text-center mt-2">{{ createError }}</p>
        </div>
      </div>
      
      <!-- Operations Feedback -->
      <div v-if="actionError || actionMessage" class="glass-panel p-4 rounded-xl border border-slate-700 flex flex-col items-center text-center">
         <p v-if="actionError" class="text-xs text-red-400 font-medium">{{ actionError }}</p>
         <p v-if="actionMessage" class="text-xs text-emerald-400 font-medium">{{ actionMessage }}</p>
      </div>
    </div>

    <!-- Review Chat Modal -->
    <div v-if="chatOpen" class="fixed inset-0 z-50 bg-onyx/90 backdrop-blur-md flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div class="w-full max-w-2xl bg-onyx sm:rounded-3xl rounded-t-3xl border-t border-slate-700 sm:border shadow-2xl overflow-hidden h-[85vh] sm:h-[70vh] flex flex-col">
        <div class="px-5 py-4 border-b border-slate-800 glass-panel-light flex items-center justify-between sticky top-0">
          <div>
            <h3 class="text-lg font-bold text-white tracking-tight">{{ chatLead?.name || 'Contact' }}</h3>
            <p class="text-[10px] text-purple-400 font-bold uppercase tracking-widest">{{ chatLead?.external_id || 'Reviewing History' }}</p>
          </div>
          <button @click="chatOpen = false" class="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 hover:text-white transition-colors">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        
        <div class="flex-grow overflow-y-auto p-5 space-y-4 bg-mobile-aurora scrollbar-none pb-10">
          <div v-if="chatLoading" class="flex flex-col items-center justify-center h-full text-slate-500 space-y-3">
             <div class="w-6 h-6 rounded-full border-t-2 border-r-2 border-purple-500 animate-spin"></div>
             <p class="text-xs font-medium uppercase tracking-widest">Loading Logs...</p>
          </div>
          <p v-else-if="chatError" class="text-sm font-semibold text-red-500 text-center mt-10">{{ chatError }}</p>
          <p v-else-if="chatMessages.length === 0" class="text-sm text-slate-500 text-center mt-10 italic">No message history.</p>
          
          <div v-else v-for="msg in chatMessages" :key="msg.id" 
               class="max-w-[85%] p-3.5 rounded-2xl text-[14px] leading-relaxed relative"
               :class="msg.direction === 'outbound' ? 'bg-aurora-gradient text-white ml-auto rounded-tr-sm shadow-lg shadow-purple-500/20' : 'glass-panel text-slate-200 mr-auto rounded-tl-sm'">
            
            <p class="whitespace-pre-wrap">{{ msg.text_content || '(non-text message)' }}</p>
            
            <div class="flex items-center justify-between mt-2 pt-2 border-t border-white/10" :class="msg.direction === 'outbound' ? 'border-white/20' : 'border-slate-700/50'">
              <span class="text-[9px] font-bold uppercase tracking-wider" :class="msg.direction === 'outbound' ? 'text-white/70' : 'text-slate-400'">{{ msg.direction }}</span>
              <span class="text-[9px] opacity-70">{{ new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</span>
            </div>
            
          </div>
        </div>
      </div>
    </div>

  </div>
</template>
