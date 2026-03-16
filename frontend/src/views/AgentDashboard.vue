<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { request } from '../services/api'
import { store } from '../store'
import {
  getChannelDescription,
  getChannelIdentity,
  getProviderSessionId,
  isConnectedChannelStatus,
} from '../utils/agentChannels'

const route = useRoute()
const router = useRouter()

const validTabs = ['settings', 'channels', 'knowledge', 'inbox', 'contacts']
const loading = ref(true)
const missingAgent = ref(false)
const toast = ref('')

const channels = ref([])
const mcpServers = ref([])
const knowledgeFiles = ref([])
const leads = ref([])
const threads = ref([])
const messages = ref([])
const activeThread = ref(null)
const salesMaterials = ref([])

const isSavingAgent = ref(false)
const isDeletingAgent = ref(false)
const isLoadingTranscript = ref(false)
const isResettingThread = ref(false)
const resettingLeadId = ref(null)
const isUploadingKnowledge = ref(false)
const isCreatingLead = ref(false)
const isUploadingSalesMaterial = ref(false)
const processingLeadId = ref(null)

const knowledgeInput = ref(null)
const salesMaterialInput = ref(null)
const selectedSalesMaterialFile = ref(null)
const salesMaterialMode = ref('file')
const salesMaterialDescription = ref('')
const salesMaterialUrl = ref('')

const leadDraft = reactive({
  name: '',
  external_id: '',
})

const form = reactive({
  id: null,
  name: '',
  system_prompt: '',
  linkedMcpIds: [],
  mimic_human_typing: false,
  emoji_level: 'none',
  segment_delay_ms: 800,
  preferred_channel_session_id: null,
})

const activeTab = computed(() => (
  validTabs.includes(String(route.query.tab || 'settings'))
    ? String(route.query.tab || 'settings')
    : 'settings'
))

const agentId = computed(() => Number(route.params.agentId))
const assignedChannel = computed(() => (
  channels.value.find((session) => Number(session.id) === Number(form.preferred_channel_session_id || 0)) || null
))
const channelOwnerById = computed(() => {
  const owners = new Map()
  for (const agent of store.agents) {
    const preferredId = Number(agent?.preferred_channel_session_id || 0)
    if (!preferredId || Number(agent.id) === Number(form.id || 0)) continue
    owners.set(preferredId, agent)
  }
  return owners
})

const setToast = (text) => {
  toast.value = text
  if (!text) return
  window.clearTimeout(setToast.timeoutId)
  setToast.timeoutId = window.setTimeout(() => {
    toast.value = ''
  }, 3200)
}
setToast.timeoutId = null

const getChannelOwner = (sessionId) => channelOwnerById.value.get(Number(sessionId || 0)) || null

const extractLinkedMcpIds = (agent) => {
  if (!agent) return []
  if (Array.isArray(agent.linked_mcp_ids)) return agent.linked_mcp_ids
  if (Array.isArray(agent.linkedMcpIds)) return agent.linkedMcpIds
  if (agent.linkedMcpId) return [agent.linkedMcpId]
  if (agent.linked_mcp_id) return [agent.linked_mcp_id]
  return []
}

const applyAgentToForm = (agent) => {
  form.id = agent?.id ?? null
  form.name = agent?.name ?? ''
  form.system_prompt = agent?.system_prompt ?? ''
  form.linkedMcpIds = [...extractLinkedMcpIds(agent)]
  form.mimic_human_typing = agent?.mimic_human_typing ?? false
  form.emoji_level = agent?.emoji_level ?? 'none'
  form.segment_delay_ms = agent?.segment_delay_ms ?? 800
  form.preferred_channel_session_id = agent?.preferred_channel_session_id ?? null
}

const formatFileSize = (bytes) => {
  const value = Number(bytes || 0)
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
  if (value >= 1024) return `${Math.round(value / 1024)} KB`
  return `${value} B`
}

const formatFollowUp = (lead) => {
  if (!lead?.next_followup_at) return 'No follow-up scheduled'
  const next = new Date(lead.next_followup_at)
  return Number.isNaN(next.getTime()) ? 'No follow-up scheduled' : next.toLocaleString()
}

const getLeadModeLabel = (lead) => {
  const tags = Array.isArray(lead?.tags) ? lead.tags : []
  if (tags.includes('WORKING')) return 'working'
  if (tags.includes('ON_HOLD')) return 'on_hold'
  return 'on_hold'
}

const setTab = (tab) => {
  if (!validTabs.includes(tab)) return
  router.replace({
    path: route.path,
    query: tab === 'settings' ? {} : { tab },
  })
}

const loadChannels = async () => {
  const data = await request('/messaging/channels/whatsapp/sessions').catch(() => [])
  channels.value = Array.isArray(data) ? data : []
}

const loadMcpServers = async () => {
  const data = await request('/mcp/servers').catch(() => [])
  mcpServers.value = Array.isArray(data)
    ? data.map((server, index) => ({
        id: server.id ?? index,
        name: server.name ?? 'server',
        description: server.description || `Tool access via ${server.name}`,
      }))
    : []
}

const loadSalesMaterials = async () => {
  if (!form.id) {
    salesMaterials.value = []
    return
  }
  const data = await request(`/agents/${form.id}/sales-materials`).catch(() => [])
  salesMaterials.value = Array.isArray(data) ? data : []
}

const loadKnowledge = async () => {
  if (!form.id) {
    knowledgeFiles.value = []
    return
  }
  const data = await request(`/agents/${form.id}/knowledge`).catch(() => [])
  knowledgeFiles.value = Array.isArray(data) ? data : []
}

const loadLeads = async () => {
  if (!form.id) {
    leads.value = []
    return
  }
  const data = await request(`/agents/${form.id}/leads`).catch(() => [])
  leads.value = Array.isArray(data) ? data : []
}

const loadThreads = async () => {
  if (!form.id) {
    threads.value = []
    return
  }
  const data = await request(`/agents/${form.id}/ai-crm/threads`).catch(() => [])
  threads.value = Array.isArray(data) ? data : []
}

const loadDashboard = async () => {
  loading.value = true
  missingAgent.value = false
  activeThread.value = null
  messages.value = []

  await store.fetchAgents()
  const agent = store.agents.find((item) => Number(item.id) === agentId.value)
  if (!agent) {
    missingAgent.value = true
    loading.value = false
    return
  }

  store.setActiveAgent(agent.id)
  applyAgentToForm(agent)

  await Promise.all([
    loadChannels(),
    loadMcpServers(),
    loadSalesMaterials(),
    loadKnowledge(),
    loadLeads(),
    loadThreads(),
  ])

  loading.value = false
}

const saveAgent = async (successMessage = 'Agent settings saved') => {
  if (!form.id) return
  isSavingAgent.value = true
  try {
    const saved = await request(`/agents/${form.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: form.name,
        system_prompt: form.system_prompt,
        mimic_human_typing: form.mimic_human_typing,
        emoji_level: form.emoji_level,
        segment_delay_ms: form.segment_delay_ms,
        preferred_channel_session_id: form.preferred_channel_session_id,
      }),
    })

    await store.fetchAgents()
    const agent = store.agents.find((item) => Number(item.id) === Number(saved?.id || form.id))
    if (agent) {
      store.setActiveAgent(agent.id)
      applyAgentToForm(agent)
    }
    setToast(successMessage)
  } catch (error) {
    setToast(`Save failed: ${error.message}`)
  } finally {
    isSavingAgent.value = false
  }
}

const deleteAgent = async () => {
  if (!form.id) return
  if (!window.confirm(`Delete agent "${form.name || 'Untitled agent'}"?`)) return

  isDeletingAgent.value = true
  try {
    await request(`/agents/${form.id}`, { method: 'DELETE' })
    await store.fetchAgents()
    router.push('/agents')
  } catch (error) {
    setToast(`Delete failed: ${error.message}`)
  } finally {
    isDeletingAgent.value = false
  }
}

const toggleSkill = async (serverId) => {
  if (!form.id) return

  const isLinked = form.linkedMcpIds.includes(serverId)
  try {
    if (isLinked) {
      await request(`/agents/${form.id}/link-mcp/${serverId}`, { method: 'DELETE' })
      form.linkedMcpIds = form.linkedMcpIds.filter((id) => id !== serverId)
    } else {
      await request(`/agents/${form.id}/link-mcp/${serverId}`, { method: 'POST' })
      form.linkedMcpIds = [...form.linkedMcpIds, serverId]
    }
    const localAgent = store.agents.find((item) => Number(item.id) === Number(form.id))
    if (localAgent) {
      localAgent.linked_mcp_ids = [...form.linkedMcpIds]
      localAgent.linked_mcp_count = form.linkedMcpIds.length
    }
    setToast('Skills updated')
  } catch (error) {
    setToast(`Skill update failed: ${error.message}`)
  }
}

const chooseKnowledgeFile = () => {
  knowledgeInput.value?.click()
}

const uploadKnowledge = async (event) => {
  const file = event.target.files?.[0]
  if (!file || !form.id) return

  isUploadingKnowledge.value = true
  try {
    const body = new FormData()
    body.append('file', file)
    body.append('tags', '["manual_upload"]')
    await request(`/agents/${form.id}/knowledge`, {
      method: 'POST',
      body,
    })
    await loadKnowledge()
    setToast('Knowledge file uploaded')
  } catch (error) {
    setToast(`Upload failed: ${error.message}`)
  } finally {
    isUploadingKnowledge.value = false
    if (knowledgeInput.value) knowledgeInput.value.value = ''
  }
}

const deleteKnowledge = async (fileId) => {
  if (!form.id) return
  if (!window.confirm('Delete this knowledge file?')) return

  try {
    await request(`/agents/${form.id}/knowledge/${fileId}`, { method: 'DELETE' })
    await loadKnowledge()
    setToast('Knowledge file deleted')
  } catch (error) {
    setToast(`Delete failed: ${error.message}`)
  }
}

const createLead = async () => {
  if (!form.id) return
  if (!leadDraft.external_id.trim()) {
    setToast('Phone / external ID is required')
    return
  }

  isCreatingLead.value = true
  try {
    await request(`/agents/${form.id}/leads`, {
      method: 'POST',
      body: JSON.stringify({
        external_id: leadDraft.external_id.trim(),
        name: leadDraft.name.trim() || null,
        stage: 'NEW',
      }),
    })
    leadDraft.name = ''
    leadDraft.external_id = ''
    await Promise.all([loadLeads(), loadThreads()])
    setToast('Contact added to this agent')
  } catch (error) {
    setToast(`Add contact failed: ${error.message}`)
  } finally {
    isCreatingLead.value = false
  }
}

const setLeadMode = async (lead, mode) => {
  processingLeadId.value = lead.id
  try {
    if (mode === 'working') {
      await request(`/messaging/leads/${lead.id}/start-work`, {
        method: 'POST',
        body: JSON.stringify({
          channel: 'whatsapp',
          channel_session_id: form.preferred_channel_session_id || null,
        }),
      })
      setToast(`AI started for ${lead.name || lead.external_id}`)
    } else {
      await request(`/leads/${lead.id}/mode`, {
        method: 'POST',
        body: JSON.stringify({ mode }),
      })
      setToast(`${lead.name || lead.external_id} moved to on hold`)
    }

    await Promise.all([loadLeads(), loadThreads()])
  } catch (error) {
    setToast(`Lead update failed: ${error.message}`)
  } finally {
    processingLeadId.value = null
  }
}

const openThread = async (thread) => {
  activeThread.value = thread
  messages.value = []
  isLoadingTranscript.value = true
  try {
    const data = await request(`/messaging/leads/${thread.lead_id}/thread?channel=whatsapp`)
    messages.value = Array.isArray(data?.messages) ? data.messages : []
  } catch (error) {
    setToast(`Transcript failed: ${error.message}`)
  } finally {
    isLoadingTranscript.value = false
  }
}

const getLeadThread = (lead) => (
  threads.value.find((item) => Number(item.lead_id) === Number(lead?.id || 0)) || null
)

const resetActiveThread = async () => {
  if (!activeThread.value?.thread_id) return
  if (!window.confirm(`Reset the conversation with "${activeThread.value.lead_name || activeThread.value.lead_external_id || 'this contact'}"? This will archive the current thread and start a fresh one.`)) {
    return
  }

  isResettingThread.value = true
  resettingLeadId.value = activeThread.value?.lead_id ?? null
  try {
    const result = await request(`/messaging/threads/${activeThread.value.thread_id}/reset`, {
      method: 'POST',
    })
    await loadThreads()
    const nextThread = threads.value.find((item) => Number(item.thread_id) === Number(result?.new_thread_id))
      || threads.value.find((item) => Number(item.lead_id) === Number(activeThread.value?.lead_id))

    if (nextThread) {
      await openThread(nextThread)
    } else {
      activeThread.value = null
      messages.value = []
    }
    setToast('Conversation reset. A fresh thread is ready.')
  } catch (error) {
    setToast(`Reset failed: ${error.message}`)
  } finally {
    isResettingThread.value = false
    resettingLeadId.value = null
  }
}

const resetLeadThread = async (lead) => {
  const thread = getLeadThread(lead)
  if (!thread?.thread_id) {
    setToast('No conversation thread exists for this contact yet')
    return
  }
  if (!window.confirm(`Reset the conversation with "${lead.name || lead.external_id || 'this contact'}"? This will archive the current thread and start a fresh one.`)) {
    return
  }

  isResettingThread.value = true
  resettingLeadId.value = lead.id
  try {
    const result = await request(`/messaging/threads/${thread.thread_id}/reset`, {
      method: 'POST',
    })
    await Promise.all([loadThreads(), loadLeads()])

    if (activeThread.value?.thread_id && Number(activeThread.value.thread_id) === Number(thread.thread_id)) {
      const nextThread = threads.value.find((item) => Number(item.thread_id) === Number(result?.new_thread_id))
        || threads.value.find((item) => Number(item.lead_id) === Number(lead.id))

      if (nextThread) {
        await openThread(nextThread)
      } else {
        activeThread.value = null
        messages.value = []
      }
    }

    setToast('Conversation reset. A fresh thread is ready.')
  } catch (error) {
    setToast(`Reset failed: ${error.message}`)
  } finally {
    isResettingThread.value = false
    resettingLeadId.value = null
  }
}

const openLeadInbox = async (lead) => {
  setTab('inbox')
  const thread = getLeadThread(lead)
  if (!thread) {
    setToast('No conversation thread exists for this contact yet')
    return
  }
  await openThread(thread)
}

const chooseSalesMaterialFile = () => {
  salesMaterialMode.value = 'file'
  salesMaterialInput.value?.click()
}

const onSalesMaterialSelected = (event) => {
  selectedSalesMaterialFile.value = event.target.files?.[0] ?? null
}

const resetSalesMaterialDraft = () => {
  selectedSalesMaterialFile.value = null
  salesMaterialDescription.value = ''
  salesMaterialUrl.value = ''
  salesMaterialMode.value = 'file'
  if (salesMaterialInput.value) salesMaterialInput.value.value = ''
}

const uploadSalesMaterial = async () => {
  if (!form.id || !selectedSalesMaterialFile.value || !salesMaterialDescription.value.trim()) return

  isUploadingSalesMaterial.value = true
  try {
    const body = new FormData()
    body.append('file', selectedSalesMaterialFile.value)
    body.append('description', salesMaterialDescription.value.trim())
    await request(`/agents/${form.id}/sales-materials`, {
      method: 'POST',
      body,
    })
    resetSalesMaterialDraft()
    await loadSalesMaterials()
    setToast('Sales material uploaded')
  } catch (error) {
    setToast(`Upload failed: ${error.message}`)
  } finally {
    isUploadingSalesMaterial.value = false
  }
}

const createSalesMaterialLink = async () => {
  if (!form.id || !salesMaterialUrl.value.trim() || !salesMaterialDescription.value.trim()) return

  isUploadingSalesMaterial.value = true
  try {
    await request(`/agents/${form.id}/sales-materials/link`, {
      method: 'POST',
      body: JSON.stringify({
        url: salesMaterialUrl.value.trim(),
        description: salesMaterialDescription.value.trim(),
      }),
    })
    resetSalesMaterialDraft()
    await loadSalesMaterials()
    setToast('Sales material link saved')
  } catch (error) {
    setToast(`Save failed: ${error.message}`)
  } finally {
    isUploadingSalesMaterial.value = false
  }
}

const deleteSalesMaterial = async (materialId) => {
  if (!form.id) return
  if (!window.confirm('Delete this sales material?')) return

  try {
    await request(`/agents/${form.id}/sales-materials/${materialId}`, { method: 'DELETE' })
    await loadSalesMaterials()
    setToast('Sales material deleted')
  } catch (error) {
    setToast(`Delete failed: ${error.message}`)
  }
}

watch(() => route.params.agentId, loadDashboard)
onMounted(loadDashboard)
</script>

<template>
  <div class="space-y-6 pb-12">
    <div
      v-if="toast"
      class="fixed left-1/2 top-20 z-50 flex -translate-x-1/2 items-center gap-2 rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-lg"
    >
      <span class="material-symbols-outlined text-sm">check_circle</span>
      {{ toast }}
    </div>

    <section v-if="loading" class="rounded-[2rem] border border-line/80 bg-surface-elevated/90 p-12 text-center shadow-shell">
      <p class="text-sm font-semibold text-ink-muted">Loading agent dashboard...</p>
    </section>

    <section v-else-if="missingAgent" class="rounded-[2rem] border border-line/80 bg-surface-elevated/90 p-12 text-center shadow-shell">
      <span class="material-symbols-outlined text-5xl text-ink-subtle">search_off</span>
      <h1 class="mt-4 text-2xl font-bold text-ink">Agent not found</h1>
      <p class="mt-2 text-sm text-ink-muted">This agent may have been deleted or the link is outdated.</p>
      <button
        type="button"
        @click="router.push('/agents')"
        class="mt-6 inline-flex items-center gap-2 rounded-2xl bg-primary px-5 py-3 text-sm font-bold text-white"
      >
        <span class="material-symbols-outlined text-[18px]">arrow_back</span>
        Back to agents
      </button>
    </section>

    <template v-else>
      <section class="rounded-[2rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell backdrop-blur-xl sm:p-6">
        <div class="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div class="min-w-0 max-w-3xl">
            <button
              type="button"
              @click="router.push('/agents')"
              class="inline-flex items-center gap-2 text-sm font-semibold text-ink-muted transition-colors hover:text-primary"
            >
              <span class="material-symbols-outlined text-[18px]">arrow_back</span>
              Back to agents
            </button>
            <p class="mt-4 text-[11px] font-bold uppercase tracking-[0.28em] text-ink-subtle">Agent Dashboard</p>
            <h1 class="mt-2 truncate text-3xl font-bold tracking-[-0.03em] text-ink">{{ form.name || 'Untitled agent' }}</h1>
            <p class="mt-3 text-sm leading-6 text-ink-muted">
              One place for this agent’s settings, WhatsApp assignment, knowledge, inbox, and contacts.
            </p>
          </div>

          <div class="grid gap-3 sm:grid-cols-3">
            <div class="rounded-2xl border border-line/80 bg-surface px-4 py-3 text-sm">
              <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Assigned WhatsApp</p>
              <p class="mt-1 text-sm font-bold text-ink">
                {{ assignedChannel ? getChannelIdentity(assignedChannel) : 'Unassigned' }}
              </p>
            </div>
            <div class="rounded-2xl border border-line/80 bg-surface px-4 py-3 text-sm">
              <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Contacts</p>
              <p class="mt-1 text-2xl font-bold text-ink">{{ leads.length }}</p>
            </div>
            <div class="rounded-2xl border border-line/80 bg-surface px-4 py-3 text-sm">
              <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Threads</p>
              <p class="mt-1 text-2xl font-bold text-ink">{{ threads.length }}</p>
            </div>
          </div>
        </div>

        <div class="mt-6 flex flex-wrap gap-2">
          <button
            v-for="tab in [
              { id: 'settings', label: 'Settings', icon: 'tune' },
              { id: 'channels', label: 'Channels', icon: 'hub' },
              { id: 'knowledge', label: 'Knowledge', icon: 'menu_book' },
              { id: 'inbox', label: 'Inbox', icon: 'inbox' },
              { id: 'contacts', label: 'Contacts', icon: 'contacts' },
            ]"
            :key="tab.id"
            type="button"
            @click="setTab(tab.id)"
            class="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-colors"
            :class="activeTab === tab.id ? 'bg-primary text-white' : 'bg-surface text-ink-muted hover:bg-surface-muted hover:text-ink'"
          >
            <span class="material-symbols-outlined text-[18px]">{{ tab.icon }}</span>
            {{ tab.label }}
          </button>
        </div>
      </section>

      <section v-if="activeTab === 'settings'" class="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_360px]">
        <div class="space-y-6">
          <article class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell sm:p-6">
            <div class="flex items-start justify-between gap-4 border-b border-line/70 pb-4">
              <div>
                <h2 class="text-xl font-bold text-ink">Agent Settings</h2>
                <p class="mt-1 text-sm text-ink-muted">Behavior, tone, and WhatsApp routing for this agent.</p>
              </div>
              <button
                type="button"
                @click="deleteAgent"
                :disabled="isDeletingAgent"
                class="inline-flex items-center gap-2 rounded-2xl border border-red-200 bg-white px-4 py-2.5 text-sm font-bold text-red-500 transition-colors hover:bg-red-50 disabled:opacity-60"
              >
                <span class="material-symbols-outlined text-[18px]">delete</span>
                {{ isDeletingAgent ? 'Deleting...' : 'Delete' }}
              </button>
            </div>

            <div class="mt-6 space-y-5">
              <div class="space-y-2">
                <label class="px-1 text-sm font-semibold text-ink">Agent Name</label>
                <input
                  v-model="form.name"
                  type="text"
                  class="h-14 w-full rounded-2xl border border-line/80 bg-surface px-4 text-ink placeholder:text-ink-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>

              <div class="space-y-2">
                <div class="flex items-center justify-between px-1">
                  <label class="text-sm font-semibold text-ink">System Instructions</label>
                  <button type="button" @click="setTab('channels')" class="text-xs font-semibold text-primary hover:underline">
                    Manage WhatsApp
                  </button>
                </div>
                <textarea
                  v-model="form.system_prompt"
                  class="min-h-[220px] w-full rounded-2xl border border-line/80 bg-surface p-4 text-ink placeholder:text-ink-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  placeholder="Describe how the agent should behave, speak, qualify leads, and escalate."
                ></textarea>
              </div>

              <div class="grid gap-4 lg:grid-cols-2">
                <div class="rounded-[1.5rem] border border-line/80 bg-surface p-4">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <p class="font-semibold text-ink">Mimic Human Typing</p>
                      <p class="mt-1 text-xs text-ink-muted">Use segmented WhatsApp-style pacing.</p>
                    </div>
                    <label class="relative inline-flex cursor-pointer items-center">
                      <input v-model="form.mimic_human_typing" type="checkbox" class="peer sr-only" />
                      <div class="h-6 w-11 rounded-full bg-slate-200 transition peer-checked:bg-primary peer-checked:after:translate-x-full after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all"></div>
                    </label>
                  </div>
                </div>

                <div class="rounded-[1.5rem] border border-line/80 bg-surface p-4">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="font-semibold text-ink">Assigned WhatsApp</p>
                      <p class="mt-1 text-xs text-ink-muted">
                        {{ assignedChannel ? getChannelIdentity(assignedChannel) : 'No WhatsApp selected' }}
                      </p>
                    </div>
                    <span
                      class="rounded-full px-3 py-1 text-xs font-bold"
                      :class="assignedChannel && isConnectedChannelStatus(assignedChannel.status)
                        ? 'bg-emerald-500/10 text-emerald-700'
                        : 'bg-amber-500/10 text-amber-700'"
                    >
                      {{ assignedChannel && isConnectedChannelStatus(assignedChannel.status) ? 'Connected' : 'Needs setup' }}
                    </span>
                  </div>
                </div>
              </div>

              <div class="rounded-[1.5rem] border border-line/80 bg-surface p-4">
                <div class="flex items-center justify-between">
                  <p class="font-semibold text-ink">Emoji Level</p>
                  <span class="text-xs font-bold uppercase tracking-[0.18em] text-ink-subtle">{{ form.emoji_level }}</span>
                </div>
                <div class="mt-4 grid gap-2 sm:grid-cols-3">
                  <button
                    v-for="option in [{ value: 'none', label: 'No emoji' }, { value: 'low', label: 'Low emoji' }, { value: 'high', label: 'High emoji' }]"
                    :key="option.value"
                    type="button"
                    @click="form.emoji_level = option.value"
                    class="rounded-xl border px-3 py-2 text-sm font-bold transition-colors"
                    :class="form.emoji_level === option.value ? 'border-primary bg-primary text-white' : 'border-line/80 bg-surface text-ink-muted hover:bg-surface-muted'"
                  >
                    {{ option.label }}
                  </button>
                </div>
              </div>

              <div class="rounded-[1.5rem] border border-line/80 bg-surface p-4">
                <div class="flex items-center justify-between">
                  <p class="font-semibold text-ink">Segment Delay</p>
                  <span class="text-xs font-bold text-primary">{{ form.segment_delay_ms }}ms</span>
                </div>
                <input
                  v-model.number="form.segment_delay_ms"
                  type="range"
                  min="200"
                  max="3000"
                  step="100"
                  class="mt-4 w-full cursor-pointer"
                />
              </div>
            </div>
          </article>

          <article class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell sm:p-6">
            <div class="flex items-center justify-between gap-4 border-b border-line/70 pb-4">
              <div>
                <h2 class="text-xl font-bold text-ink">Sales Materials</h2>
                <p class="mt-1 text-sm text-ink-muted">Files or links this agent can send in conversations.</p>
              </div>
            </div>

            <input
              ref="salesMaterialInput"
              type="file"
              accept="application/pdf,image/*"
              class="hidden"
              @change="onSalesMaterialSelected"
            />

            <div class="mt-5 grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
              <div class="rounded-[1.5rem] border border-line/80 bg-surface p-4">
                <div class="grid gap-2">
                  <button
                    type="button"
                    @click="salesMaterialMode = 'file'"
                    class="rounded-xl border px-4 py-2 text-sm font-bold transition-colors"
                    :class="salesMaterialMode === 'file' ? 'border-primary bg-primary text-white' : 'border-line/80 bg-surface text-ink-muted hover:bg-surface-muted'"
                  >
                    File / PDF
                  </button>
                  <button
                    type="button"
                    @click="salesMaterialMode = 'url'"
                    class="rounded-xl border px-4 py-2 text-sm font-bold transition-colors"
                    :class="salesMaterialMode === 'url' ? 'border-primary bg-primary text-white' : 'border-line/80 bg-surface text-ink-muted hover:bg-surface-muted'"
                  >
                    URL / YouTube
                  </button>
                </div>
                <button
                  v-if="salesMaterialMode === 'file'"
                  type="button"
                  @click="chooseSalesMaterialFile"
                  class="mt-4 w-full rounded-xl bg-primary px-4 py-3 text-sm font-bold text-white"
                >
                  Choose file
                </button>
              </div>

              <div class="space-y-4 rounded-[1.5rem] border border-line/80 bg-surface p-4">
                <div v-if="salesMaterialMode === 'file'" class="rounded-2xl border border-dashed border-line/80 px-4 py-4 text-sm text-ink-muted">
                  {{ selectedSalesMaterialFile ? `${selectedSalesMaterialFile.name} · ${formatFileSize(selectedSalesMaterialFile.size)}` : 'Pick a brochure or image up to 30 MB.' }}
                </div>
                <div v-else class="space-y-2">
                  <label class="px-1 text-sm font-semibold text-ink">Target URL</label>
                  <input
                    v-model="salesMaterialUrl"
                    type="url"
                    class="h-12 w-full rounded-xl border border-line/80 bg-surface px-4 text-ink placeholder:text-ink-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="https://example.com/brochure"
                  />
                </div>

                <div class="space-y-2">
                  <label class="px-1 text-sm font-semibold text-ink">Description</label>
                  <textarea
                    v-model="salesMaterialDescription"
                    class="min-h-[96px] w-full rounded-xl border border-line/80 bg-surface p-4 text-ink placeholder:text-ink-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="Explain when the agent should send this material."
                  ></textarea>
                </div>

                <button
                  type="button"
                  @click="salesMaterialMode === 'file' ? uploadSalesMaterial() : createSalesMaterialLink()"
                  :disabled="isUploadingSalesMaterial"
                  class="rounded-xl bg-slate-900 px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                >
                  {{ isUploadingSalesMaterial ? 'Saving...' : salesMaterialMode === 'file' ? 'Save file material' : 'Save link material' }}
                </button>
              </div>
            </div>

            <div class="mt-5 space-y-3">
              <div v-if="salesMaterials.length === 0" class="rounded-2xl border border-dashed border-line/80 px-4 py-6 text-sm text-ink-muted">
                No sales materials uploaded for this agent yet.
              </div>
              <div
                v-for="material in salesMaterials"
                :key="material.id"
                class="rounded-[1.4rem] border border-line/80 bg-surface p-4"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="font-semibold text-ink">{{ material.filename }}</p>
                    <p class="mt-1 text-xs uppercase tracking-[0.18em] text-ink-subtle">
                      {{ material.kind }}<span v-if="material.source_type !== 'url'"> · {{ formatFileSize(material.file_size_bytes) }}</span>
                    </p>
                    <p class="mt-2 text-sm text-ink-muted">{{ material.description }}</p>
                    <a :href="material.public_url" target="_blank" class="mt-3 inline-flex items-center gap-2 text-xs font-bold text-primary hover:underline">
                      <span class="material-symbols-outlined text-[16px]">open_in_new</span>
                      Open
                    </a>
                  </div>
                  <button
                    type="button"
                    @click="deleteSalesMaterial(material.id)"
                    class="rounded-lg border border-line/80 px-3 py-2 text-xs font-bold text-ink-muted hover:border-red-300 hover:text-red-500"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          </article>
        </div>

        <aside class="space-y-6">
          <article class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell">
            <div class="px-1">
              <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Quick Save</p>
              <h2 class="mt-2 text-xl font-bold text-ink">Commit agent settings</h2>
              <p class="mt-2 text-sm leading-6 text-ink-muted">Save behavior and channel routing changes for this specific agent.</p>
            </div>
            <button
              type="button"
              @click="saveAgent()"
              :disabled="isSavingAgent"
              class="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-bold text-white shadow-[0_18px_35px_-20px_rgb(var(--accent-rgb)_/_0.8)] transition-transform hover:-translate-y-0.5 disabled:opacity-60"
            >
              <span v-if="isSavingAgent" class="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
              <span v-else class="material-symbols-outlined text-[20px]">save</span>
              {{ isSavingAgent ? 'Saving...' : 'Save Settings' }}
            </button>
          </article>

          <article class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell">
            <div class="flex items-center justify-between gap-4 pb-4">
              <div>
                <h2 class="text-xl font-bold text-ink">Skills</h2>
                <p class="mt-1 text-sm text-ink-muted">MCP tools this agent can use.</p>
              </div>
            </div>
            <div v-if="mcpServers.length === 0" class="rounded-2xl border border-dashed border-line/80 px-4 py-6 text-sm text-ink-muted">
              No skills registered yet.
            </div>
            <div v-else class="space-y-3">
              <div
                v-for="server in mcpServers"
                :key="server.id"
                class="flex items-center justify-between gap-3 rounded-2xl border border-line/80 px-4 py-3"
              >
                <div class="min-w-0">
                  <p class="truncate font-semibold text-ink">{{ server.name }}</p>
                  <p class="truncate text-xs text-ink-muted">{{ server.description }}</p>
                </div>
                <label class="relative inline-flex cursor-pointer items-center">
                  <input
                    :checked="form.linkedMcpIds.includes(server.id)"
                    type="checkbox"
                    class="peer sr-only"
                    @change="toggleSkill(server.id)"
                  />
                  <div class="h-6 w-11 rounded-full bg-slate-200 transition peer-checked:bg-primary peer-checked:after:translate-x-full after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all"></div>
                </label>
              </div>
            </div>
          </article>
        </aside>
      </section>

      <section v-else-if="activeTab === 'channels'" class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <article class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell sm:p-6">
          <div class="flex items-center justify-between gap-4 border-b border-line/70 pb-4">
            <div>
              <h2 class="text-xl font-bold text-ink">WhatsApp Routing</h2>
              <p class="mt-1 text-sm text-ink-muted">Choose which connected WhatsApp number this agent owns. Each WhatsApp number can belong to only one agent.</p>
            </div>
            <button
              type="button"
              @click="loadChannels"
              class="inline-flex items-center gap-2 rounded-2xl border border-line/80 bg-surface px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-surface-muted"
            >
              <span class="material-symbols-outlined text-[18px]">refresh</span>
              Refresh
            </button>
          </div>

          <div class="mt-5 space-y-3">
            <label class="flex items-start gap-3 rounded-[1.4rem] border border-line/80 bg-surface p-4">
              <input v-model="form.preferred_channel_session_id" :value="null" type="radio" name="preferredChannel" class="mt-1 h-4 w-4" />
              <div>
                <p class="font-semibold text-ink">No WhatsApp assigned</p>
                <p class="mt-1 text-sm text-ink-muted">Agent-driven outbound work stays blocked until one exact WhatsApp channel is assigned.</p>
              </div>
            </label>

            <label
              v-for="session in channels"
              :key="session.id"
              class="flex items-start gap-3 rounded-[1.4rem] border p-4"
              :class="getChannelOwner(session.id)
                ? 'cursor-not-allowed border-line/80 bg-surface-muted/70 opacity-70'
                : (Number(form.preferred_channel_session_id) === Number(session.id) ? 'border-primary/40 bg-primary/5' : 'border-line/80 bg-surface')"
            >
              <input
                v-model="form.preferred_channel_session_id"
                :value="session.id"
                :disabled="Boolean(getChannelOwner(session.id))"
                type="radio"
                name="preferredChannel"
                class="mt-1 h-4 w-4"
              />
              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="font-semibold text-ink">{{ getChannelIdentity(session) }}</p>
                    <p class="mt-1 text-sm text-ink-muted">{{ getChannelDescription(session) || 'No description saved.' }}</p>
                    <p v-if="getChannelOwner(session.id)" class="mt-2 text-xs font-semibold text-amber-700">
                      Already assigned to {{ getChannelOwner(session.id).name || `Agent #${getChannelOwner(session.id).id}` }}
                    </p>
                  </div>
                  <span
                    class="rounded-full px-3 py-1 text-xs font-bold"
                    :class="getChannelOwner(session.id)
                      ? 'bg-amber-500/10 text-amber-700'
                      : (isConnectedChannelStatus(session.status) ? 'bg-emerald-500/10 text-emerald-700' : 'bg-amber-500/10 text-amber-700')"
                  >
                    {{ getChannelOwner(session.id) ? 'In Use' : (isConnectedChannelStatus(session.status) ? 'Connected' : 'Needs setup') }}
                  </span>
                </div>
                <div class="mt-3 flex flex-wrap gap-2 text-xs text-ink-muted">
                  <span class="rounded-full bg-surface-muted px-3 py-1">Provider: {{ getProviderSessionId(session) }}</span>
                  <span class="rounded-full bg-surface-muted px-3 py-1">Session #{{ session.id }}</span>
                </div>
              </div>
            </label>

            <div v-if="channels.length === 0" class="rounded-2xl border border-dashed border-line/80 px-4 py-8 text-center text-sm text-ink-muted">
              No WhatsApp channels connected yet.
            </div>
          </div>
        </article>

        <aside class="space-y-6">
          <article class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell">
            <h2 class="text-xl font-bold text-ink">Current Routing</h2>
            <p class="mt-2 text-sm leading-6 text-ink-muted">
              New outbound starts and follow-ups use this agent's assigned WhatsApp. If that channel is disconnected, the send should stop instead of silently switching to another number.
            </p>
            <div class="mt-5 rounded-[1.4rem] border border-line/80 bg-surface p-4">
              <p class="text-[11px] font-bold uppercase tracking-[0.2em] text-ink-subtle">Assigned Number</p>
              <p class="mt-2 text-base font-bold text-ink">
                {{ assignedChannel ? getChannelIdentity(assignedChannel) : 'No assignment yet' }}
              </p>
            </div>
            <button
              type="button"
              @click="saveAgent('Channel routing saved')"
              :disabled="isSavingAgent"
              class="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
            >
              <span class="material-symbols-outlined text-[20px]">save</span>
              Save Channel Routing
            </button>
          </article>

          <article class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell">
            <h2 class="text-xl font-bold text-ink">Need a new WhatsApp?</h2>
            <p class="mt-2 text-sm leading-6 text-ink-muted">
              Connect or refresh WhatsApp sessions from the channel setup page, then come back here to assign one to this agent.
            </p>
            <button
              type="button"
              @click="router.push('/channels')"
              class="mt-5 inline-flex items-center gap-2 rounded-2xl border border-line/80 bg-surface px-4 py-3 text-sm font-bold text-ink transition-colors hover:border-primary/40 hover:text-primary"
            >
              <span class="material-symbols-outlined text-[18px]">open_in_new</span>
              Open Channel Setup
            </button>
          </article>
        </aside>
      </section>

      <section v-else-if="activeTab === 'knowledge'" class="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell">
          <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Knowledge</p>
          <h2 class="mt-2 text-xl font-bold text-ink">Add training material</h2>
          <p class="mt-2 text-sm leading-6 text-ink-muted">Upload PDFs, docs, images, or text files for this specific agent.</p>
          <input ref="knowledgeInput" type="file" class="hidden" @change="uploadKnowledge" />
          <button
            type="button"
            @click="chooseKnowledgeFile"
            :disabled="isUploadingKnowledge"
            class="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
          >
            <span v-if="isUploadingKnowledge" class="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
            <span v-else class="material-symbols-outlined text-[20px]">upload_file</span>
            {{ isUploadingKnowledge ? 'Uploading...' : 'Upload Knowledge File' }}
          </button>
        </aside>

        <article class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell sm:p-6">
          <div class="flex items-center justify-between gap-4 border-b border-line/70 pb-4">
            <div>
              <h2 class="text-xl font-bold text-ink">Knowledge Files</h2>
              <p class="mt-1 text-sm text-ink-muted">{{ knowledgeFiles.length }} files attached to this agent.</p>
            </div>
          </div>

          <div v-if="knowledgeFiles.length === 0" class="mt-5 rounded-2xl border border-dashed border-line/80 px-4 py-10 text-center text-sm text-ink-muted">
            No files uploaded yet.
          </div>

          <div v-else class="mt-5 space-y-3">
            <div
              v-for="file in knowledgeFiles"
              :key="file.id"
              class="rounded-[1.4rem] border border-line/80 bg-surface p-4"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="font-semibold text-ink">{{ file.filename }}</p>
                  <p class="mt-1 text-xs uppercase tracking-[0.18em] text-ink-subtle">
                    {{ new Date(file.created_at).toLocaleString() }}
                  </p>
                  <p class="mt-3 line-clamp-4 text-sm leading-6 text-ink-muted">{{ file.content }}</p>
                </div>
                <button
                  type="button"
                  @click="deleteKnowledge(file.id)"
                  class="rounded-lg border border-line/80 px-3 py-2 text-xs font-bold text-ink-muted hover:border-red-300 hover:text-red-500"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section v-else-if="activeTab === 'contacts'" class="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell">
          <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Add Contact</p>
          <h2 class="mt-2 text-xl font-bold text-ink">Feed a lead to this agent</h2>
          <p class="mt-2 text-sm leading-6 text-ink-muted">Any contact added here is attached directly to this agent.</p>

          <div class="mt-6 space-y-4">
            <div class="space-y-2">
              <label class="px-1 text-sm font-semibold text-ink">Contact Name</label>
              <input
                v-model="leadDraft.name"
                type="text"
                class="h-12 w-full rounded-xl border border-line/80 bg-surface px-4 text-ink placeholder:text-ink-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="e.g. John Tan"
              />
            </div>
            <div class="space-y-2">
              <label class="px-1 text-sm font-semibold text-ink">Phone / External ID</label>
              <input
                v-model="leadDraft.external_id"
                type="text"
                class="h-12 w-full rounded-xl border border-line/80 bg-surface px-4 text-ink placeholder:text-ink-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="e.g. 60123456789"
              />
            </div>
            <button
              type="button"
              @click="createLead"
              :disabled="isCreatingLead"
              class="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
            >
              <span v-if="isCreatingLead" class="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
              <span v-else class="material-symbols-outlined text-[20px]">person_add</span>
              {{ isCreatingLead ? 'Adding...' : 'Add Contact' }}
            </button>
          </div>
        </aside>

        <article class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell sm:p-6">
          <div class="flex items-center justify-between gap-4 border-b border-line/70 pb-4">
            <div>
              <h2 class="text-xl font-bold text-ink">Agent Contacts</h2>
              <p class="mt-1 text-sm text-ink-muted">{{ leads.length }} contacts linked to this agent.</p>
            </div>
          </div>

          <div v-if="leads.length === 0" class="mt-5 rounded-2xl border border-dashed border-line/80 px-4 py-10 text-center text-sm text-ink-muted">
            No contacts added yet.
          </div>

          <div v-else class="mt-5 space-y-3">
            <div
              v-for="lead in leads"
              :key="lead.id"
              class="rounded-[1.4rem] border border-line/80 bg-surface p-4"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="font-semibold text-ink">{{ lead.name || 'Unnamed contact' }}</p>
                  <p class="mt-1 text-sm text-ink-muted">{{ lead.external_id }}</p>
                  <div class="mt-3 flex flex-wrap gap-2 text-xs">
                    <span class="rounded-full bg-surface-muted px-3 py-1 text-ink-subtle">{{ lead.stage }}</span>
                    <span
                      class="rounded-full px-3 py-1 font-semibold"
                      :class="getLeadModeLabel(lead) === 'working'
                        ? 'bg-emerald-500/10 text-emerald-700'
                        : 'bg-amber-500/10 text-amber-700'"
                    >
                      {{ getLeadModeLabel(lead) === 'working' ? 'Working' : 'On Hold' }}
                    </span>
                    <span class="rounded-full bg-surface-muted px-3 py-1 text-ink-subtle">{{ formatFollowUp(lead) }}</span>
                  </div>
                </div>
                <div class="flex flex-col items-end gap-2">
                  <button
                    type="button"
                    @click="setLeadMode(lead, getLeadModeLabel(lead) === 'working' ? 'on_hold' : 'working')"
                    :disabled="processingLeadId === lead.id"
                    class="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-bold text-white transition-colors disabled:opacity-60"
                    :class="getLeadModeLabel(lead) === 'working'
                      ? 'bg-amber-500 hover:bg-amber-600'
                      : 'bg-primary hover:bg-primary/90'"
                  >
                    <span v-if="processingLeadId === lead.id" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
                    <span v-else class="material-symbols-outlined text-[16px]">
                      {{ getLeadModeLabel(lead) === 'working' ? 'pause_circle' : 'play_circle' }}
                    </span>
                    {{ getLeadModeLabel(lead) === 'working' ? 'Put On Hold' : 'Start Working' }}
                  </button>
                  <button
                    type="button"
                    @click="resetLeadThread(lead)"
                    :disabled="isResettingThread || !getLeadThread(lead)"
                    class="inline-flex items-center gap-2 rounded-xl border border-red-200 px-3 py-2 text-xs font-bold text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span v-if="isResettingThread && Number(resettingLeadId || 0) === Number(lead.id)" class="h-4 w-4 animate-spin rounded-full border-2 border-red-300 border-t-red-600"></span>
                    <span v-else class="material-symbols-outlined text-[16px]">restart_alt</span>
                    Reset Thread
                  </button>
                  <button
                    type="button"
                    @click="openLeadInbox(lead)"
                    class="inline-flex items-center gap-2 rounded-xl border border-line/80 px-3 py-2 text-xs font-bold text-ink transition-colors hover:border-primary/40 hover:text-primary"
                  >
                    <span class="material-symbols-outlined text-[16px]">forum</span>
                    Inbox
                  </button>
                </div>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section v-else class="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell sm:p-6">
          <div class="flex items-center justify-between gap-4 border-b border-line/70 pb-4">
            <div>
              <h2 class="text-xl font-bold text-ink">Inbox</h2>
              <p class="mt-1 text-sm text-ink-muted">Conversations handled by this agent.</p>
            </div>
          </div>

          <div v-if="threads.length === 0" class="mt-5 rounded-2xl border border-dashed border-line/80 px-4 py-10 text-center text-sm text-ink-muted">
            No conversations for this agent yet.
          </div>

          <div v-else class="mt-5 space-y-3">
            <button
              v-for="thread in threads"
              :key="thread.thread_id"
              type="button"
              @click="openThread(thread)"
              class="w-full rounded-[1.4rem] border p-4 text-left transition-colors"
              :class="activeThread?.thread_id === thread.thread_id ? 'border-primary/40 bg-primary/5' : 'border-line/80 bg-surface hover:border-line-strong hover:bg-surface-muted'"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="truncate font-semibold text-ink">{{ thread.lead_name || thread.lead_external_id || 'Unknown lead' }}</p>
                  <p class="mt-1 line-clamp-2 text-sm text-ink-muted">{{ thread.last_message_preview || 'No preview yet.' }}</p>
                </div>
                <span class="text-[11px] font-bold uppercase tracking-[0.16em] text-ink-subtle">
                  {{ thread.pending_scan ? 'New' : 'Seen' }}
                </span>
              </div>
            </button>
          </div>
        </aside>

        <article class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell sm:p-6">
          <div class="flex items-center justify-between gap-4 border-b border-line/70 pb-4">
            <div>
              <h2 class="text-xl font-bold text-ink">{{ activeThread?.lead_name || 'Select a conversation' }}</h2>
              <p class="mt-1 text-sm text-ink-muted">
                {{ activeThread?.lead_external_id || 'Choose a thread on the left to inspect the transcript.' }}
              </p>
            </div>
            <button
              v-if="activeThread"
              type="button"
              class="inline-flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-4 py-2 text-xs font-bold uppercase tracking-[0.18em] text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="isResettingThread"
              @click="resetActiveThread"
            >
              <span class="material-symbols-outlined text-[16px]">restart_alt</span>
              {{ isResettingThread ? 'Resetting...' : 'Reset Thread' }}
            </button>
          </div>

          <div v-if="!activeThread" class="mt-5 rounded-2xl border border-dashed border-line/80 px-4 py-12 text-center text-sm text-ink-muted">
            Pick a conversation to see the transcript.
          </div>

          <div v-else-if="isLoadingTranscript" class="mt-5 rounded-2xl border border-line/80 px-4 py-12 text-center text-sm text-ink-muted">
            Loading transcript...
          </div>

          <div v-else-if="messages.length === 0" class="mt-5 rounded-2xl border border-dashed border-line/80 px-4 py-12 text-center text-sm text-ink-muted">
            No messages found in this transcript yet.
          </div>

          <div v-else class="mt-5 space-y-4">
            <div
              v-for="message in messages"
              :key="message.id"
              class="flex"
              :class="message.direction === 'outbound' ? 'justify-end' : 'justify-start'"
            >
              <div
                class="max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm"
                :class="message.direction === 'outbound' ? 'bg-primary text-white' : 'border border-line/80 bg-surface text-ink'"
              >
                <p class="whitespace-pre-wrap">{{ message.text_content || '(media attached)' }}</p>
                <p
                  class="mt-2 text-[11px] font-semibold"
                  :class="message.direction === 'outbound' ? 'text-white/70' : 'text-ink-subtle'"
                >
                  {{ new Date(message.created_at).toLocaleString() }}
                </p>
              </div>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
input[type='range'] {
  accent-color: var(--primary);
}
</style>
