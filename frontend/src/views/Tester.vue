<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiSelect from '../components/ui/TuiSelect.vue'

import { request } from '../services/api'

const route = useRoute()

const agents = ref([])
const isLoadingAgents = ref(true)
const agentError = ref('')

const includeReasoning = ref(true)
const currentAgentId = ref('')
const composer = ref('')
const isSending = ref(false)

const conversation = ref([]) 
const sessionMeta = reactive({
  startedAt: '',
  label: ''
})

const statusVariant = (state) => {
  const normalized = (state || '').toLowerCase()
  if (['ready', 'live', 'active', 'connected'].includes(normalized)) return 'success'
  if (['tool', 'syncing', 'cooldown', 'warning'].includes(normalized)) return 'warning'
  return 'muted'
}

const agentOptions = computed(() =>
  agents.value.map((agent) => ({
    label: agent.name,
    value: String(agent.id)
  }))
)

const currentAgent = computed(() =>
  agents.value.find((agent) => String(agent.id) === String(currentAgentId.value))
)

const stampSession = () => {
  const now = new Date()
  sessionMeta.startedAt = now.toISOString()
  sessionMeta.label = `Session ${now.toLocaleTimeString()}`
  conversation.value = []
}

const startNewSession = () => {
  if (!currentAgentId.value) return
  stampSession()
}

const loadAgents = async () => {
  isLoadingAgents.value = true
  agentError.value = ''
  try {
    const data = await request('/agents/')
    agents.value = Array.isArray(data)
      ? data.map((agent, index) => ({
          id: agent.id ?? index,
          name: agent.name ?? 'Agent',
          model: agent.model ?? 'n/a',
          status: (agent.status ?? 'ready').toLowerCase(),
          lastActive: agent.lastActive ?? agent.last_active ?? '—',
          tokenCountToday: agent.tokenCountToday ?? agent.token_count_today ?? 0
        }))
      : []
  } catch (error) {
    console.error('Failed to load agents', error)
    agentError.value = 'Failed to load agents from API.'
    agents.value = []
  } finally {
    isLoadingAgents.value = false
    if (!currentAgentId.value && agents.value.length) {
      currentAgentId.value = String(agents.value[0].id)
    }
  }
}

const setAgentFromRoute = () => {
  const paramId = route.params.agentId || route.query.agentId
  if (paramId) currentAgentId.value = String(paramId)
}

const sendMessage = async () => {
  if (!currentAgentId.value || !composer.value.trim()) return
  
  const messageText = composer.value.trim()
  composer.value = ''
  
  // Add user message to conversation immediately
  conversation.value.push({ role: 'user', text: messageText, ts: new Date().toISOString() })
  isSending.value = true
  
  try {
    const data = await request('/chat/', {
      method: 'POST',
      body: JSON.stringify({
        agent_id: parseInt(currentAgentId.value),
        message: messageText,
        include_reasoning: includeReasoning.value
      })
    })

    // Add assistant response
    conversation.value.push({
      role: 'assistant',
      text: data.response || '(No response text)',
      ts: new Date().toISOString()
    })

  } catch (error) {
    console.error('Chat request failed', error)
    conversation.value.push({
      role: 'assistant',
      text: `Error: ${error.message}. Check backend logs.`,
      ts: new Date().toISOString()
    })
  } finally {
    isSending.value = false
  }
}

const toggleReasoning = () => {
  includeReasoning.value = !includeReasoning.value
}

onMounted(() => {
  setAgentFromRoute()
  loadAgents().then(() => {
    if (currentAgentId.value) stampSession()
  })
})
</script>

<template>
  <div class="relative min-h-screen bg-white">
    <div class="pointer-events-none absolute inset-0 tui-grid opacity-10" aria-hidden="true"></div>
    <main class="relative z-10 mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:px-10 space-y-8">
      <header class="flex flex-col gap-3">
        <div class="space-y-2">
          <p class="text-xs uppercase tracking-[0.32em] text-slate-600">tester</p>
          <h1 class="text-3xl font-bold text-slate-900">Agent Chat Tester</h1>
          <p class="text-sm text-slate-600">
            Lightweight surface for external testers. No admin navigation.
          </p>
          <div class="flex flex-wrap items-center gap-2">
            <TuiBadge variant="info">POST /api/v1/chat</TuiBadge>
            <TuiBadge variant="muted">base: dynamic (current host)</TuiBadge>
            <TuiBadge :variant="includeReasoning ? 'success' : 'muted'">
              reasoning: {{ includeReasoning ? 'on' : 'off' }}
            </TuiBadge>
          </div>
        </div>
      </header>

      <section class="grid gap-4 md:grid-cols-[1.1fr_1fr]">
        <div class="space-y-4">
          <TuiSelect
            label="Agent"
            hint="required"
            :options="agentOptions"
            v-model="currentAgentId"
            placeholder="Select agent"
          />
          <div class="flex flex-wrap items-center gap-2">
            <TuiButton size="sm" variant="outline" @click="startNewSession" :disabled="!currentAgentId">
              New chat
            </TuiButton>
            <TuiButton size="sm" variant="ghost" @click="toggleReasoning">
              Reasoning: {{ includeReasoning ? 'On' : 'Off' }}
            </TuiButton>
            <TuiBadge v-if="currentAgent" :variant="statusVariant(currentAgent.status)" class="w-24 justify-center">
              {{ currentAgent.status || 'ready' }}
            </TuiBadge>
          </div>
          <p v-if="agentError" class="text-xs text-slate-600">{{ agentError }}</p>

          <div class="rounded-xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-[11px] uppercase tracking-[0.2em] text-slate-600">session</p>
                <h2 class="text-lg font-semibold text-slate-900">HTTP Chat</h2>
              </div>
              <TuiBadge variant="muted">
                started: {{ sessionMeta.startedAt ? new Date(sessionMeta.startedAt).toLocaleTimeString() : 'pending' }}
              </TuiBadge>
            </div>
            <div class="mt-3 space-y-2 text-sm text-slate-700">
              <p>Chat requests are sent via standard HTTP POST.</p>
              <p>History is maintained on the backend per session.</p>
            </div>
          </div>
        </div>

        <div class="rounded-xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm">
          <header class="mb-3 flex items-center justify-between">
            <div>
              <p class="text-[11px] uppercase tracking-[0.2em] text-slate-600">conversation</p>
              <h2 class="text-xl font-semibold text-slate-900">{{ currentAgent?.name || 'Select an agent' }}</h2>
            </div>
            <TuiBadge v-if="currentAgent" variant="muted">{{ currentAgent.model }}</TuiBadge>
          </header>

          <div class="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-3 sm:p-4 max-h-[55vh] overflow-y-auto">
            <p v-if="!conversation.length" class="text-sm text-slate-600">Start chatting to see messages.</p>
            <div v-else>
              <div
                v-for="(message, idx) in conversation"
                :key="idx"
                :class="[
                  'mb-3 flex',
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                ]"
              >
                <div
                  :class="[
                    'max-w-full rounded-lg border px-3 py-2 text-sm sm:max-w-[75%]',
                    message.role === 'user'
                      ? 'border-slate-900 bg-slate-50 text-slate-900'
                      : 'border-slate-200 bg-white text-slate-900'
                  ]"
                >
                  <p class="text-[11px] uppercase tracking-[0.16em] text-slate-600" v-if="message.role === 'assistant'">
                    {{ currentAgent?.name || 'agent' }}
                  </p>
                  <p class="text-[11px] uppercase tracking-[0.16em] text-slate-900/80" v-else>
                    you
                  </p>
                  <p class="whitespace-pre-wrap leading-relaxed">
                    {{ message.text }}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-4 space-y-3">
            <label class="flex flex-col gap-2 text-sm text-slate-800">
              <div class="flex items-center justify-between">
                <span class="text-[11px] uppercase tracking-[0.2em] text-slate-600">message</span>
                <span class="text-[11px] text-slate-600">agent: {{ currentAgent?.name || 'none' }}</span>
              </div>
              <div class="relative breathing-ring">
                <textarea
                  v-model="composer"
                  rows="3"
                  :disabled="!currentAgentId || isSending"
                  placeholder="Type a message to the agent. Press Send to dispatch."
                  class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-[inset_0_1px_1px_rgba(15,23,42,0.06)] focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-200 disabled:cursor-not-allowed disabled:bg-slate-100"
                  @keydown.ctrl.enter="sendMessage"
                ></textarea>
              </div>
            </label>
            <div class="flex flex-wrap items-center gap-3">
              <TuiButton :loading="isSending" @click="sendMessage" :disabled="!currentAgentId">
                Send
              </TuiButton>
              <TuiButton variant="outline" @click="startNewSession" :disabled="!currentAgentId">New chat</TuiButton>
              <p class="text-xs text-slate-600">Standard HTTP Mode.</p>
            </div>
          </div>
        </div>
      </section>

      <section class="rounded-xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p class="text-[11px] uppercase tracking-[0.2em] text-slate-600">agent config</p>
            <h3 class="text-lg font-semibold text-slate-900">Details</h3>
          </div>
          <TuiBadge v-if="currentAgent" variant="muted">{{ currentAgent.model }}</TuiBadge>
        </div>
        <div class="mt-3 grid gap-3 sm:grid-cols-3 text-sm text-slate-800">
          <div>
            <p class="text-[11px] uppercase tracking-[0.18em] text-slate-600">name</p>
            <p class="font-semibold">{{ currentAgent?.name || 'Select agent' }}</p>
          </div>
          <div>
            <p class="text-[11px] uppercase tracking-[0.18em] text-slate-600">status</p>
            <p class="font-semibold capitalize">{{ currentAgent?.status || 'unknown' }}</p>
          </div>
          <div>
            <p class="text-[11px] uppercase tracking-[0.18em] text-slate-600">last active</p>
            <p class="font-semibold">{{ currentAgent?.lastActive || '—' }}</p>
          </div>
        </div>
        <p class="mt-2 text-xs text-slate-600">
          Read-only for testers; configuration is shown for context.
        </p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.breathing-ring {
  position: relative;
  border-radius: 0.5rem;
}

.breathing-ring::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: inherit;
  background: linear-gradient(120deg, #16f2b3, #7c3aed, #06b6d4, #16f2b3);
  background-size: 220% 220%;
  opacity: 0;
  z-index: 0;
  filter: blur(0.5px);
  transition: opacity 0.3s ease;
  animation: breatheGradient 3s ease-in-out infinite;
  pointer-events: none;
}

.breathing-ring:focus-within::after {
  opacity: 0.65;
}

.breathing-ring > textarea {
  position: relative;
  z-index: 1;
}

@keyframes breatheGradient {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}
</style>
