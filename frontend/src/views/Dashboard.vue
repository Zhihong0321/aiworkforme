<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiSelect from '../components/ui/TuiSelect.vue'

const API_BASE = `${window.location.origin}/api/v1`

const router = useRouter()
const origin = window.location.origin

const agents = ref([])
const mcps = ref([])
const health = ref(null)

const isLoadingAgents = ref(true)
const isLoadingMcps = ref(true)
const isLoadingHealth = ref(false)
const agentError = ref('')
const mcpError = ref('')
const message = ref('')
const togglingMcpId = ref(null)

const quickAgentId = ref('')
const quickComposer = ref('')
const quickSending = ref(false)
const quickLog = ref([])
const quickStatus = ref('idle')

const formatTokens = (value) => {
  const num = Number(value)
  if (Number.isNaN(num)) return value || '—'
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`
  return `${num}`
}

const statusVariant = (status) => {
  const normalized = (status || '').toLowerCase()
  if (['live', 'active', 'ready', 'online', 'running', 'connected'].includes(normalized)) return 'success'
  if (['watch', 'syncing', 'cooldown', 'tool', 'warning'].includes(normalized)) return 'warning'
  return 'muted'
}

const agentOptions = computed(() =>
  agents.value.map((agent) => ({
    label: agent.name,
    value: String(agent.id)
  }))
)

const metrics = computed(() => {
  const readyAgents = agents.value.filter((a) => ['ready', 'live', 'active'].includes((a.status || '').toLowerCase()))
  const runningMcps = mcps.value.filter((m) =>
    ['ready', 'online', 'running', 'connected'].includes((m.status || '').toLowerCase())
  )
  const tokensToday = agents.value.reduce((acc, agent) => acc + (Number(agent.tokenCountToday) || 0), 0)

  return {
    totalAgents: agents.value.length,
    readyAgents: readyAgents.length,
    tokensToday,
    mcps: mcps.value.length,
    runningMcps: runningMcps.length
  }
})

const topAgents = computed(() => agents.value.slice(0, 4))

const loadAgents = async () => {
  isLoadingAgents.value = true
  agentError.value = ''
  try {
    const res = await fetch(`${API_BASE}/agents/`)
    if (!res.ok) throw new Error('Failed to fetch agents')
    const data = await res.json()
    agents.value = Array.isArray(data)
        ? data.map((agent, index) => ({
            id: agent.id ?? index,
            name: agent.name ?? 'Unknown Agent',
            status: (agent.status ?? 'ready').toLowerCase(),
            lastActive: agent.lastActive ?? agent.last_active ?? '—',
            tokenCountToday: agent.tokenCountToday ?? agent.token_count_today ?? 0
        }))
      : []
    if (!quickAgentId.value && agents.value.length) {
      quickAgentId.value = String(agents.value[0].id)
    }
  } catch (error) {
    console.error('Failed to load agents', error)
    agentError.value = 'Failed to load agents from API.'
    agents.value = []
  } finally {
    isLoadingAgents.value = false
  }
}

const loadMcps = async () => {
  isLoadingMcps.value = true
  mcpError.value = ''
  try {
    const res = await fetch(`${API_BASE}/mcp/servers`)
    if (!res.ok) throw new Error('Failed to fetch servers')
    const data = await res.json()
    mcps.value = Array.isArray(data)
      ? data.map((server, index) => ({
          id: server.id ?? index,
          name: server.name ?? 'server',
          status: (server.status ?? 'stopped').toLowerCase(),
          endpoint: server.endpoint ?? server.script ?? '',
          last_error: server.last_error,
          last_heartbeat: server.last_heartbeat
        }))
      : []
  } catch (error) {
    console.error('Failed to load mcp servers', error)
    mcpError.value = 'Failed to load MCP servers.'
    mcps.value = []
  } finally {
    isLoadingMcps.value = false
  }
}

const loadHealth = async () => {
  isLoadingHealth.value = true
  try {
    const res = await fetch(`${API_BASE}/health`)
    if (!res.ok) throw new Error('Failed to fetch health')
    health.value = await res.json()
  } catch (error) {
    console.error('Failed to load health', error)
    health.value = { api_status: 'error', database_status: { ok: false, message: 'Health check failed' } }
  } finally {
    isLoadingHealth.value = false
  }
}

const refreshAll = () => {
  loadAgents()
  loadMcps()
  loadHealth()
}

const sendQuickMessage = async () => {
  if (!quickAgentId.value || !quickComposer.value.trim()) {
    message.value = 'Select an agent and enter a message.'
    return
  }

  const agentId = parseInt(quickAgentId.value, 10)
  const text = quickComposer.value.trim()
  quickComposer.value = ''
  quickSending.value = true
  quickStatus.value = 'sending'
  message.value = ''

  const entryTs = new Date().toISOString()
  quickLog.value.push({ role: 'user', text, ts: entryTs })

  try {
    const res = await fetch(`${API_BASE}/chat/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: agentId, message: text })
    })
    if (!res.ok) throw new Error('Chat request failed')
    const data = await res.json()
    quickLog.value.push({
      role: 'assistant',
      text: data.response || 'No response text.',
      ts: new Date().toISOString()
    })
    quickStatus.value = 'idle'
  } catch (error) {
    console.error('Quick chat failed', error)
    quickStatus.value = 'error'
    quickLog.value.push({
      role: 'assistant',
      text: 'Send failed. Check backend connectivity.',
      ts: new Date().toISOString()
    })
  } finally {
    quickSending.value = false
  }
}

const resetQuickChat = () => {
  quickLog.value = []
  quickComposer.value = ''
  quickStatus.value = 'idle'
}

const toggleMcp = async (server, action) => {
  if (!server?.id) return
  togglingMcpId.value = server.id
  message.value = ''
  try {
    const endpoint = action === 'start' ? 'start' : 'stop'
    const res = await fetch(`${API_BASE}/mcp/servers/${server.id}/${endpoint}`, { method: 'POST' })
    if (!res.ok) throw new Error(`Failed to ${endpoint} MCP`)
    message.value = `MCP ${action}ed.`
    await loadMcps()
  } catch (error) {
    console.error('Toggle MCP failed', error)
    message.value = `MCP ${action} failed.`
  } finally {
    togglingMcpId.value = null
  }
}

const goTo = (path) => {
  router.push(path)
}

onMounted(() => {
  refreshAll()
})
</script>

<template>
  <div class="relative min-h-screen bg-white text-slate-900">
    <main class="mx-auto w-full max-w-6xl px-4 py-8">
      <header class="mb-8">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div class="space-y-1">
            <p class="text-xs uppercase tracking-wider text-slate-600">z.ai control</p>
            <h1 class="text-3xl font-bold">Operations Dashboard</h1>
            <p class="text-sm text-slate-600">
              Live agent, MCP, and chat controls. Use this page to glance and act without leaving the shell vibe.
            </p>
            <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
              <span class="uppercase tracking-wider">/api/v1</span>
              <span class="uppercase tracking-wider text-slate-600">base: {{ origin }}</span>
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <TuiButton size="sm" variant="outline" @click="refreshAll">refresh</TuiButton>
          </div>
        </div>
      </header>

      <section class="grid grid-cols-1 rounded-lg border border-slate-200 text-xs uppercase tracking-wider text-slate-600 md:grid-cols-4 mb-8">
        <div class="border-b border-slate-200 px-5 py-4 md:border-b-0 md:border-r">
          Agents: {{ metrics.totalAgents }} ({{ metrics.readyAgents }} ready)
        </div>
        <div class="border-b border-slate-200 px-5 py-4 md:border-b-0 md:border-r">
          Tokens today: {{ formatTokens(metrics.tokensToday) }}
        </div>
        <div class="border-b border-slate-200 px-5 py-4 md:border-b-0 md:border-r">
          MCPs: {{ metrics.mcps }} running: {{ metrics.runningMcps }}
        </div>
        <div class="px-5 py-4">
          Health: API {{ health?.api_status || '—' }} / DB {{ health?.database_status?.ok ? 'ok' : 'check' }}
        </div>
      </section>

      <div class="grid grid-cols-1 lg:grid-cols-2">
        <TuiCard title="Status & Usage" subtitle="Agent">
          <template #actions>
            <span v-if="agentError" class="text-xs text-red-500">{{ agentError }}</span>
            <TuiButton size="sm" variant="outline" @click="loadAgents" :loading="isLoadingAgents">refresh</TuiButton>
          </template>
          <div v-if="isLoadingAgents" class="text-sm text-slate-600 py-4">Loading agents...</div>
          <div v-else class="divide-y divide-slate-200">
            <div
              v-for="agent in topAgents"
              :key="agent.id"
              class="flex flex-wrap items-center justify-between gap-4 px-5 py-4"
            >
              <div class="flex min-w-0 flex-1 items-center gap-4">
                <div class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-sm font-semibold uppercase text-slate-800">
                  {{ agent.name.slice(0, 2) }}
                </div>
                <div class="min-w-0 flex-1">
                  <p class="truncate text-base font-semibold leading-tight">{{ agent.name }}</p>
                </div>
              </div>

              <div class="hidden items-center gap-3 text-sm text-slate-700 sm:flex">
                <div class="text-center">
                  <p class="text-xs uppercase tracking-wider text-slate-600">tokens</p>
                  <p class="font-semibold tabular-nums">{{ formatTokens(agent.tokenCountToday) }}</p>
                </div>
                <div class="text-center">
                  <p class="text-xs uppercase tracking-wider text-slate-600">active</p>
                  <p class="font-semibold tabular-nums">{{ agent.lastActive || '—' }}</p>
                </div>
                <TuiBadge :variant="statusVariant(agent.status)" class="w-24 justify-center">
                  {{ agent.status || 'ready' }}
                </TuiBadge>
              </div>

              <div class="flex flex-wrap justify-start gap-2">
                <TuiButton size="sm" variant="ghost" @click="goTo(`/chat/${agent.id}`)">chat</TuiButton>
                <TuiButton size="sm" variant="outline" @click="goTo('/agents')">manage</TuiButton>
              </div>
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Smoke Test" subtitle="Quick Chat">
          <template #actions>
            <TuiBadge :variant="statusVariant(quickStatus)">state: {{ quickStatus }}</TuiBadge>
          </template>
          <div class="space-y-4">
            <TuiSelect
              label="Agent"
              :options="agentOptions"
              v-model="quickAgentId"
              placeholder="Select agent"
            />
            <div class="border rounded-md border-slate-200 p-3 h-48 overflow-y-auto">
              <p v-if="!quickLog.length" class="text-xs text-slate-600">Messages will appear here.</p>
              <div v-else class="space-y-3">
                <div v-for="(entry, idx) in quickLog" :key="idx" class="text-sm leading-relaxed">
                  <p class="text-xs uppercase tracking-wider text-slate-600">
                    {{ entry.role }} — {{ new Date(entry.ts).toLocaleTimeString() }}
                  </p>
                  <p class="whitespace-pre-wrap text-slate-800">{{ entry.text }}</p>
                </div>
              </div>
            </div>
            <div class="space-y-2">
               <label class="text-xs uppercase tracking-wider text-slate-600">message</label>
              <textarea
                v-model="quickComposer"
                rows="3"
                :disabled="quickSending || !quickAgentId"
                placeholder="Ping the agent without leaving the dashboard."
                class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-200 disabled:cursor-not-allowed disabled:bg-slate-100"
              ></textarea>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <TuiButton size="sm" :loading="quickSending" @click="sendQuickMessage" :disabled="quickSending || !quickAgentId">
                send
              </TuiButton>
              <TuiButton variant="outline" size="sm" @click="resetQuickChat">reset</TuiButton>
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Runtime" subtitle="MCP Servers">
          <template #actions>
            <span v-if="mcpError" class="text-xs text-red-500">{{ mcpError }}</span>
            <TuiButton size="sm" variant="outline" @click="loadMcps" :loading="isLoadingMcps">refresh</TuiButton>
          </template>
          <div v-if="isLoadingMcps" class="text-sm text-slate-600 py-4">Loading MCP servers...</div>
          <div v-else-if="!mcps.length" class="text-sm text-slate-600 py-4">No MCP servers registered yet.</div>
          <div v-else class="divide-y divide-slate-200">
            <div
              v-for="server in mcps"
              :key="server.id"
              class="flex flex-wrap items-center justify-between gap-4 px-5 py-3"
            >
              <div class="flex min-w-0 flex-1 items-center gap-4">
                <div class="min-w-0 flex-1">
                  <p class="truncate text-base font-semibold">{{ server.name }}</p>
                  <p class="truncate text-xs text-slate-600">{{ server.endpoint }}</p>
                </div>
                <TuiBadge :variant="statusVariant(server.status)" class="w-24 flex-shrink-0 justify-center">
                  {{ server.status }}
                </TuiBadge>
              </div>
              <div class="flex flex-wrap justify-start gap-2">
                <TuiButton
                  size="sm"
                  variant="outline"
                  :loading="togglingMcpId === server.id"
                  @click="toggleMcp(server, 'start')"
                >
                  start
                </TuiButton>
                <TuiButton
                  size="sm"
                  variant="ghost"
                  class="text-red-600 hover:bg-red-50"
                  :loading="togglingMcpId === server.id"
                  @click="toggleMcp(server, 'stop')"
                >
                  stop
                </TuiButton>
              </div>
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Health & Vitals" subtitle="System">
          <div class="space-y-4">
            <div v-if="isLoadingHealth" class="text-sm text-slate-600">Checking health...</div>
            <div v-else class="text-sm text-slate-700 space-y-1">
              <p><strong>API:</strong> {{ health?.api_status || 'unknown' }}</p>
              <p><strong>DB:</strong> {{ health?.database_status?.message || '—' }}</p>
            </div>
            <div class="space-y-1">
              <p class="text-xs uppercase tracking-wider text-slate-600">Recent Events</p>
              <p class="mt-1 text-sm text-slate-600 min-h-[3em]">
                {{ message || 'Use quick chat or MCP controls to populate this space.' }}
              </p>
            </div>
            <div class="space-y-2 text-xs text-slate-600">
              <p class="text-xs uppercase tracking-wider text-slate-600">API Endpoints</p>
              <p><strong>Agents</strong>: GET /agents/</p>
              <p><strong>MCP</strong>: GET /mcp/servers</p>
              <p><strong>Chat</strong>: POST /chat/</p>
              <p><strong>Health</strong>: GET /health</p>
            </div>
          </div>
        </TuiCard>
      </div>
    </main>
  </div>
</template>

