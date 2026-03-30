<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { request } from '../services/api'
import { store } from '../store'
import {
  getChannelBadgeLabel,
  getChannelIdentity,
  isConnectedChannelStatus,
} from '../utils/agentChannels'

const router = useRouter()

const isLoading = ref(false)
const isCreating = ref(false)
const channels = ref([])
const message = ref('')

const form = reactive({
  name: '',
  system_prompt: '',
})

const creationSteps = [
  'Agent Name',
  'Setup WhatsApp Channel',
  'Instruction Setting',
  'Sales Material Upload',
  'Playground',
]

const loadHome = async () => {
  isLoading.value = true
  try {
    const [_, channelSessions] = await Promise.all([
      store.fetchAgents(),
      request('/messaging/channels/whatsapp/sessions').catch(() => []),
    ])
    channels.value = Array.isArray(channelSessions) ? channelSessions : []
  } finally {
    isLoading.value = false
  }
}

const setMessage = (text) => {
  message.value = text
  if (!text) return
  window.clearTimeout(setMessage.timeoutId)
  setMessage.timeoutId = window.setTimeout(() => {
    message.value = ''
  }, 3200)
}
setMessage.timeoutId = null

const channelById = computed(() =>
  new Map(channels.value.map((session) => [Number(session.id), session]))
)

const assignedChannel = (agent) =>
  channelById.value.get(Number(agent?.preferred_channel_session_id || 0)) || null

const formatLastActive = (value) => {
  if (!value || value === '—') return 'No activity yet'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

const agentStatus = (agent) => {
  const channel = assignedChannel(agent)
  if (channel && isConnectedChannelStatus(channel.status)) {
    return {
      label: 'Active',
      badge: 'bg-emerald-500/12 text-emerald-700',
      note: 'Connected and ready to handle WhatsApp conversations',
    }
  }
  if (channel) {
    return {
      label: 'Needs Attention',
      badge: 'bg-amber-500/12 text-amber-700',
      note: 'Assigned channel still needs connection or recovery',
    }
  }
  if (agent?.system_prompt) {
    return {
      label: 'Idle',
      badge: 'bg-sky-500/12 text-sky-700',
      note: 'Instructions exist, but WhatsApp is not assigned yet',
    }
  }
  return {
    label: 'Draft',
    badge: 'bg-slate-500/12 text-slate-600',
    note: 'Basic agent record exists without its full workspace setup',
  }
}

const overviewCards = computed(() => {
  const total = store.agents.length
  const active = store.agents.filter((agent) => agentStatus(agent).label === 'Active').length
  const needsAttention = store.agents.filter((agent) => agentStatus(agent).label === 'Needs Attention').length
  return [
    { label: 'Total Agents', value: total, hint: 'Tenant-level roster' },
    { label: 'Active Now', value: active, hint: 'Connected and ready on WhatsApp' },
    { label: 'Channels', value: channels.value.length, hint: 'WhatsApp numbers available' },
    { label: 'Alerts', value: needsAttention, hint: 'Agents that still need setup' },
  ]
})

const openAgentDashboard = (agentId) => {
  if (store.setActiveAgent(agentId)) {
    router.push(`/agents/${agentId}`)
    return
  }
  router.push(`/agents/${agentId}`)
}

const createAgent = async () => {
  isCreating.value = true
  try {
    const created = await request('/agents/', {
      method: 'POST',
      body: JSON.stringify({
        name: form.name.trim() || 'New Agent',
        system_prompt: form.system_prompt.trim(),
      }),
    })
    form.name = ''
    form.system_prompt = ''
    await loadHome()
    setMessage('Agent created. Opening inbox workspace.')
    if (created?.id) {
      openAgentDashboard(created.id)
    }
  } catch (error) {
    setMessage(`Create failed: ${error.message}`)
  } finally {
    isCreating.value = false
  }
}

onMounted(loadHome)
</script>

<template>
  <div class="space-y-6 pb-12">
    <div
      v-if="message"
      class="fixed left-1/2 top-20 z-50 flex -translate-x-1/2 items-center gap-2 rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-lg"
    >
      <span class="material-symbols-outlined text-sm">check_circle</span>
      {{ message }}
    </div>

    <section class="overflow-hidden rounded-[2rem] border border-line/70 bg-[linear-gradient(135deg,_rgb(var(--panel-elevated-rgb)_/_0.97),_rgb(var(--accent-soft-rgb)_/_0.48),_rgb(var(--panel-rgb)_/_0.98))] p-6 shadow-[0_32px_70px_-40px_rgb(var(--accent-rgb)_/_0.35)] backdrop-blur-xl lg:p-8">
      <div class="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
        <div class="max-w-3xl">
          <p class="text-[11px] font-extrabold uppercase tracking-[0.32em] text-ink-subtle">Tenant Workspace</p>
          <h1 class="mt-3 text-3xl font-extrabold tracking-[-0.04em] text-ink md:text-4xl">All agent status in one desktop dashboard</h1>
          <p class="mt-3 max-w-2xl text-sm leading-6 text-ink-muted">
            This is the tenant entry point. Each card is an agent workspace with its own inbox, instruction setting,
            WhatsApp channel, CRM actions, and sales materials.
          </p>
        </div>

        <div class="flex flex-wrap gap-3">
          <button
            type="button"
            @click="loadHome"
            :disabled="isLoading"
            class="inline-flex items-center gap-2 rounded-full border border-line/70 bg-surface-elevated/90 px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-surface disabled:opacity-60"
          >
            <span class="material-symbols-outlined text-[18px]" :class="{ 'animate-spin': isLoading }">refresh</span>
            Refresh
          </button>
          <button
            type="button"
            @click="router.push('/playground')"
            class="inline-flex items-center gap-2 rounded-full border border-primary/10 bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-[0_18px_32px_-20px_rgb(var(--accent-rgb)_/_0.85)] transition-transform hover:-translate-y-0.5"
          >
            <span class="material-symbols-outlined text-[18px]">add_circle</span>
            Open Playground
          </button>
        </div>
      </div>
    </section>

    <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <article
        v-for="card in overviewCards"
        :key="card.label"
        class="rounded-[1.7rem] border border-line/70 bg-surface-elevated/92 p-5 shadow-[0_22px_48px_-34px_rgb(var(--accent-rgb)_/_0.22)]"
      >
        <p class="text-[11px] font-extrabold uppercase tracking-[0.24em] text-ink-subtle">{{ card.label }}</p>
        <p class="mt-4 text-3xl font-extrabold tracking-[-0.04em] text-ink">{{ card.value }}</p>
        <p class="mt-2 text-sm text-ink-muted">{{ card.hint }}</p>
      </article>
    </section>

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_400px]">
      <section class="rounded-[1.85rem] border border-line/70 bg-surface-elevated/94 p-5 shadow-[0_28px_56px_-36px_rgb(var(--accent-rgb)_/_0.18)] sm:p-6">
        <div class="flex flex-col gap-4 border-b border-line/70 pb-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p class="text-[11px] font-extrabold uppercase tracking-[0.24em] text-ink-subtle">Agents</p>
            <h2 class="mt-2 text-2xl font-extrabold tracking-[-0.03em] text-ink">Tenant dashboard</h2>
            <p class="mt-2 text-sm text-ink-muted">Click any status card to enter that agent’s inbox-first workspace.</p>
          </div>
          <p class="text-sm font-semibold text-ink-muted">{{ store.agents.length }} agents loaded</p>
        </div>

        <div v-if="store.isLoading || isLoading" class="py-14 text-center text-sm text-ink-muted">
          Loading agents...
        </div>

        <div v-else-if="store.agents.length === 0" class="rounded-[1.6rem] border border-dashed border-line/70 bg-surface px-5 py-12 text-center">
          <span class="material-symbols-outlined text-5xl text-ink-subtle">smart_toy</span>
          <h3 class="mt-4 text-lg font-bold text-ink">No agents yet</h3>
          <p class="mt-2 text-sm text-ink-muted">Create your first agent on the right to start the new tenant workflow.</p>
        </div>

        <div v-else class="mt-6 grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          <button
            v-for="agent in store.agents"
            :key="agent.id"
            type="button"
            @click="openAgentDashboard(agent.id)"
            class="group rounded-[1.7rem] border border-line/70 bg-[linear-gradient(180deg,_rgb(var(--panel-elevated-rgb)_/_0.98),_rgb(var(--panel-rgb)_/_0.94))] p-5 text-left shadow-[0_24px_48px_-36px_rgb(var(--accent-rgb)_/_0.25)] transition-all hover:-translate-y-1 hover:border-primary/35 hover:shadow-[0_28px_60px_-34px_rgb(var(--accent-rgb)_/_0.32)]"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="flex items-center gap-3">
                  <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-base font-extrabold text-primary">
                    {{ (agent.name || 'A').charAt(0).toUpperCase() }}
                  </div>
                  <div class="min-w-0">
                    <p class="truncate text-lg font-extrabold text-ink">{{ agent.name || 'Untitled agent' }}</p>
                    <p class="mt-1 text-xs font-semibold uppercase tracking-[0.18em] text-ink-subtle">
                      {{ formatLastActive(agent.lastActive || agent.last_active) }}
                    </p>
                  </div>
                </div>
              </div>
              <span class="rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em]" :class="agentStatus(agent).badge">
                {{ agentStatus(agent).label }}
              </span>
            </div>

            <p class="mt-4 min-h-[72px] text-sm leading-6 text-ink-muted">
              {{ agent.system_prompt || 'Add brand instructions, sales materials, and WhatsApp routing to complete this workspace.' }}
            </p>

            <div class="mt-5 grid gap-3 sm:grid-cols-2">
              <div class="rounded-2xl bg-[rgb(var(--accent-soft-rgb)_/_0.42)] px-4 py-3">
                <p class="text-[11px] font-extrabold uppercase tracking-[0.18em] text-ink-subtle">WhatsApp</p>
                <p class="mt-2 text-sm font-bold text-ink">
                  {{ assignedChannel(agent) ? getChannelIdentity(assignedChannel(agent)) : 'Not assigned' }}
                </p>
                <p class="mt-1 text-xs text-ink-muted">{{ getChannelBadgeLabel(assignedChannel(agent)) }}</p>
              </div>
              <div class="rounded-2xl bg-surface px-4 py-3 ring-1 ring-line/60">
                <p class="text-[11px] font-extrabold uppercase tracking-[0.18em] text-ink-subtle">Workspace</p>
                <p class="mt-2 text-sm font-bold text-ink">{{ agent.linked_mcp_count || 0 }} linked skills</p>
                <p class="mt-1 text-xs text-ink-muted">{{ agentStatus(agent).note }}</p>
              </div>
            </div>

            <div class="mt-5 inline-flex items-center gap-2 text-sm font-extrabold text-primary">
              Enter agent dashboard
              <span class="material-symbols-outlined text-[18px] transition-transform group-hover:translate-x-1">arrow_forward</span>
            </div>
          </button>
        </div>
      </section>

      <aside class="space-y-4">
        <section class="rounded-[1.85rem] border border-line/70 bg-surface-elevated/94 p-5 shadow-[0_28px_56px_-36px_rgb(var(--accent-rgb)_/_0.18)] sm:p-6">
          <p class="text-[11px] font-extrabold uppercase tracking-[0.24em] text-ink-subtle">New Agent Flow</p>
          <h2 class="mt-2 text-2xl font-extrabold tracking-[-0.03em] text-ink">Start with the new workflow</h2>
          <p class="mt-2 text-sm leading-6 text-ink-muted">
            The onboarding now follows the same desktop structure you requested, with WhatsApp and instruction setup before conversation testing.
          </p>

          <div class="mt-5 space-y-3">
            <div
              v-for="(step, index) in creationSteps"
              :key="step"
              class="flex items-center gap-3 rounded-2xl bg-[rgb(var(--accent-soft-rgb)_/_0.32)] px-4 py-3"
            >
              <div class="flex h-9 w-9 items-center justify-center rounded-full bg-white text-sm font-extrabold text-primary ring-1 ring-primary/10">
                {{ index + 1 }}
              </div>
              <p class="text-sm font-semibold text-ink">{{ step }}</p>
            </div>
          </div>
        </section>

        <section class="rounded-[1.85rem] border border-line/70 bg-surface-elevated/94 p-5 shadow-[0_28px_56px_-36px_rgb(var(--accent-rgb)_/_0.18)] sm:p-6">
          <p class="text-[11px] font-extrabold uppercase tracking-[0.24em] text-ink-subtle">Create Agent</p>
          <h3 class="mt-2 text-xl font-extrabold tracking-[-0.02em] text-ink">Create the workspace shell</h3>
          <p class="mt-2 text-sm leading-6 text-ink-muted">
            Give the agent a name and starting instructions now. You’ll continue with WhatsApp, contacts, sales materials, and playground inside the dashboard.
          </p>

          <div class="mt-6 space-y-4">
            <div class="space-y-2">
              <label class="px-1 text-sm font-semibold text-ink">Agent Name</label>
              <input
                v-model="form.name"
                type="text"
                class="h-14 w-full rounded-2xl border border-line/70 bg-surface px-4 text-ink placeholder:text-ink-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="e.g. Sales Closer, VIP Support, Booking Desk"
              />
            </div>

            <div class="space-y-2">
              <label class="px-1 text-sm font-semibold text-ink">Instruction Setting</label>
              <textarea
                v-model="form.system_prompt"
                class="min-h-[220px] w-full rounded-2xl border border-line/70 bg-surface p-4 text-ink placeholder:text-ink-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="Describe the tone, goals, offer positioning, and escalation rules for this agent."
              ></textarea>
            </div>

            <button
              type="button"
              @click="createAgent"
              :disabled="isCreating"
              class="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-bold text-white shadow-[0_18px_35px_-20px_rgb(var(--accent-rgb)_/_0.8)] transition-transform hover:-translate-y-0.5 disabled:opacity-60"
            >
              <span v-if="isCreating" class="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
              <span v-else class="material-symbols-outlined text-[20px]">add_circle</span>
              {{ isCreating ? 'Creating...' : 'Create Agent and Open Inbox' }}
            </button>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>
