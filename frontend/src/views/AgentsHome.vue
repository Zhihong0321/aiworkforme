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
    setMessage('Agent created. Opening dashboard.')
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

    <section class="rounded-[2rem] border border-line/80 bg-surface-elevated/90 p-6 shadow-shell backdrop-blur-xl">
      <div class="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div class="max-w-2xl">
          <p class="text-[11px] font-bold uppercase tracking-[0.28em] text-ink-subtle">Agents</p>
          <h1 class="mt-2 text-3xl font-bold tracking-[-0.03em] text-ink">Every agent gets its own workspace now</h1>
          <p class="mt-3 text-sm leading-6 text-ink-muted">
            Open an agent to manage its WhatsApp channel, knowledge, inbox, and contacts in one place instead of jumping across global pages.
          </p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <div class="rounded-2xl border border-line/80 bg-surface px-4 py-3 text-sm">
            <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Agents</p>
            <p class="mt-1 text-2xl font-bold text-ink">{{ store.agents.length }}</p>
          </div>
          <div class="rounded-2xl border border-line/80 bg-surface px-4 py-3 text-sm">
            <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">WhatsApp Channels</p>
            <p class="mt-1 text-2xl font-bold text-ink">{{ channels.length }}</p>
          </div>
        </div>
      </div>
    </section>

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_360px]">
      <section class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell sm:p-6">
        <div class="flex items-center justify-between gap-4 border-b border-line/70 pb-4">
          <div>
            <h2 class="text-xl font-bold text-ink">Agent Directory</h2>
            <p class="mt-1 text-sm text-ink-muted">Click any agent card to enter its dashboard.</p>
          </div>
          <button
            type="button"
            @click="loadHome"
            :disabled="isLoading"
            class="inline-flex items-center gap-2 rounded-2xl border border-line/80 bg-surface px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-surface-muted disabled:opacity-60"
          >
            <span class="material-symbols-outlined text-[18px]" :class="{ 'animate-spin': isLoading }">refresh</span>
            Refresh
          </button>
        </div>

        <div v-if="store.isLoading || isLoading" class="py-12 text-center text-sm text-ink-muted">
          Loading agents...
        </div>

        <div v-else-if="store.agents.length === 0" class="rounded-[1.5rem] border border-dashed border-line bg-surface px-5 py-10 text-center">
          <span class="material-symbols-outlined text-5xl text-ink-subtle">smart_toy</span>
          <h3 class="mt-4 text-lg font-bold text-ink">No agents yet</h3>
          <p class="mt-2 text-sm text-ink-muted">Create your first agent on the right, then open its dashboard to assign channels and add contacts.</p>
        </div>

        <div v-else class="mt-5 grid gap-4 md:grid-cols-2">
          <button
            v-for="agent in store.agents"
            :key="agent.id"
            type="button"
            @click="openAgentDashboard(agent.id)"
            class="group rounded-[1.6rem] border border-line/80 bg-surface p-5 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-primary/5"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="truncate text-lg font-bold text-ink">{{ agent.name || 'Untitled agent' }}</p>
                <p class="mt-2 line-clamp-3 text-sm leading-6 text-ink-muted">
                  {{ agent.system_prompt || 'No system instructions yet. Open the dashboard to define how this agent should behave.' }}
                </p>
              </div>
              <div class="flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-lg font-bold text-primary">
                {{ (agent.name || 'A').charAt(0).toUpperCase() }}
              </div>
            </div>

            <div class="mt-5 flex flex-wrap gap-2 text-xs font-semibold">
              <span class="rounded-full bg-surface-muted px-3 py-1 text-ink-subtle">
                {{ agent.linked_mcp_count || 0 }} skills
              </span>
              <span
                class="rounded-full px-3 py-1"
                :class="assignedChannel(agent) && isConnectedChannelStatus(assignedChannel(agent).status)
                  ? 'bg-emerald-500/10 text-emerald-700'
                  : 'bg-amber-500/10 text-amber-700'"
              >
                {{ getChannelBadgeLabel(assignedChannel(agent)) }}
              </span>
            </div>

            <div class="mt-4 rounded-2xl border border-line/70 bg-surface-muted/70 px-4 py-3">
              <p class="text-[11px] font-bold uppercase tracking-[0.2em] text-ink-subtle">Assigned WhatsApp</p>
              <p class="mt-2 text-sm font-semibold text-ink">
                {{ assignedChannel(agent) ? getChannelIdentity(assignedChannel(agent)) : 'No WhatsApp assigned yet' }}
              </p>
            </div>

            <div class="mt-4 inline-flex items-center gap-2 text-sm font-bold text-primary">
              Open dashboard
              <span class="material-symbols-outlined text-[18px] transition-transform group-hover:translate-x-1">arrow_forward</span>
            </div>
          </button>
        </div>
      </section>

      <aside class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/90 p-5 shadow-shell sm:p-6">
        <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Create Agent</p>
        <h2 class="mt-2 text-2xl font-bold tracking-[-0.02em] text-ink">Start with the basics</h2>
        <p class="mt-2 text-sm leading-6 text-ink-muted">
          Create the agent here, then use the dashboard to wire its WhatsApp, knowledge base, inbox, and contacts.
        </p>

        <div class="mt-6 space-y-4">
          <div class="space-y-2">
            <label class="px-1 text-sm font-semibold text-ink">Agent Name</label>
            <input
              v-model="form.name"
              type="text"
              class="h-14 w-full rounded-2xl border border-line/80 bg-surface px-4 text-ink placeholder:text-ink-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              placeholder="e.g. Sales Closer, VIP Support, Booking Desk"
            />
          </div>

          <div class="space-y-2">
            <label class="px-1 text-sm font-semibold text-ink">System Instructions</label>
            <textarea
              v-model="form.system_prompt"
              class="min-h-[220px] w-full rounded-2xl border border-line/80 bg-surface p-4 text-ink placeholder:text-ink-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              placeholder="Describe the tone, goals, guardrails, and escalation rules for this agent."
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
            {{ isCreating ? 'Creating...' : 'Create Agent' }}
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>
