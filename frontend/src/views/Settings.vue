<script setup>
import { computed, onMounted, ref } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import PlatformAdminShell from '../components/platform/PlatformAdminShell.vue'
import { useTheme } from '../composables/theme'
import { request } from '../services/api'

const zaiKey = ref('')
const zaiMasked = ref('')
const zaiStatus = ref('unknown')
const uniKey = ref('')
const uniMasked = ref('')
const uniStatus = ref('unknown')
const zaiValidationStatus = ref('unknown')
const zaiValidationDetail = ref('')
const uniValidationStatus = ref('unknown')
const uniValidationDetail = ref('')

const llmTasks = ref([])
const llmProviders = ref([])
const llmRouting = ref({})
const llmTaskModels = ref({})
const llmModels = ref([])
const recordContextPrompt = ref(false)

const platformMessages = ref([])
const historyDirection = ref('')
const historyAiOnly = ref(true)
const historyLimit = ref(6)

const platformSystemHealth = ref(null)
const message = ref('')
const isSaving = ref(false)
const isValidating = ref(false)
const isRefreshing = ref(false)
const loadingSettings = ref(true)
const loadingMessages = ref(true)
const loadingHealth = ref(true)
const loadingModels = ref(true)
const availableModels = ref([])

const { theme, toggleTheme } = useTheme()

const adminSections = [
  { label: 'Dashboard', description: 'Operational overview and shortcuts', href: '#overview' },
  { label: 'Platform Setting', description: 'Keys, routing, and defaults', href: '#platform-settings' },
  { label: 'Message Review', description: 'History, traces, and AI usage', href: '#message-review' },
  { label: 'Benchmark', description: 'Provider comparison and latency tests', href: '#benchmark' },
  { label: 'Health', description: 'Readiness and schema diagnostics', href: '#health' }
]

const connectedKeys = computed(() => {
  let count = 0
  if (zaiStatus.value === 'set') count += 1
  if (uniStatus.value === 'set') count += 1
  return count
})

const summaryCards = computed(() => [
  { label: 'Connected keys', value: `${connectedKeys.value}/2`, hint: 'Z.ai and UniAPI' },
  { label: 'Workflow tasks', value: llmTasks.value.length, hint: 'Routing assignments' },
  { label: 'Models published', value: llmModels.value.length, hint: `${llmProviders.value.length} providers` },
  { label: 'Review batch', value: platformMessages.value.length, hint: 'Latest messages loaded' }
])

const healthLabel = computed(() => {
  if (loadingHealth.value) return 'Loading'
  return platformSystemHealth.value?.ready ? 'READY' : 'NOT READY'
})

const toNumber = (value) => {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

const formatUsd = (value, digits = 6) => `$${toNumber(value).toFixed(digits)}`
const formatInt = (value) => toNumber(value).toLocaleString()

const getTotalTokens = (msg) => {
  const total = toNumber(msg?.llm_total_tokens)
  if (total > 0) return total
  return toNumber(msg?.llm_prompt_tokens) + toNumber(msg?.llm_completion_tokens)
}

const getCostUsd = (msg) => {
  const direct = toNumber(msg?.llm_estimated_cost_usd)
  if (direct > 0) return direct
  return toNumber(msg?.ai_trace?.usage?.estimated_cost_usd)
}

const fetchSettings = async () => {
  loadingSettings.value = true
  try {
    const [zaiData, uniData, tasksData, providersData, routingData, taskModelsData, modelsData, contextPromptData] = await Promise.all([
      request('/settings/zai-key'),
      request('/settings/uniapi-key'),
      request('/platform/llm/tasks'),
      request('/platform/llm/providers'),
      request('/platform/llm/routing'),
      request('/platform/llm/task-models'),
      request('/platform/llm/models'),
      request('/platform/settings/record-context-prompt')
    ])

    zaiStatus.value = zaiData.status
    zaiMasked.value = zaiData.masked_key
    uniStatus.value = uniData.status
    uniMasked.value = uniData.masked_key
    llmTasks.value = tasksData || []
    llmProviders.value = providersData || []
    llmRouting.value = routingData || {}
    llmTaskModels.value = taskModelsData || {}
    llmModels.value = Array.isArray(modelsData) ? modelsData : []
    recordContextPrompt.value = !!contextPromptData.value
  } catch (error) {
    message.value = `Failed to load platform settings: ${error.message}`
  } finally {
    loadingSettings.value = false
  }
}

const fetchMessages = async () => {
  loadingMessages.value = true
  try {
    const params = new URLSearchParams()
    params.set('limit', String(historyLimit.value || 6))
    if (historyDirection.value) params.set('direction', historyDirection.value)
    params.set('ai_only', historyAiOnly.value ? 'true' : 'false')
    const data = await request(`/platform/messages/history?${params.toString()}`)
    platformMessages.value = Array.isArray(data) ? data : []
  } catch (error) {
    message.value = `Error: ${error.message}`
    platformMessages.value = []
  } finally {
    loadingMessages.value = false
  }
}

const fetchHealth = async () => {
  loadingHealth.value = true
  try {
    platformSystemHealth.value = await request('/platform/system-health')
  } catch (error) {
    message.value = `Error: ${error.message}`
    platformSystemHealth.value = null
  } finally {
    loadingHealth.value = false
  }
}

const fetchModels = async () => {
  loadingModels.value = true
  try {
    const data = await request('/platform/llm/models')
    availableModels.value = (Array.isArray(data) ? data : []).filter((row) => row.provider === 'uniapi')
  } catch (error) {
    message.value = `Failed to load model catalog: ${error.message}`
  } finally {
    loadingModels.value = false
  }
}

const refreshAll = async () => {
  isRefreshing.value = true
  try {
    await Promise.all([fetchSettings(), fetchMessages(), fetchHealth(), fetchModels()])
  } finally {
    isRefreshing.value = false
  }
}

const saveZai = async () => {
  if (!zaiKey.value) return
  isSaving.value = true
  message.value = 'Saving...'
  try {
    await request('/settings/zai-key', {
      method: 'POST',
      body: JSON.stringify({ api_key: zaiKey.value })
    })
    zaiKey.value = ''
    message.value = 'Z.ai key updated'
    await fetchSettings()
  } catch (error) {
    message.value = `Error: ${error.message}`
  } finally {
    isSaving.value = false
  }
}

const saveUni = async () => {
  if (!uniKey.value) return
  isSaving.value = true
  message.value = 'Saving...'
  try {
    await request('/settings/uniapi-key', {
      method: 'POST',
      body: JSON.stringify({ api_key: uniKey.value })
    })
    uniKey.value = ''
    message.value = 'UniAPI key updated'
    await fetchSettings()
  } catch (error) {
    message.value = `Error: ${error.message}`
  } finally {
    isSaving.value = false
  }
}

const saveRouting = async () => {
  isSaving.value = true
  message.value = 'Saving...'
  try {
    await request('/platform/llm/routing', {
      method: 'POST',
      body: JSON.stringify({ config: llmRouting.value })
    })
    message.value = 'LLM routing strategy updated'
    await fetchSettings()
  } catch (error) {
    message.value = `Error: ${error.message}`
  } finally {
    isSaving.value = false
  }
}

const saveTaskModels = async () => {
  isSaving.value = true
  message.value = 'Saving...'
  try {
    await request('/platform/llm/task-models', {
      method: 'POST',
      body: JSON.stringify({ config: llmTaskModels.value })
    })
    message.value = 'Default task models updated'
    await fetchSettings()
  } catch (error) {
    message.value = `Error: ${error.message}`
  } finally {
    isSaving.value = false
  }
}

const saveRecordContextPrompt = async () => {
  isSaving.value = true
  message.value = 'Saving...'
  try {
    await request('/platform/settings/record-context-prompt', {
      method: 'PUT',
      body: JSON.stringify({ value: recordContextPrompt.value })
    })
    message.value = 'Context prompt recording updated'
    await fetchSettings()
  } catch (error) {
    message.value = `Error: ${error.message}`
  } finally {
    isSaving.value = false
  }
}

const validateProviderKey = async (provider) => {
  isValidating.value = true
  message.value = `Validating ${provider} key...`
  try {
    const payload = {}
    if (provider === 'zai' && zaiKey.value.trim()) payload.api_key = zaiKey.value.trim()
    if (provider === 'uniapi' && uniKey.value.trim()) payload.api_key = uniKey.value.trim()
    const data = await request(`/platform/api-keys/${provider}/validate`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
    if (provider === 'zai') {
      zaiValidationStatus.value = data.status || 'unknown'
      zaiValidationDetail.value = data.detail || ''
    } else {
      uniValidationStatus.value = data.status || 'unknown'
      uniValidationDetail.value = data.detail || ''
    }
    message.value = `${provider.toUpperCase()} validation: ${data.status}`
  } catch (error) {
    if (provider === 'zai') {
      zaiValidationStatus.value = 'invalid'
      zaiValidationDetail.value = error.message || 'Validation failed'
    } else {
      uniValidationStatus.value = 'invalid'
      uniValidationDetail.value = error.message || 'Validation failed'
    }
    message.value = `Validation error: ${error.message}`
  } finally {
    isValidating.value = false
  }
}

const jumpTo = (hash) => {
  window.location.hash = hash
}

onMounted(() => {
  refreshAll()
})
</script>
<template>
  <PlatformAdminShell>
    <template #sidebar>
      <div class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/92 p-5 shadow-panel">
        <p class="text-[10px] font-black uppercase tracking-[0.3em] text-ink-subtle">Platform Admin</p>
        <h2 class="mt-2 text-2xl font-bold text-ink">Console</h2>
        <p class="mt-2 text-sm text-ink-muted">
          A desktop-first workspace for platform-wide keys, routing, message review, and model benchmarking.
        </p>

        <div class="mt-5 grid grid-cols-2 gap-3">
          <div class="rounded-2xl border border-line/70 bg-surface px-3 py-3">
            <p class="text-[10px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Status</p>
            <p class="mt-1 text-sm font-semibold text-ink">{{ healthLabel }}</p>
          </div>
          <div class="rounded-2xl border border-line/70 bg-surface px-3 py-3">
            <p class="text-[10px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Mode</p>
            <p class="mt-1 text-sm font-semibold text-ink">Desktop</p>
          </div>
        </div>

        <nav class="mt-6 space-y-2">
          <a
            v-for="section in adminSections"
            :key="section.href"
            :href="section.href"
            class="group flex items-start justify-between gap-4 rounded-2xl border border-transparent px-4 py-3 transition-colors hover:border-line hover:bg-primary/5"
          >
            <span class="min-w-0">
              <span class="block text-sm font-semibold text-ink">{{ section.label }}</span>
              <span class="mt-0.5 block text-[11px] text-ink-muted">{{ section.description }}</span>
            </span>
            <span class="material-symbols-outlined text-sm text-ink-subtle transition-transform group-hover:translate-x-0.5">arrow_forward</span>
          </a>
        </nav>
      </div>
    </template>

    <section class="rounded-[1.9rem] border border-line/80 bg-[linear-gradient(140deg,_rgb(var(--panel-elevated-rgb)_/_0.96),_rgb(var(--accent-soft-rgb)_/_0.22))] p-6 shadow-panel">
      <div class="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div class="space-y-3">
          <p class="text-[10px] font-black uppercase tracking-[0.32em] text-aurora">Platform Admin Console</p>
          <h1 class="max-w-4xl text-3xl font-black tracking-tight text-ink lg:text-4xl">
            Desktop control room for platform settings, message review, and model benchmarking.
          </h1>
          <p class="max-w-3xl text-sm text-ink-muted">
            Everything stays in one place, but the layout now groups the admin work into clear sections so operators can move faster on a laptop or desktop.
          </p>
          <div class="flex flex-wrap gap-2">
            <TuiBadge variant="success" size="sm">Desktop optimized</TuiBadge>
            <TuiBadge :variant="connectedKeys === 2 ? 'success' : 'warning'" size="sm">
              {{ connectedKeys }}/2 keys connected
            </TuiBadge>
            <TuiBadge :variant="healthLabel === 'READY' ? 'success' : 'warning'" size="sm">
              {{ healthLabel }}
            </TuiBadge>
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <TuiButton @click="refreshAll" :loading="isRefreshing">Refresh All</TuiButton>
          <TuiButton variant="outline" @click="jumpTo('#message-review')">Message Review</TuiButton>
          <TuiButton variant="outline" @click="jumpTo('#benchmark')">Benchmark</TuiButton>
        </div>
      </div>
    </section>

    <section id="overview" class="space-y-4">
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article
          v-for="stat in summaryCards"
          :key="stat.label"
          class="rounded-[1.6rem] border border-line/70 bg-surface-elevated/90 p-5 shadow-[0_20px_40px_-28px_rgb(var(--text-rgb)_/_0.2)]"
        >
          <p class="text-[10px] font-black uppercase tracking-[0.28em] text-ink-subtle">{{ stat.label }}</p>
          <p class="mt-3 text-3xl font-black tracking-tight text-ink">{{ stat.value }}</p>
          <p class="mt-2 text-sm text-ink-muted">{{ stat.hint }}</p>
        </article>
      </div>

      <div class="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <TuiCard title="Dashboard" subtitle="Quick actions and operational shortcuts">
          <div class="grid gap-4 md:grid-cols-2">
            <div class="rounded-2xl border border-line/70 bg-surface px-4 py-4">
              <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Platform setting</p>
              <p class="mt-2 text-sm text-ink-muted">
                Manage provider keys, routing, default models, and context recording without leaving the console.
              </p>
            </div>
            <div class="rounded-2xl border border-line/70 bg-surface px-4 py-4">
              <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Message review</p>
              <p class="mt-2 text-sm text-ink-muted">
                Inspect the latest platform traffic, cost trace data, and AI metadata before diving into the dedicated history page.
              </p>
            </div>
            <div class="rounded-2xl border border-line/70 bg-surface px-4 py-4">
              <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Benchmark</p>
              <p class="mt-2 text-sm text-ink-muted">
                Compare model latency and token usage from the same place you configure providers.
              </p>
            </div>
            <div class="rounded-2xl border border-line/70 bg-surface px-4 py-4">
              <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Health</p>
              <p class="mt-2 text-sm text-ink-muted">
                Use system health and schema readiness as the final check before making platform-wide changes.
              </p>
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Daily Ops" subtitle="Common desktop actions">
          <div class="space-y-3">
            <button
              class="flex w-full items-center justify-between rounded-2xl border border-line/70 bg-surface px-4 py-4 text-left transition-colors hover:border-line-strong hover:bg-primary/5"
              @click="jumpTo('#platform-settings')"
            >
              <span>
                <span class="block text-sm font-semibold text-ink">Jump to platform settings</span>
                <span class="block text-[11px] text-ink-muted">Edit keys and workflow defaults</span>
              </span>
              <span class="material-symbols-outlined text-ink-subtle">tune</span>
            </button>
            <button
              class="flex w-full items-center justify-between rounded-2xl border border-line/70 bg-surface px-4 py-4 text-left transition-colors hover:border-line-strong hover:bg-primary/5"
              @click="jumpTo('#message-review')"
            >
              <span>
                <span class="block text-sm font-semibold text-ink">Open message review</span>
                <span class="block text-[11px] text-ink-muted">Inspect traces and recent usage</span>
              </span>
              <span class="material-symbols-outlined text-ink-subtle">history</span>
            </button>
            <button
              class="flex w-full items-center justify-between rounded-2xl border border-line/70 bg-surface px-4 py-4 text-left transition-colors hover:border-line-strong hover:bg-primary/5"
              @click="jumpTo('#benchmark')"
            >
              <span>
                <span class="block text-sm font-semibold text-ink">Open benchmark section</span>
                <span class="block text-[11px] text-ink-muted">Model catalog and jump to tests</span>
              </span>
              <span class="material-symbols-outlined text-ink-subtle">speed</span>
            </button>
          </div>
        </TuiCard>
      </div>
    </section>

    <section id="platform-settings" class="space-y-4">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="text-[10px] font-black uppercase tracking-[0.28em] text-aurora">Platform Setting</p>
          <h2 class="mt-2 text-2xl font-black text-ink">Keys, routing, and defaults</h2>
          <p class="mt-2 text-sm text-ink-muted">Keep provider access and workflow defaults centralized in one section.</p>
        </div>
        <TuiButton variant="outline" @click="saveRecordContextPrompt" :loading="isSaving" size="sm">Save Platform Setting</TuiButton>
      </div>

      <div v-if="loadingSettings" class="py-4 text-sm text-ink-muted">Loading platform settings...</div>
      <div v-else class="grid gap-4 xl:grid-cols-2">
        <TuiCard title="Provider Keys" subtitle="Validate and update access tokens">
          <div class="grid gap-4 md:grid-cols-2">
            <div class="space-y-4 rounded-[1.5rem] border border-line/70 bg-surface px-4 py-4">
              <div class="flex items-center justify-between gap-3">
                <h3 class="text-lg font-bold text-ink">Z.ai</h3>
                <div class="flex items-center gap-2">
                  <TuiBadge :variant="zaiStatus === 'set' ? 'success' : 'warning'" size="sm">
                    {{ zaiStatus === 'set' ? 'Connected' : 'Missing' }}
                  </TuiBadge>
                  <span v-if="zaiMasked" class="font-mono text-[10px] text-ink-muted">{{ zaiMasked }}</span>
                </div>
              </div>
              <TuiInput v-model="zaiKey" type="password" placeholder="sk-..." label="API Key" />
              <div class="flex flex-col gap-2">
                <TuiButton @click="saveZai" :loading="isSaving" class="w-full">Update Z.ai Key</TuiButton>
                <TuiButton @click="validateProviderKey('zai')" :loading="isValidating" variant="outline" class="w-full">Validate Z.ai Key</TuiButton>
              </div>
              <p v-if="zaiValidationStatus !== 'unknown'" class="text-[11px] font-semibold" :class="zaiValidationStatus === 'valid' ? 'text-emerald-700' : zaiValidationStatus === 'not_set' ? 'text-amber-700' : 'text-red-700'">
                {{ zaiValidationStatus.toUpperCase() }}: {{ zaiValidationDetail }}
              </p>
            </div>

            <div class="space-y-4 rounded-[1.5rem] border border-line/70 bg-surface px-4 py-4">
              <div class="flex items-center justify-between gap-3">
                <h3 class="text-lg font-bold text-ink">UniAPI</h3>
                <div class="flex items-center gap-2">
                  <TuiBadge :variant="uniStatus === 'set' ? 'success' : 'warning'" size="sm">
                    {{ uniStatus === 'set' ? 'Connected' : 'Missing' }}
                  </TuiBadge>
                  <span v-if="uniMasked" class="font-mono text-[10px] text-ink-muted">{{ uniMasked }}</span>
                </div>
              </div>
              <TuiInput v-model="uniKey" type="password" placeholder="Key..." label="UniAPI Key" />
              <div class="flex flex-col gap-2">
                <TuiButton @click="saveUni" :loading="isSaving" variant="outline" class="w-full">Update UniAPI Key</TuiButton>
                <TuiButton @click="validateProviderKey('uniapi')" :loading="isValidating" variant="outline" class="w-full">Validate UniAPI Key</TuiButton>
              </div>
              <p v-if="uniValidationStatus !== 'unknown'" class="text-[11px] font-semibold" :class="uniValidationStatus === 'valid' ? 'text-emerald-700' : uniValidationStatus === 'not_set' ? 'text-amber-700' : 'text-red-700'">
                {{ uniValidationStatus.toUpperCase() }}: {{ uniValidationDetail }}
              </p>
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Workflow Controls" subtitle="Routing, defaults, and context behavior">
          <div class="space-y-6">
            <div class="grid gap-4 md:grid-cols-2">
              <div v-for="task in llmTasks" :key="task" class="space-y-2">
                <label class="block text-xs font-bold uppercase tracking-wider text-ink-subtle">{{ task }}</label>
                <select v-model="llmRouting[task]" class="w-full rounded-2xl border border-line-strong bg-surface-elevated/90 px-4 py-3 text-sm text-ink">
                  <option v-for="provider in llmProviders" :key="provider" :value="provider">
                    {{ provider }}
                  </option>
                </select>
              </div>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <div v-for="task in llmTasks" :key="`model-${task}`" class="space-y-2">
                <label class="block text-xs font-bold uppercase tracking-wider text-ink-subtle">{{ task }}</label>
                <select v-model="llmTaskModels[task]" class="w-full rounded-2xl border border-line-strong bg-surface-elevated/90 px-4 py-3 text-sm text-ink">
                  <option :value="null">Use provider default</option>
                  <option v-for="model in llmModels" :key="`${task}:${model.provider}:${model.schema}:${model.model}`" :value="model.model">
                    {{ model.model }} ({{ model.provider }} · {{ model.schema }})
                  </option>
                </select>
              </div>
            </div>

            <div class="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
              <div class="rounded-[1.5rem] border border-line/70 bg-surface px-4 py-4">
                <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Context Recording</p>
                <p class="mt-2 text-sm text-ink-muted">
                  When enabled, outbound AI rows include <code class="font-mono text-[11px] text-ink">raw_payload.ai_trace.context_prompt</code>.
                </p>
                <label class="mt-4 inline-flex items-center gap-2 text-xs font-bold text-ink">
                  <input v-model="recordContextPrompt" type="checkbox" class="h-4 w-4 rounded border-line text-primary focus:ring-primary" />
                  {{ recordContextPrompt ? 'True' : 'False' }}
                </label>
              </div>

              <div class="rounded-[1.5rem] border border-line/70 bg-surface px-4 py-4">
                <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Theme</p>
                <p class="mt-2 text-sm text-ink-muted">Local browser preference for the admin console.</p>
                <TuiButton variant="outline" @click="toggleTheme" class="mt-4" size="sm">
                  {{ theme === 'dark' ? 'Dark' : 'Light' }} Mode
                </TuiButton>
              </div>
            </div>

            <div class="flex justify-end gap-2">
              <TuiButton @click="saveRouting" :loading="isSaving" size="sm">Save Routing Strategy</TuiButton>
              <TuiButton @click="saveTaskModels" :loading="isSaving" variant="outline" size="sm">Save Model Defaults</TuiButton>
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Available Models" subtitle="Provider catalog returned by the platform API" class="xl:col-span-2">
          <div v-if="loadingModels" class="py-4 text-sm text-ink-muted">Loading models...</div>
          <div v-else-if="availableModels.length === 0" class="py-4 text-sm text-ink-muted">No models published.</div>
          <div v-else class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <article
              v-for="item in availableModels"
              :key="`${item.provider}:${item.schema}:${item.model}`"
              class="rounded-2xl border border-line/70 bg-surface px-4 py-3"
            >
              <p class="text-sm font-bold text-ink">{{ item.model }}</p>
              <p class="mt-1 text-[10px] uppercase tracking-[0.24em] text-ink-muted">{{ item.provider }} · {{ item.schema }}</p>
            </article>
          </div>
        </TuiCard>
      </div>
    </section>

    <section id="message-review" class="space-y-4">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="text-[10px] font-black uppercase tracking-[0.28em] text-aurora">Message Review</p>
          <h2 class="mt-2 text-2xl font-black text-ink">Recent platform traffic and trace data</h2>
          <p class="mt-2 text-sm text-ink-muted">A trimmed review surface for day-to-day ops, with a deeper history page still available.</p>
        </div>
        <TuiButton variant="outline" @click="fetchMessages" :loading="loadingMessages" size="sm">Refresh History</TuiButton>
      </div>

      <TuiCard title="Filters" subtitle="Narrow the history view">
        <div class="grid gap-3 lg:grid-cols-[160px_160px_160px_auto]">
          <div>
            <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-ink-subtle">Direction</label>
            <select v-model="historyDirection" class="w-full rounded-2xl border border-line-strong bg-surface-elevated/90 px-4 py-3 text-sm text-ink">
              <option value="">All</option>
              <option value="inbound">Inbound</option>
              <option value="outbound">Outbound</option>
            </select>
          </div>
          <div>
            <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-ink-subtle">Limit</label>
            <input v-model.number="historyLimit" type="number" min="1" max="1000" class="w-full rounded-2xl border border-line-strong bg-surface-elevated/90 px-4 py-3 text-sm text-ink" />
          </div>
          <div class="flex items-end">
            <label class="inline-flex items-center gap-2 text-xs font-bold text-ink">
              <input v-model="historyAiOnly" type="checkbox" class="h-4 w-4 rounded border-line text-primary focus:ring-primary" />
              AI only
            </label>
          </div>
          <div class="flex items-end justify-end">
            <TuiButton @click="fetchMessages" :loading="loadingMessages" size="sm">Refresh</TuiButton>
          </div>
        </div>
      </TuiCard>

      <div class="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <TuiCard title="Review Notes" subtitle="Fast read summary">
          <div v-if="loadingMessages" class="py-4 text-sm text-ink-muted">Loading message history...</div>
          <div v-else-if="platformMessages.length === 0" class="py-4 text-sm text-ink-muted">No messages found for the selected filters.</div>
          <div v-else class="space-y-3">
            <article v-for="msg in platformMessages" :key="msg.message_id" class="rounded-2xl border border-line/70 bg-surface px-4 py-4">
              <div class="flex flex-wrap items-center gap-2 text-[10px] font-black uppercase tracking-widest text-ink-subtle">
                <span>#{{ msg.message_id }}</span>
                <span>{{ msg.direction }}</span>
                <span>{{ msg.channel }}</span>
                <span v-if="msg.llm_provider">provider {{ msg.llm_provider }}</span>
                <span v-if="msg.llm_model">model {{ msg.llm_model }}</span>
              </div>
              <p class="mt-3 whitespace-pre-wrap text-sm text-ink">{{ msg.text_content || '(empty)' }}</p>
              <p class="mt-2 text-[11px] text-ink-muted">
                {{ formatInt(getTotalTokens(msg)) }} tokens
                <span v-if="getCostUsd(msg) > 0">· {{ formatUsd(getCostUsd(msg), 6) }}</span>
              </p>
            </article>
          </div>
        </TuiCard>

        <TuiCard title="Trace Preview" subtitle="AI trace metadata">
          <div v-if="loadingMessages" class="py-4 text-sm text-ink-muted">Loading message history...</div>
          <div v-else-if="platformMessages.length === 0" class="py-4 text-sm text-ink-muted">No messages available.</div>
          <div v-else class="max-h-[28rem] space-y-3 overflow-y-auto pr-1">
            <pre
              v-for="msg in platformMessages"
              :key="`trace-${msg.message_id}`"
              class="overflow-x-auto rounded-2xl bg-slate-950 p-4 text-[11px] leading-5 text-slate-100"
            >{{ JSON.stringify(msg.ai_trace || {}, null, 2) }}</pre>
          </div>
        </TuiCard>
      </div>
    </section>

    <section id="benchmark" class="space-y-4">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="text-[10px] font-black uppercase tracking-[0.28em] text-aurora">Benchmark</p>
          <h2 class="mt-2 text-2xl font-black text-ink">Provider comparison and latency tests</h2>
          <p class="mt-2 text-sm text-ink-muted">The detailed benchmark workflow stays on its dedicated page. This console keeps the model catalog close at hand.</p>
        </div>
        <TuiButton variant="outline" @click="fetchModels" :loading="loadingModels" size="sm">Refresh Catalog</TuiButton>
      </div>

      <TuiCard title="Model Catalog" subtitle="UniAPI models available for benchmarking">
        <div v-if="loadingModels" class="py-4 text-sm text-ink-muted">Loading model catalog...</div>
        <div v-else-if="availableModels.length === 0" class="py-4 text-sm text-ink-muted">No models published.</div>
        <div v-else class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <article
            v-for="item in availableModels"
            :key="`catalog-${item.provider}:${item.schema}:${item.model}`"
            class="rounded-2xl border border-line/70 bg-surface px-4 py-3"
          >
            <p class="text-sm font-bold text-ink">{{ item.model }}</p>
            <p class="mt-1 text-[10px] uppercase tracking-[0.24em] text-ink-muted">{{ item.provider }} · {{ item.schema }}</p>
          </article>
        </div>
      </TuiCard>
    </section>

    <section id="health" class="space-y-4">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="text-[10px] font-black uppercase tracking-[0.28em] text-aurora">Health</p>
          <h2 class="mt-2 text-2xl font-black text-ink">Readiness and schema diagnostics</h2>
          <p class="mt-2 text-sm text-ink-muted">Use this as the final check before making platform-wide changes.</p>
        </div>
        <TuiButton variant="outline" @click="fetchHealth" :loading="loadingHealth" size="sm">Refresh Health</TuiButton>
      </div>

      <div class="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <TuiCard title="System Health" subtitle="Permanent readiness diagnostics">
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">State</p>
              <p class="mt-2 text-2xl font-black" :class="platformSystemHealth?.ready ? 'text-emerald-700' : 'text-red-700'">
                {{ healthLabel }}
              </p>
            </div>
            <TuiButton @click="fetchHealth" :loading="loadingHealth" size="sm">Refresh</TuiButton>
          </div>
          <div class="mt-4 rounded-2xl border border-line/70 bg-surface px-4 py-4">
            <p class="text-[11px] font-semibold text-ink-muted">
              The JSON payload below is the fastest way to confirm readiness, migration state, and service coverage.
            </p>
            <pre v-if="platformSystemHealth" class="mt-3 overflow-x-auto rounded-xl bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">{{ JSON.stringify(platformSystemHealth, null, 2) }}</pre>
            <p v-else-if="loadingHealth" class="mt-3 text-sm text-ink-muted">Loading system health...</p>
            <p v-else class="mt-3 text-sm text-ink-muted">No system health payload available.</p>
          </div>
        </TuiCard>

        <TuiCard title="Console Message" subtitle="Feedback from recent actions">
          <div class="rounded-2xl border border-line/70 bg-surface px-4 py-4">
            <p class="text-[11px] font-semibold text-ink-muted">The admin console keeps the existing functionality intact while grouping it into clearer sections.</p>
            <p v-if="message" class="mt-3 rounded-2xl border border-primary/15 bg-primary/5 px-4 py-3 text-sm font-semibold text-primary">
              {{ message }}
            </p>
            <p v-else class="mt-3 text-sm text-ink-muted">
              Save or validate any section above to see a status message here.
            </p>
          </div>
        </TuiCard>
      </div>
    </section>
  </PlatformAdminShell>
</template>
