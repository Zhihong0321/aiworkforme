<script setup>
import { onMounted, reactive, ref } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'

const API_BASE = `${window.location.origin}/api/v1`

const servers = ref([])
const isLoading = ref(true)
const isSaving = ref(false)
const deletingServerId = ref(null)
const message = ref('')

const form = reactive({
  name: '',
  script: '',
  env_vars: '{}'
})

const statusVariant = (status) => {
  const normalized = (status || '').toLowerCase()
  if (normalized === 'online' || normalized === 'live' || normalized === 'ready') return 'success'
  if (normalized === 'syncing' || normalized === 'watch' || normalized === 'cooldown') return 'warning'
  return 'muted'
}

const resetForm = () => {
  form.name = ''
  form.script = ''
  form.env_vars = '{}'
}

const loadServers = async () => {
  isLoading.value = true
  message.value = ''
  try {
    const res = await fetch(`${API_BASE}/mcp/servers`)
    if (!res.ok) throw new Error('Failed to fetch servers')
    const data = await res.json()
    servers.value = Array.isArray(data)
      ? data.map((server, index) => ({
          id: server.id ?? index,
          name: server.name ?? 'server',
          status: (server.status ?? 'online').toLowerCase(),
          endpoint: server.endpoint ?? server.script ?? '',
          env_vars: server.env_vars ?? server.env ?? '{}'
        }))
      : []
  } catch (error) {
    console.error('Failed to load mcp servers', error)
    message.value = 'Failed to load MCP servers from API.'
    servers.value = []
  } finally {
    isLoading.value = false
  }
}

const saveServer = async () => {
  isSaving.value = true
  message.value = ''
  try {
    const payload = {
      name: form.name,
      script: form.script,
      env_vars: form.env_vars || '{}'
    }
    const res = await fetch(`${API_BASE}/mcp/servers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!res.ok) throw new Error('Failed to create server')
    message.value = 'MCP server created.'
    resetForm()
    await loadServers()
  } catch (error) {
    console.error('Failed to create mcp server', error)
    message.value = 'Create failed. Check API connectivity.'
  } finally {
    isSaving.value = false
  }
}

const deleteServer = async (serverId) => {
  if (!serverId) return
  const confirmDelete = window.confirm('Delete this MCP server?')
  if (!confirmDelete) return
  deletingServerId.value = serverId
  message.value = ''
  try {
    const res = await fetch(`${API_BASE}/mcp/servers/${serverId}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('Failed to delete server')
    message.value = 'MCP server deleted.'
    await loadServers()
  } catch (error) {
    console.error('Failed to delete mcp server', error)
    message.value = 'Delete failed. Confirm backend DELETE /mcp/servers/{id} is available.'
  } finally {
    deletingServerId.value = null
  }
}

onMounted(() => {
  loadServers()
})
</script>

<template>
  <div class="relative min-h-screen">
    <main class="relative z-10 mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:px-10 space-y-8">
      <header class="tui-surface rounded-xl border border-slate-200 p-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="space-y-2">
            <p class="text-xs uppercase tracking-[0.32em] text-slate-500">z.ai admin</p>
            <h1 class="text-3xl font-bold text-slate-900">MCP Management</h1>
            <p class="text-sm text-slate-600">
              Register MCP servers, check status, and view endpoints for agents to link.
            </p>
            <div class="flex flex-wrap items-center gap-2">
              <TuiBadge variant="info">/api/v1/mcp/servers</TuiBadge>
            <TuiBadge variant="muted">base: dynamic (current host)</TuiBadge>
            </div>
          </div>
          <TuiButton size="sm" variant="outline" @click="loadServers">Refresh</TuiButton>
        </div>
      </header>

      <section class="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <TuiCard title="Servers" subtitle="list">
          <div class="mb-4 text-xs text-slate-600" v-if="message">{{ message }}</div>
          <div v-if="isLoading" class="text-sm text-slate-600">Loading MCP servers...</div>
          <div v-else class="divide-y divide-slate-200">
            <div
              v-for="server in servers"
              :key="server.id"
              class="grid gap-3 py-4 sm:grid-cols-[1fr_1fr_auto] sm:items-center"
            >
              <div class="space-y-1">
                <p class="text-base font-semibold text-slate-900">{{ server.name }}</p>
                <p class="text-sm text-slate-600 break-all">{{ server.endpoint }}</p>
                <p class="text-[11px] uppercase tracking-[0.18em] text-slate-500">env</p>
                <p class="text-xs text-slate-700 break-all">{{ server.env_vars }}</p>
              </div>
              <div class="flex flex-col gap-2 text-sm text-slate-700">
                <p class="text-[11px] uppercase tracking-[0.18em] text-slate-500">status</p>
                <TuiBadge :variant="statusVariant(server.status)" class="w-24 justify-center">
                  {{ server.status || 'online' }}
                </TuiBadge>
              </div>
              <div class="flex justify-start gap-2 sm:justify-end">
                <TuiButton size="sm" variant="outline">refresh</TuiButton>
                <TuiButton
                  size="sm"
                  variant="ghost"
                  class="text-red-600"
                  :loading="deletingServerId === server.id"
                  @click="deleteServer(server.id)"
                >
                  delete
                </TuiButton>
              </div>
            </div>
            <div v-if="!servers.length" class="py-6 text-sm text-slate-600">
              No MCP servers found. Create one using the form.
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Create MCP Server" subtitle="register">
          <div class="space-y-4">
            <TuiInput label="Name" placeholder="repo-tools" v-model="form.name" />
            <TuiInput label="Script Path" placeholder="/app/mcp/repo-tools.py" v-model="form.script" />
            <label class="flex flex-col gap-2 text-sm text-slate-800">
              <div class="flex items-center justify-between">
                <span class="text-[11px] uppercase tracking-[0.2em] text-slate-600">Env Vars (JSON)</span>
                <span class="text-[11px] text-slate-500">optional</span>
              </div>
              <div class="relative breathing-ring">
                <textarea
                  v-model="form.env_vars"
                  rows="3"
                  placeholder='{"API_KEY":"..."}'
                  class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-[inset_0_1px_1px_rgba(15,23,42,0.06)] focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-200"
                ></textarea>
              </div>
            </label>
            <div class="flex flex-wrap gap-3">
              <TuiButton :loading="isSaving" @click="saveServer">Create Server</TuiButton>
              <TuiButton variant="outline" @click="resetForm()">Reset</TuiButton>
            </div>
            <p class="text-xs text-slate-600">POST /mcp/servers with name, script, env_vars</p>
          </div>
        </TuiCard>
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
