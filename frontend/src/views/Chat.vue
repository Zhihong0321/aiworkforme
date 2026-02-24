<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiSelect from '../components/ui/TuiSelect.vue'

const API_BASE = `${window.location.origin}/api/v1`

const route = useRoute()
const router = useRouter()

const agents = ref([])
const isLoadingAgents = ref(true)
const agentError = ref('')
const isSending = ref(false)
const composer = ref('')
const status = ref('idle')
const tokenStats = ref(null)

const conversations = reactive({})
const currentAgentId = ref('')

const statusVariant = (state) => {
  const normalized = (state || '').toLowerCase()
  if (normalized === 'live' || normalized === 'active' || normalized === 'ready') return 'success'
  if (normalized === 'watch' || normalized === 'syncing' || normalized === 'cooldown') return 'warning'
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

const currentConversation = computed(() => ensureConversation(String(currentAgentId.value || '')))

const ensureConversation = (key) => {
  if (!key) return []
  if (!conversations[key]) conversations[key] = []
  return conversations[key]
}

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
            name: agent.name ?? 'Agent',
            status: (agent.status ?? 'ready').toLowerCase()
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

const handleAgentChange = (agentId) => {
  currentAgentId.value = agentId
  router.replace({ name: 'Chat', params: { agentId } })
}

const startNewChat = () => {
  if (!currentAgentId.value) return
  conversations[String(currentAgentId.value)] = []
  tokenStats.value = null
}

const sendMessage = async () => {
  if (!currentAgentId.value || !composer.value.trim()) return

  const agentId = currentAgentId.value
  const messageText = composer.value.trim()
  composer.value = ''

  const convo = currentConversation.value
  convo.push({ role: 'user', text: messageText, ts: new Date().toISOString() })
  status.value = 'sending'
  isSending.value = true
  agentError.value = ''

  try {
    const res = await fetch(`${API_BASE}/chat/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        agent_id: parseInt(agentId),
        message: messageText
      })
    })

    if (!res.ok) {
      throw new Error(`API Error: ${res.statusText}`)
    }

    const data = await res.json()
    
    // Add assistant response to conversation
    convo.push({
      role: 'assistant',
      text: data.response || 'No response text.',
      ts: new Date().toISOString()
    })
    
    status.value = 'idle'
  } catch (error) {
    console.error('Chat send failed', error)
    status.value = 'degraded'
    agentError.value = error.message || 'Failed to send message'
    convo.push({
      role: 'assistant',
      text: 'Send failed. Please try again.',
      ts: new Date().toISOString()
    })
  } finally {
    isSending.value = false
  }
}

watch(
  () => route.params.agentId,
  () => setAgentFromRoute()
)

onMounted(() => {
  setAgentFromRoute()
  loadAgents()
})
</script>

<template>
  <div class="relative min-h-screen">
    <main class="relative z-10 mx-auto w-full max-w-2xl px-3 py-4 sm:px-4 space-y-4">
      
      <!-- Simplified Header -->
      <header class="flex items-center justify-between">
        <h1 class="text-xl font-bold text-[var(--text)]">Chat</h1>
        <div class="flex items-center gap-2">
           <TuiButton size="sm" variant="outline" @click="startNewChat" :disabled="!currentAgentId">New Chat</TuiButton>
           <TuiButton size="sm" variant="ghost" @click="loadAgents">Refresh</TuiButton>
        </div>
      </header>

      <!-- Agent Selector -->
      <section class="flex flex-col gap-2">
        <div class="flex items-center gap-2">
          <div class="flex-grow">
             <TuiSelect
              :options="agentOptions"
              v-model="currentAgentId"
              placeholder="Select agent"
              @update:modelValue="handleAgentChange"
            />
          </div>
          <TuiBadge v-if="currentAgent" :variant="statusVariant(currentAgent.status)" class="shrink-0">
              {{ currentAgent.status || 'ready' }}
          </TuiBadge>
        </div>
        <p v-if="agentError" class="text-xs text-red-600">{{ agentError }}</p>
      </section>

      <!-- Chat Area -->
      <section class="flex flex-col gap-3">
        <!-- Messages -->
        <div
          class="flex flex-col gap-3 border border-[var(--border)] bg-white p-3 min-h-[50vh] max-h-[70vh] overflow-y-auto rounded-md"
        >
          <p v-if="!currentAgentId" class="text-sm text-[var(--muted)] text-center mt-10">Select an agent to start chatting.</p>
          <div v-else class="flex flex-col gap-3">
             <div v-if="currentConversation.length === 0" class="text-sm text-[var(--muted)] text-center mt-10">
               No messages yet. Say hello!
             </div>
            <div
              v-for="(message, idx) in currentConversation"
              :key="idx"
              :class="[
                'flex flex-col max-w-[85%]',
                message.role === 'user' ? 'self-end items-end' : 'self-start items-start'
              ]"
            >
              <div
                :class="[
                  'px-3 py-2 text-sm rounded-lg',
                  message.role === 'user'
                    ? 'bg-[var(--accent-soft)] text-[var(--text)] border border-[#ff8200]'
                    : 'bg-gray-50 text-[var(--text)] border border-[var(--border)]'
                ]"
              >
                <p class="whitespace-pre-wrap leading-relaxed">{{ message.text }}</p>
              </div>
              <span class="text-[10px] text-[var(--muted)] uppercase tracking-wider mt-1">
                {{ message.role === 'assistant' ? (currentAgent?.name || 'Agent') : 'You' }}
              </span>
            </div>
            
            <div v-if="isSending" class="self-start">
               <div class="px-3 py-2 text-sm text-[var(--muted)] italic bg-gray-50 border border-[var(--border)] rounded-lg">
                  Thinking...
               </div>
            </div>
          </div>
        </div>

        <!-- Input -->
        <div class="space-y-2">
          <div class="relative breathing-ring">
            <textarea
              v-model="composer"
              rows="3"
              :disabled="!currentAgentId || isSending"
              placeholder="Message..."
              class="w-full rounded-md border border-[var(--border-strong)] bg-white px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--text)] disabled:bg-gray-50"
              @keydown.enter.prevent="sendMessage"
            ></textarea>
          </div>
          <TuiButton class="w-full" size="md" :loading="isSending" @click="sendMessage" :disabled="!currentAgentId || isSending">
            Send
          </TuiButton>
        </div>
      </section>

    </main>
  </div>
</template>

<style scoped>
.breathing-ring {
  position: relative;
  border-radius: 0.375rem; /* rounded-md */
}

.breathing-ring::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: inherit;
  background: linear-gradient(120deg, #16f2b3, #7c3aed, #06b6d4, #16f2b3);
  background-size: 220% 220%;
  opacity: 0;
  z-index: 0;
  filter: blur(1px);
  transition: opacity 0.3s ease;
  animation: breatheGradient 3s ease-in-out infinite;
  pointer-events: none;
}

.breathing-ring:focus-within::after {
  opacity: 0.5;
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
