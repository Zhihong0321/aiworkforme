<script setup>
import { ref, onMounted, watch } from 'vue'
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

onMounted(async () => {
  await fetchLeads()
  await refreshOperationalChecks()
})
watch(() => store.activeWorkspaceId, async () => {
  await fetchLeads()
  await refreshOperationalChecks()
})
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto">
    <header class="mb-12 flex justify-between items-end">
      <div>
        <div class="flex items-center gap-2 mb-2">
            <h1 class="text-3xl font-black text-slate-900 tracking-tight">People to Help</h1>
            <TuiBadge variant="success" size="sm" class="animate-pulse">Agent Active</TuiBadge>
        </div>
        <p class="text-slate-500 text-sm">You have {{ leads.length }} potential conversations ready for your teammate to handle.</p>
      </div>
      <div class="flex gap-3">
          <TuiButton variant="outline" size="lg" class="!rounded-2xl border-slate-200">Import Contacts</TuiButton>
          <TuiButton size="lg" class="!rounded-2xl bg-indigo-600 shadow-xl shadow-indigo-600/20 px-8" @click="startAllLeads">Send Agent to Work</TuiButton>
      </div>
    </header>

    <div class="mb-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div class="mb-4">
        <h2 class="text-lg font-black text-slate-900 tracking-tight">Manual Insert Lead</h2>
        <p class="text-xs text-slate-500">Create a lead directly for WhatsApp outbound/inbound testing.</p>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <TuiInput v-model="newLeadName" label="Name (Optional)" placeholder="John Doe" />
        <TuiInput v-model="newLeadExternalId" label="Phone / External ID" placeholder="60123456789" />
        <div class="flex items-end">
          <TuiButton class="w-full" :loading="isCreating" @click="createLead">Add Lead</TuiButton>
        </div>
      </div>
      <p v-if="createError" class="mt-3 text-xs font-semibold text-red-600">{{ createError }}</p>
      <p v-if="actionError" class="mt-1 text-xs font-semibold text-red-600">{{ actionError }}</p>
      <p v-if="actionMessage" class="mt-1 text-xs font-semibold text-emerald-700">{{ actionMessage }}</p>
    </div>

    <div class="mb-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-black text-slate-900 tracking-tight">MVP Operational Check</h2>
          <p class="text-xs text-slate-500">Validate minimum in/out prerequisites before real WhatsApp test.</p>
        </div>
        <TuiButton variant="outline" size="sm" :loading="checkLoading" @click="refreshOperationalChecks">Refresh Check</TuiButton>
      </div>
      <div v-if="mvpCheck" class="space-y-2">
        <p class="text-xs font-black uppercase tracking-wider" :class="mvpCheck.ready ? 'text-emerald-700' : 'text-red-700'">
          {{ mvpCheck.ready ? 'READY' : 'NOT READY' }}
        </p>
        <p class="text-xs text-slate-600">
          Workspaces: {{ mvpCheck.checks.workspace_count }} | Agents: {{ mvpCheck.checks.agent_count }} | Active WA sessions: {{ mvpCheck.checks.whatsapp_active_session_count }} | Valid WA leads: {{ mvpCheck.checks.valid_whatsapp_lead_count }}
        </p>
        <div v-if="Array.isArray(mvpCheck.blockers) && mvpCheck.blockers.length" class="space-y-1">
          <p v-for="b in mvpCheck.blockers" :key="b" class="text-xs font-semibold text-red-700">- {{ b }}</p>
        </div>
      </div>
      <div v-if="inboundHealth" class="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="text-[10px] uppercase tracking-[0.2em] font-black text-slate-500">Inbound Health</p>
            <p class="text-xs text-slate-600">
              Mode: {{ inboundHealth.worker_mode }} | Channel: {{ inboundHealth.notify_channel }}
            </p>
          </div>
          <p class="text-xs font-black uppercase tracking-wider" :class="inboundHealth.ready ? 'text-emerald-700' : 'text-red-700'">
            {{ inboundHealth.ready ? 'HEALTHY' : 'ATTENTION' }}
          </p>
        </div>
        <p class="mt-2 text-xs text-slate-700">
          Received(unprocessed): {{ inboundHealth.checks?.inbound_received_unprocessed ?? 0 }}
          | Stuck >5m: {{ inboundHealth.checks?.inbound_received_stuck_over_5m ?? 0 }}
          | Last processed ID: {{ inboundHealth.checks?.last_processed_inbound_message_id ?? '-' }}
        </p>
        <div v-if="Array.isArray(inboundHealth.blockers) && inboundHealth.blockers.length" class="mt-2 space-y-1">
          <p v-for="b in inboundHealth.blockers" :key="b" class="text-xs font-semibold text-red-700">- {{ b }}</p>
        </div>
      </div>
      <div class="mt-5 grid grid-cols-1 md:grid-cols-4 gap-3">
        <select v-model="simLeadId" class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm md:col-span-1">
          <option value="">Select lead</option>
          <option v-for="lead in leads" :key="lead.id" :value="lead.id">{{ lead.name || `Lead ${lead.id}` }}</option>
        </select>
        <input v-model="simText" class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm md:col-span-2" placeholder="Inbound text for simulation" />
        <TuiButton :loading="simLoading" @click="simulateInbound">Simulate Inbound</TuiButton>
      </div>
      <p v-if="simResult" class="mt-2 text-xs font-semibold text-emerald-700">{{ simResult }}</p>
    </div>

    <div v-if="isLoading" class="p-20 text-center">
        <div class="inline-flex gap-2 mb-4">
            <span class="w-2 h-2 rounded-full bg-indigo-600 animate-bounce"></span>
            <span class="w-2 h-2 rounded-full bg-indigo-600 animate-bounce [animation-delay:0.2s]"></span>
            <span class="w-2 h-2 rounded-full bg-indigo-600 animate-bounce [animation-delay:0.4s]"></span>
        </div>
        <p class="text-slate-400 font-medium uppercase tracking-widest text-[10px]">Syncing with teammates...</p>
    </div>

    <div v-else-if="leads.length === 0" class="p-20 text-center border-2 border-dashed border-slate-200 rounded-[2rem] bg-slate-50/50">
      <div class="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-6">
          <svg class="w-8 h-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
      </div>
      <h3 class="text-slate-900 font-bold mb-2">Your contact list is empty</h3>
      <p class="text-slate-500 text-sm mb-8 max-w-sm mx-auto">Add some contacts to give your AI teammate someone to talk to.</p>
      <TuiButton variant="outline" class="!rounded-xl">Import Sample Contacts</TuiButton>
    </div>

    <div v-else class="bg-white border border-slate-200 rounded-[2rem] overflow-hidden shadow-xl shadow-slate-200/50">
      <table class="w-full text-left text-sm">
        <thead class="bg-slate-50/50 border-b border-slate-100 uppercase text-[10px] tracking-[0.2em] font-black text-slate-400">
          <tr>
            <th class="px-8 py-5">Contact</th>
            <th class="px-8 py-5">Status</th>
            <th class="px-8 py-5">Agent Activity</th>
            <th class="px-8 py-5">Contact ID</th>
            <th class="px-8 py-5 text-right">Conversation</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-50">
          <tr v-for="lead in leads" :key="lead.id" class="hover:bg-slate-50/80 transition-all group">
            <td class="px-8 py-6">
              <div class="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">{{ lead.name || 'Anonymous' }}</div>
              <div class="text-[10px] text-slate-400 font-medium mt-0.5">{{ lead.external_id }}</div>
            </td>
            <td class="px-8 py-6">
              <TuiBadge :variant="getStageVariant(lead.stage)" class="!rounded-lg px-3 py-1 text-[10px] font-black uppercase tracking-wider">{{ lead.stage }}</TuiBadge>
            </td>
            <td class="px-8 py-6">
                <div class="flex items-center gap-3">
                   <TuiBadge :variant="getModeLabel(lead) === 'WORKING' ? 'success' : 'warning'" class="!rounded-lg px-2 py-1 text-[10px] font-black uppercase tracking-wider">
                     {{ getModeLabel(lead) }}
                   </TuiBadge>
                </div>
                <div class="flex items-center gap-3 mt-2">
                   <TuiButton variant="outline" size="sm" class="!rounded-xl" :loading="actionLoadingLeadId === lead.id" @click="setLeadMode(lead, 'on_hold')">On Hold</TuiButton>
                   <TuiButton size="sm" class="!rounded-xl" :loading="actionLoadingLeadId === lead.id" @click="setLeadMode(lead, 'working')">Working</TuiButton>
                   <TuiButton variant="outline" size="sm" class="!rounded-xl !border-red-200 !text-red-700 hover:!bg-red-50" :loading="actionLoadingLeadId === lead.id" @click="deleteLead(lead)">Delete</TuiButton>
                </div>
                <div class="flex items-center gap-3 mt-2">
                   <div v-if="lead.next_followup_at" class="flex flex-col">
                       <div class="flex items-center gap-1.5 mb-1">
                           <span class="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                           <span class="text-[10px] font-black text-slate-400 uppercase tracking-tight">Scheduled</span>
                       </div>
                       <span class="text-xs text-slate-600 font-medium">Due {{ new Date(lead.next_followup_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}</span>
                   </div>
                   <div v-else class="flex items-center gap-1.5 opacity-30">
                       <span class="w-1.5 h-1.5 rounded-full bg-slate-300"></span>
                       <span class="text-[10px] font-black uppercase tracking-tight">On Hold</span>
                   </div>
                </div>
            </td>
            <td class="px-8 py-6">
                <div class="mt-2 text-[10px] text-slate-500 font-mono break-all">
                  {{ lead.external_id || 'none' }}
                </div>
            </td>
            <td class="px-8 py-6 text-right">
              <TuiButton variant="outline" size="sm" class="!rounded-xl border-slate-200 hover:border-indigo-200 hover:bg-indigo-50 transition-all" @click="reviewLeadChat(lead)">Review Chat</TuiButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="chatOpen" class="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div class="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white shadow-2xl overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 class="text-lg font-black text-slate-900 tracking-tight">Conversation Review</h3>
            <p class="text-xs text-slate-500">{{ chatLead?.name || 'Lead' }} · {{ chatLead?.external_id || '' }}</p>
          </div>
          <TuiButton variant="outline" size="sm" @click="chatOpen = false">Close</TuiButton>
        </div>
        <div class="max-h-[65vh] overflow-y-auto p-6 space-y-3 bg-slate-50">
          <p v-if="chatLoading" class="text-sm text-slate-500">Loading messages...</p>
          <p v-else-if="chatError" class="text-sm font-semibold text-red-600">{{ chatError }}</p>
          <p v-else-if="chatMessages.length === 0" class="text-sm text-slate-500">No messages yet.</p>
          <div v-else v-for="msg in chatMessages" :key="msg.id" class="rounded-2xl px-4 py-3 text-sm"
               :class="msg.direction === 'outbound' ? 'bg-indigo-600 text-white ml-12' : 'bg-white border border-slate-200 mr-12'">
            <div class="flex items-center justify-between text-[10px] font-black uppercase tracking-wider opacity-80 mb-1">
              <span>{{ msg.direction }}</span>
              <span>{{ new Date(msg.created_at).toLocaleString() }}</span>
            </div>
            <p class="whitespace-pre-wrap break-words">{{ msg.text_content || '(non-text message)' }}</p>
            <p class="text-[10px] mt-1 opacity-80">status: {{ msg.delivery_status }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
