<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { request } from '../services/api'
import { store } from '../store'

const mcpServers = ref([])
const selectedAgentId = ref(null)
const isSaving = ref(false)
const isDeleting = ref(false)
const message = ref('')
const salesMaterials = ref([])
const isLoadingSalesMaterials = ref(false)
const isUploadingSalesMaterial = ref(false)
const salesMaterialDescription = ref('')
const selectedSalesMaterialFile = ref(null)
const salesMaterialInput = ref(null)

const createDefaultForm = () => ({
  id: null,
  name: '',
  system_prompt: '',
  linkedMcpIds: [],
  mimic_human_typing: false,
  emoji_level: 'none',
  segment_delay_ms: 800,
})

const form = reactive(createDefaultForm())

const isCreatingNewAgent = computed(() => selectedAgentId.value === 'new')
const hasAgents = computed(() => store.agents.length > 0)

const extractLinkedMcpIds = (agent) => {
  if (!agent) return []
  if (Array.isArray(agent.linked_mcp_ids)) return agent.linked_mcp_ids
  if (Array.isArray(agent.linkedMcpIds)) return agent.linkedMcpIds
  if (agent.linkedMcpId) return [agent.linkedMcpId]
  if (agent.linked_mcp_id) return [agent.linked_mcp_id]
  return []
}

const resetForm = () => {
  Object.assign(form, createDefaultForm())
}

const applyAgentToForm = (agent) => {
  resetForm()
  if (!agent) return
  form.id = agent.id
  form.name = agent.name ?? ''
  form.system_prompt = agent.system_prompt ?? agent.systemPrompt ?? ''
  form.linkedMcpIds = [...extractLinkedMcpIds(agent)]
  form.mimic_human_typing = agent.mimic_human_typing ?? false
  form.emoji_level = agent.emoji_level ?? 'none'
  form.segment_delay_ms = agent.segment_delay_ms ?? 800
}

const setMessage = (text) => {
  message.value = text
  if (!text) return
  window.clearTimeout(setMessage.timeoutId)
  setMessage.timeoutId = window.setTimeout(() => {
    message.value = ''
  }, 3000)
}
setMessage.timeoutId = null

const formatFileSize = (bytes) => {
  const value = Number(bytes || 0)
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
  if (value >= 1024) return `${Math.round(value / 1024)} KB`
  return `${value} B`
}

const loadMcpServers = async () => {
  try {
    const data = await request('/mcp/servers')
    mcpServers.value = Array.isArray(data)
      ? data.map((server, index) => ({
          id: server.id ?? index,
          name: server.name ?? 'server',
          status: (server.status ?? 'online').toLowerCase(),
          endpoint: server.endpoint ?? server.script ?? '',
          description: server.description || `Tool access via ${server.name}`,
        }))
      : []
  } catch (error) {
    console.error('Failed to load mcp servers', error)
  }
}

const loadSalesMaterials = async (agentId = form.id) => {
  if (!agentId) {
    salesMaterials.value = []
    return
  }

  isLoadingSalesMaterials.value = true
  try {
    const data = await request(`/agents/${agentId}/sales-materials`)
    salesMaterials.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('Failed to load sales materials', error)
    salesMaterials.value = []
  } finally {
    isLoadingSalesMaterials.value = false
  }
}

const openAgent = async (agentId, options = {}) => {
  const { syncStore = true } = options
  const agent = store.agents.find((item) => String(item.id) === String(agentId))
  if (!agent) return

  selectedAgentId.value = agent.id
  applyAgentToForm(agent)
  if (syncStore) {
    store.setActiveAgent(agent.id)
  }
  await loadSalesMaterials(agent.id)
}

const startNewAgent = () => {
  selectedAgentId.value = 'new'
  resetForm()
  salesMaterials.value = []
  selectedSalesMaterialFile.value = null
  salesMaterialDescription.value = ''
  if (salesMaterialInput.value) {
    salesMaterialInput.value.value = ''
  }
}

const initializePage = async () => {
  await store.fetchAgents()
  await loadMcpServers()

  if (store.activeAgentId) {
    await openAgent(store.activeAgentId, { syncStore: false })
    return
  }

  if (store.agents.length > 0) {
    await openAgent(store.agents[0].id, { syncStore: false })
    return
  }

  startNewAgent()
}

watch(
  () => store.activeAgentId,
  async (newAgentId) => {
    if (!newAgentId || isCreatingNewAgent.value || String(newAgentId) === String(selectedAgentId.value)) {
      return
    }
    await openAgent(newAgentId, { syncStore: false })
  }
)

const saveChanges = async () => {
  isSaving.value = true
  try {
    const isEditing = Boolean(form.id)
    const method = form.id ? 'PUT' : 'POST'
    const path = form.id ? `/agents/${form.id}` : '/agents/'
    const payload = {
      name: form.name,
      system_prompt: form.system_prompt,
      mimic_human_typing: form.mimic_human_typing,
      emoji_level: form.emoji_level,
      segment_delay_ms: form.segment_delay_ms,
    }

    const savedAgent = await request(path, {
      method,
      body: JSON.stringify(payload),
    })

    await store.fetchAgents()
    if (savedAgent?.id) {
      await openAgent(savedAgent.id)
    }
    setMessage(isEditing ? 'Agent updated successfully' : 'Agent created successfully')
  } catch (error) {
    console.error('Save failed', error)
    setMessage(`Save failed: ${error.message}`)
  } finally {
    isSaving.value = false
  }
}

const deleteAgent = async () => {
  if (!form.id) return
  if (!window.confirm(`Delete agent "${form.name || 'Untitled agent'}"?`)) return

  isDeleting.value = true
  try {
    await request(`/agents/${form.id}`, { method: 'DELETE' })
    const deletedAgentId = form.id
    await store.fetchAgents()

    if (String(store.activeAgentId) === String(deletedAgentId) && store.agents.length > 0) {
      store.setActiveAgent(store.agents[0].id)
    }

    if (store.agents.length > 0) {
      const nextAgentId = store.activeAgentId ?? store.agents[0].id
      await openAgent(nextAgentId, { syncStore: false })
    } else {
      startNewAgent()
    }

    setMessage('Agent deleted')
  } catch (error) {
    console.error('Delete failed', error)
    setMessage(`Delete failed: ${error.message}`)
  } finally {
    isDeleting.value = false
  }
}

const toggleSkill = async (serverId) => {
  if (!form.id) return

  const linkedIds = Array.isArray(form.linkedMcpIds) ? [...form.linkedMcpIds] : []
  const isLinked = linkedIds.includes(serverId)
  try {
    if (isLinked) {
      await request(`/agents/${form.id}/link-mcp/${serverId}`, { method: 'DELETE' })
      form.linkedMcpIds = linkedIds.filter((id) => id !== serverId)
    } else {
      await request(`/agents/${form.id}/link-mcp/${serverId}`, { method: 'POST' })
      form.linkedMcpIds = [...linkedIds, serverId]
    }

    const agent = store.agents.find((item) => String(item.id) === String(form.id))
    if (agent) {
      agent.linked_mcp_ids = [...form.linkedMcpIds]
      agent.linked_mcp_count = form.linkedMcpIds.length
    }

    setMessage('Skills updated')
  } catch (error) {
    console.error('Link update failed', error)
    setMessage(`Skill update failed: ${error.message}`)
  }
}

const chooseSalesMaterialFile = () => {
  salesMaterialInput.value?.click()
}

const onSalesMaterialSelected = (event) => {
  selectedSalesMaterialFile.value = event.target.files?.[0] ?? null
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

    salesMaterialDescription.value = ''
    selectedSalesMaterialFile.value = null
    if (salesMaterialInput.value) {
      salesMaterialInput.value.value = ''
    }
    await loadSalesMaterials(form.id)
    setMessage('Sales material uploaded successfully')
  } catch (error) {
    console.error('Sales material upload failed', error)
    setMessage(`Upload failed: ${error.message}`)
  } finally {
    isUploadingSalesMaterial.value = false
  }
}

const deleteSalesMaterial = async (materialId) => {
  if (!form.id) return
  if (!window.confirm('Delete this sales material?')) return

  try {
    await request(`/agents/${form.id}/sales-materials/${materialId}`, { method: 'DELETE' })
    await loadSalesMaterials(form.id)
    setMessage('Sales material deleted')
  } catch (error) {
    console.error('Failed to delete sales material', error)
    setMessage(`Delete failed: ${error.message}`)
  }
}

onMounted(() => {
  initializePage()
})
</script>

<template>
  <div class="flex flex-col gap-6 pb-12 text-slate-900 dark:text-slate-100">
    <div
      v-if="message"
      class="fixed left-1/2 top-20 z-50 flex -translate-x-1/2 items-center gap-2 rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-lg"
    >
      <span class="material-symbols-outlined text-sm">check_circle</span>
      {{ message }}
    </div>

    <section class="rounded-[2rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell backdrop-blur-xl sm:p-6">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div class="max-w-2xl">
          <p class="text-[11px] font-bold uppercase tracking-[0.28em] text-ink-subtle">Agent Control</p>
          <h1 class="mt-2 text-3xl font-bold tracking-[-0.03em] text-ink">Manage every agent in one page</h1>
          <p class="mt-3 text-sm leading-6 text-ink-muted">
            Create new agents, switch between them instantly, edit prompts and behavior, attach skills, and remove unused agents without relying on the hover menu.
          </p>
        </div>

        <div class="flex flex-col gap-3 sm:flex-row">
          <div class="rounded-2xl border border-line/80 bg-surface px-4 py-3 text-sm">
            <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Total Agents</p>
            <p class="mt-1 text-2xl font-bold text-ink">{{ store.agents.length }}</p>
          </div>
          <button
            type="button"
            @click="startNewAgent"
            class="inline-flex items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3 text-sm font-bold text-white shadow-[0_18px_35px_-20px_rgb(var(--accent-rgb)_/_0.8)] transition-transform hover:-translate-y-0.5"
          >
            <span class="material-symbols-outlined text-[20px]">add</span>
            <span>Add New Agent</span>
          </button>
        </div>
      </div>
    </section>

    <div class="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
      <aside class="space-y-4">
        <section class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-4 shadow-shell">
          <div class="flex items-center justify-between px-1 pb-3">
            <div>
              <h2 class="text-lg font-bold text-ink">All Agents</h2>
              <p class="text-sm text-ink-muted">Pick any agent to edit it here.</p>
            </div>
            <button
              type="button"
              @click="startNewAgent"
              class="flex h-10 w-10 items-center justify-center rounded-full border border-line/80 bg-surface text-ink transition-colors hover:border-primary/40 hover:text-primary"
            >
              <span class="material-symbols-outlined text-[20px]">add</span>
            </button>
          </div>

          <div class="space-y-3">
            <button
              v-for="agent in store.agents"
              :key="agent.id"
              type="button"
              @click="openAgent(agent.id)"
              class="w-full rounded-[1.4rem] border p-4 text-left transition-all"
              :class="selectedAgentId == agent.id
                ? 'border-primary/40 bg-primary/10 shadow-[0_16px_34px_-28px_rgb(var(--accent-rgb)_/_0.9)]'
                : 'border-line/80 bg-surface hover:border-line-strong hover:bg-surface-muted/70'"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="truncate text-base font-bold text-ink">{{ agent.name || 'Untitled agent' }}</p>
                  <p class="mt-1 line-clamp-2 text-sm text-ink-muted">
                    {{ agent.system_prompt || 'No system prompt yet. Open this agent to define its behavior.' }}
                  </p>
                </div>
                <span
                  v-if="store.activeAgentId == agent.id"
                  class="rounded-full bg-emerald-500/12 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-emerald-600"
                >
                  Live
                </span>
              </div>

              <div class="mt-4 flex items-center gap-2 text-xs font-medium text-ink-subtle">
                <span class="rounded-full bg-surface-muted px-2.5 py-1">{{ extractLinkedMcpIds(agent).length }} skills</span>
                <span class="rounded-full bg-surface-muted px-2.5 py-1">
                  {{ agent.mimic_human_typing ? 'Human style on' : 'Human style off' }}
                </span>
              </div>
            </button>

            <div
              v-if="!hasAgents"
              class="rounded-[1.4rem] border border-dashed border-line bg-surface p-5 text-sm text-ink-muted"
            >
              No agents yet. Start with your first agent and it will appear here for ongoing edits.
            </div>
          </div>
        </section>
      </aside>

      <section class="space-y-6">
        <div class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell sm:p-6">
          <div class="flex flex-col gap-4 border-b border-line/70 pb-5 sm:flex-row sm:items-start sm:justify-between">
            <div class="flex items-center gap-4">
              <div class="flex h-16 w-16 items-center justify-center rounded-full border border-primary/20 bg-primary/10 text-2xl font-bold text-primary">
                {{ form.name ? form.name.charAt(0).toUpperCase() : 'A' }}
              </div>
              <div>
                <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">
                  {{ isCreatingNewAgent ? 'New Agent Draft' : 'Agent Profile' }}
                </p>
                <h2 class="mt-1 text-2xl font-bold tracking-[-0.02em] text-ink">
                  {{ form.name || (isCreatingNewAgent ? 'Create a new agent' : 'Untitled agent') }}
                </h2>
                <p class="mt-2 text-sm text-ink-muted">
                  {{ isCreatingNewAgent
                    ? 'Fill in the profile below, then save to create this agent.'
                    : 'Edit behavior, prompt, skills, and sales assets for this agent.' }}
                </p>
              </div>
            </div>

            <div class="flex flex-wrap items-center gap-3">
              <span
                v-if="form.id && store.activeAgentId == form.id"
                class="rounded-full bg-emerald-500/12 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-emerald-600"
              >
                Active Agent
              </span>
              <button
                v-if="form.id"
                type="button"
                @click="deleteAgent"
                :disabled="isDeleting"
                class="inline-flex items-center justify-center gap-2 rounded-2xl border border-red-200 bg-white px-4 py-2.5 text-sm font-bold text-red-500 transition-colors hover:bg-red-50 disabled:opacity-60"
              >
                <span class="material-symbols-outlined text-[18px]">delete</span>
                <span>{{ isDeleting ? 'Deleting...' : 'Delete Agent' }}</span>
              </button>
            </div>
          </div>

          <div class="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div class="space-y-6">
              <section class="space-y-4">
                <div class="space-y-2">
                  <label class="px-1 text-sm font-semibold text-slate-900 dark:text-slate-100">Agent Name</label>
                  <input
                    v-model="form.name"
                    class="h-14 w-full rounded-2xl border border-slate-200 bg-white px-4 text-slate-900 transition-all placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
                    placeholder="e.g. Sales Closer, Support Concierge, Booking Assistant"
                    type="text"
                  />
                </div>

                <div class="space-y-2">
                  <div class="flex items-center justify-between px-1">
                    <label class="text-sm font-semibold text-slate-900 dark:text-slate-100">System Instructions</label>
                    <span class="hidden text-xs font-mono text-slate-500 sm:inline">system_prompt</span>
                  </div>
                  <textarea
                    v-model="form.system_prompt"
                    class="min-h-[220px] w-full rounded-2xl border border-slate-200 bg-white p-4 text-slate-900 transition-all placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
                    placeholder="Describe how the agent should behave, what it should optimize for, how it should speak, and when it should escalate."
                  ></textarea>
                </div>
              </section>

              <section class="space-y-4">
                <div class="px-1">
                  <h3 class="text-lg font-bold text-slate-900 dark:text-slate-100">Advanced Behaviour</h3>
                  <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Tune how this agent sounds in real conversations.</p>
                </div>

                <div class="rounded-[1.5rem] border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                  <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-5 dark:border-slate-800">
                    <div>
                      <p class="font-medium text-slate-800 dark:text-slate-200">Mimic Human Typing</p>
                      <p class="mt-1 text-xs text-slate-500">Short replies, casual rhythm, and WhatsApp-style pacing.</p>
                    </div>
                    <label class="relative inline-flex cursor-pointer items-center">
                      <input v-model="form.mimic_human_typing" class="peer sr-only" type="checkbox" />
                      <div class="h-6 w-11 rounded-full bg-slate-200 transition peer-checked:bg-primary peer-checked:after:translate-x-full peer-checked:after:border-white after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all dark:bg-slate-700"></div>
                    </label>
                  </div>

                  <div class="space-y-3 border-b border-slate-100 py-5 dark:border-slate-800">
                    <div class="flex items-center justify-between">
                      <p class="font-medium text-slate-800 dark:text-slate-200">Emoji Frequency</p>
                      <span class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">{{ form.emoji_level }}</span>
                    </div>
                    <div class="grid gap-2 sm:grid-cols-3">
                      <button
                        v-for="opt in [{ val: 'none', label: 'No emoji' }, { val: 'low', label: 'Low emoji' }, { val: 'high', label: 'High emoji' }]"
                        :key="opt.val"
                        type="button"
                        @click="form.emoji_level = opt.val"
                        class="rounded-xl border px-3 py-2 text-sm font-bold transition-colors"
                        :class="form.emoji_level === opt.val
                          ? 'border-primary bg-primary text-white'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'"
                      >
                        {{ opt.label }}
                      </button>
                    </div>
                  </div>

                  <div class="space-y-3 pt-5">
                    <div class="flex items-center justify-between">
                      <p class="font-medium text-slate-800 dark:text-slate-200">Segment Delay</p>
                      <span class="text-xs font-bold text-primary">{{ form.segment_delay_ms }}ms</span>
                    </div>
                    <input
                      v-model.number="form.segment_delay_ms"
                      type="range"
                      min="200"
                      max="3000"
                      step="100"
                      class="w-full cursor-pointer appearance-none rounded-full"
                    />
                  </div>
                </div>
              </section>

              <section class="space-y-4">
                <div class="px-1">
                  <h3 class="text-lg font-bold text-slate-900 dark:text-slate-100">Sales Materials</h3>
                  <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Upload PDFs or images for this agent and describe when the AI should send them.
                  </p>
                </div>

                <div class="rounded-[1.5rem] border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                  <div
                    v-if="!form.id"
                    class="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-400"
                  >
                    Save the agent first to unlock file uploads and agent-specific sales materials.
                  </div>

                  <template v-else>
                    <input
                      ref="salesMaterialInput"
                      type="file"
                      accept="application/pdf,image/*"
                      class="hidden"
                      @change="onSalesMaterialSelected"
                    />

                    <div class="flex flex-col gap-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-950/40 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p class="font-semibold text-slate-800 dark:text-slate-100">Upload brochure or promo image</p>
                        <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">PDF up to 15MB. Images up to 8MB.</p>
                      </div>
                      <button
                        type="button"
                        @click="chooseSalesMaterialFile"
                        class="rounded-xl bg-primary px-4 py-2 text-sm font-bold text-white shadow-sm shadow-primary/20"
                      >
                        Choose File
                      </button>
                    </div>

                    <div
                      v-if="selectedSalesMaterialFile"
                      class="mt-4 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:bg-slate-800/70 dark:text-slate-200"
                    >
                      {{ selectedSalesMaterialFile.name }} · {{ formatFileSize(selectedSalesMaterialFile.size) }}
                    </div>

                    <div class="mt-4 space-y-2">
                      <label class="px-1 text-sm font-semibold text-slate-900 dark:text-slate-100">Description</label>
                      <textarea
                        v-model="salesMaterialDescription"
                        class="min-h-[96px] w-full rounded-xl border border-slate-200 bg-white p-4 text-slate-900 placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
                        placeholder="Example: Use this brochure when the customer asks for pricing, package details, or an overview."
                      ></textarea>
                    </div>

                    <button
                      type="button"
                      @click="uploadSalesMaterial"
                      :disabled="isUploadingSalesMaterial || !selectedSalesMaterialFile || !salesMaterialDescription.trim()"
                      class="mt-4 w-full rounded-xl bg-slate-900 py-3 text-sm font-bold text-white disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
                    >
                      {{ isUploadingSalesMaterial ? 'Uploading...' : 'Save Sales Material' }}
                    </button>
                  </template>
                </div>

                <div class="overflow-hidden rounded-[1.5rem] border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
                  <div v-if="isLoadingSalesMaterials" class="px-4 py-6 text-sm text-slate-500 dark:text-slate-400">Loading sales materials...</div>
                  <div v-else-if="salesMaterials.length === 0" class="px-4 py-6 text-sm text-slate-500 dark:text-slate-400">No sales materials uploaded for this agent yet.</div>
                  <template v-else>
                    <div
                      v-for="(material, index) in salesMaterials"
                      :key="material.id"
                      class="p-4"
                      :class="{ 'border-b border-slate-100 dark:border-slate-800': index !== salesMaterials.length - 1 }"
                    >
                      <div class="flex items-start justify-between gap-3">
                        <div class="flex min-w-0 items-start gap-3">
                          <div class="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                            <span class="material-symbols-outlined text-[20px]">{{ material.kind === 'image' ? 'image' : 'picture_as_pdf' }}</span>
                          </div>
                          <div class="min-w-0">
                            <p class="break-all font-semibold text-slate-800 dark:text-slate-100">{{ material.filename }}</p>
                            <p class="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">{{ material.kind }} · {{ formatFileSize(material.file_size_bytes) }}</p>
                            <p class="mt-2 text-sm text-slate-600 dark:text-slate-300">{{ material.description }}</p>
                            <a :href="material.public_url" target="_blank" class="mt-3 inline-flex items-center gap-2 text-xs font-bold text-primary hover:underline">
                              <span class="material-symbols-outlined text-[16px]">open_in_new</span>
                              Open file
                            </a>
                          </div>
                        </div>
                        <button
                          type="button"
                          @click="deleteSalesMaterial(material.id)"
                          class="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 hover:border-red-300 hover:text-red-500 dark:border-slate-700 dark:text-slate-200"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </template>
                </div>
              </section>
            </div>

            <div class="space-y-6">
              <section class="rounded-[1.5rem] border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                <div class="px-1 pb-4">
                  <h3 class="text-lg font-bold text-slate-900 dark:text-slate-100">Skills</h3>
                  <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Enable the MCP tools this agent can use.</p>
                </div>

                <div
                  v-if="!form.id"
                  class="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-400"
                >
                  Save the agent first to attach skills.
                </div>
                <div v-else-if="mcpServers.length === 0" class="px-1 text-sm text-slate-500 dark:text-slate-400">
                  No skills registered in the system yet.
                </div>
                <div v-else class="space-y-3">
                  <div
                    v-for="server in mcpServers"
                    :key="server.id"
                    class="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 px-4 py-3 dark:border-slate-800"
                  >
                    <div class="flex min-w-0 items-center gap-3">
                      <div
                        class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-primary"
                        :class="form.linkedMcpIds.includes(server.id) ? 'bg-primary/20' : 'bg-primary/5'"
                      >
                        <span class="material-symbols-outlined">{{ form.linkedMcpIds.includes(server.id) ? 'check_circle' : 'extension' }}</span>
                      </div>
                      <div class="min-w-0">
                        <p class="truncate font-medium text-slate-800 dark:text-slate-200">{{ server.name }}</p>
                        <p class="truncate text-xs text-slate-500">{{ server.description }}</p>
                      </div>
                    </div>
                    <label class="relative inline-flex cursor-pointer items-center">
                      <input
                        :checked="form.linkedMcpIds.includes(server.id)"
                        class="peer sr-only"
                        type="checkbox"
                        @change="toggleSkill(server.id)"
                      />
                      <div class="h-6 w-11 rounded-full bg-slate-200 transition peer-checked:bg-primary peer-checked:after:translate-x-full peer-checked:after:border-white after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all dark:bg-slate-700"></div>
                    </label>
                  </div>
                </div>
              </section>

              <section class="rounded-[1.5rem] border border-line/80 bg-surface p-4">
                <div class="px-1">
                  <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Quick Actions</p>
                  <h3 class="mt-2 text-lg font-bold text-ink">Save or create instantly</h3>
                  <p class="mt-2 text-sm leading-6 text-ink-muted">
                    This page is now the dedicated place for adding, editing, deleting, and reviewing every agent in your workspace.
                  </p>
                </div>

                <button
                  type="button"
                  @click="saveChanges"
                  :disabled="isSaving"
                  class="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-bold text-white shadow-[0_18px_35px_-20px_rgb(var(--accent-rgb)_/_0.8)] transition-transform hover:-translate-y-0.5 disabled:opacity-60"
                >
                  <span v-if="isSaving" class="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
                  <span v-else class="material-symbols-outlined text-[20px]">{{ form.id ? 'save' : 'add_circle' }}</span>
                  <span>{{ isSaving ? 'Saving...' : form.id ? 'Save Changes' : 'Create Agent' }}</span>
                </button>
              </section>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
input[type='range'] {
  accent-color: var(--primary);
}
</style>
