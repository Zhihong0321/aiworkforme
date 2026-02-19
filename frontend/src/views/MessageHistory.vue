<script setup>
import { computed, onMounted, ref } from 'vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import { request } from '../services/api'

const platformMessages = ref([])
const platformMessagesLoading = ref(true)
const historyDirection = ref('')
const historyAiOnly = ref(true)
const historyLimit = ref(100)
const message = ref('')

const toNumber = (value) => {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

const getPromptTokens = (msg) => toNumber(msg?.llm_prompt_tokens)
const getCompletionTokens = (msg) => toNumber(msg?.llm_completion_tokens)
const getTotalTokens = (msg) => {
  const total = toNumber(msg?.llm_total_tokens)
  if (total > 0) return total
  return getPromptTokens(msg) + getCompletionTokens(msg)
}
const getCostUsd = (msg) => {
  const direct = toNumber(msg?.llm_estimated_cost_usd)
  if (direct > 0) return direct
  return toNumber(msg?.ai_trace?.usage?.estimated_cost_usd)
}
const getCostPerToken = (msg) => {
  const totalTokens = getTotalTokens(msg)
  if (totalTokens <= 0) return 0
  return getCostUsd(msg) / totalTokens
}
const getCostPer1M = (msg) => getCostPerToken(msg) * 1_000_000

const formatUsd = (value, digits = 6) => `$${toNumber(value).toFixed(digits)}`
const formatInt = (value) => toNumber(value).toLocaleString()

const modelSummary = computed(() => {
  const map = new Map()
  for (const msg of platformMessages.value) {
    if (!msg?.llm_model) continue
    const key = `${msg.llm_provider || 'unknown'}|${msg.llm_model}`
    if (!map.has(key)) {
      map.set(key, {
        provider: msg.llm_provider || 'unknown',
        model: msg.llm_model,
        message_count: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
        total_cost_usd: 0
      })
    }
    const row = map.get(key)
    row.message_count += 1
    row.prompt_tokens += getPromptTokens(msg)
    row.completion_tokens += getCompletionTokens(msg)
    row.total_tokens += getTotalTokens(msg)
    row.total_cost_usd += getCostUsd(msg)
  }
  return Array.from(map.values())
    .map((row) => {
      const costPerToken = row.total_tokens > 0 ? row.total_cost_usd / row.total_tokens : 0
      return {
        ...row,
        cost_per_token_usd: costPerToken,
        cost_per_1m_tokens_usd: costPerToken * 1_000_000
      }
    })
    .sort((a, b) => b.total_cost_usd - a.total_cost_usd)
})

const fetchPlatformMessages = async () => {
  platformMessagesLoading.value = true
  message.value = ''
  try {
    const params = new URLSearchParams()
    params.set('limit', String(historyLimit.value || 100))
    if (historyDirection.value) params.set('direction', historyDirection.value)
    params.set('ai_only', historyAiOnly.value ? 'true' : 'false')
    const data = await request(`/platform/messages/history?${params.toString()}`)
    platformMessages.value = Array.isArray(data) ? data : []
  } catch (e) {
    message.value = `Error: ${e.message}`
    platformMessages.value = []
  } finally {
    platformMessagesLoading.value = false
  }
}

onMounted(() => {
  fetchPlatformMessages()
})
</script>

<template>
  <div class="relative min-h-screen">
    <main class="relative z-10 mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-10 space-y-6">
      <header class="tui-surface rounded-3xl border border-slate-200 p-8 shadow-sm">
        <p class="text-[10px] uppercase font-black tracking-[0.32em] text-indigo-600">Platform Admin</p>
        <h1 class="mt-2 text-3xl font-black text-slate-900 tracking-tight">Message History</h1>
        <p class="mt-2 text-sm text-slate-500">Review inbound/outbound messages with LLM usage and trace metadata.</p>
      </header>

      <TuiCard title="Filters" subtitle="Narrow the history view">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label class="text-[10px] font-black uppercase tracking-widest text-slate-400 block mb-2">Direction</label>
            <select v-model="historyDirection" class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800">
              <option value="">All</option>
              <option value="inbound">Inbound</option>
              <option value="outbound">Outbound</option>
            </select>
          </div>
          <div>
            <label class="text-[10px] font-black uppercase tracking-widest text-slate-400 block mb-2">Limit</label>
            <input v-model.number="historyLimit" type="number" min="1" max="1000" class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800" />
          </div>
          <div class="flex items-end">
            <label class="inline-flex items-center gap-2 text-xs font-bold text-slate-700">
              <input v-model="historyAiOnly" type="checkbox" class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
              AI only
            </label>
          </div>
          <div class="flex items-end justify-end">
            <TuiButton @click="fetchPlatformMessages" :loading="platformMessagesLoading" size="sm">Refresh</TuiButton>
          </div>
        </div>
        <p v-if="message" class="mt-3 text-xs font-semibold text-red-600">{{ message }}</p>
      </TuiCard>

      <TuiCard title="Messages" subtitle="Latest platform message records">
        <div v-if="!platformMessagesLoading && modelSummary.length > 0" class="mb-4 overflow-x-auto">
          <table class="w-full text-xs border border-slate-200 rounded-xl overflow-hidden">
            <thead>
              <tr class="bg-slate-50 text-left text-slate-600 uppercase tracking-wide">
                <th class="px-3 py-2">Model</th>
                <th class="px-3 py-2">Provider</th>
                <th class="px-3 py-2">Msgs</th>
                <th class="px-3 py-2">Input</th>
                <th class="px-3 py-2">Output</th>
                <th class="px-3 py-2">Total</th>
                <th class="px-3 py-2">Cost</th>
                <th class="px-3 py-2">$/Token</th>
                <th class="px-3 py-2">$/1M</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in modelSummary" :key="`${row.provider}:${row.model}`" class="border-t border-slate-100">
                <td class="px-3 py-2 font-semibold">{{ row.model }}</td>
                <td class="px-3 py-2">{{ row.provider }}</td>
                <td class="px-3 py-2">{{ formatInt(row.message_count) }}</td>
                <td class="px-3 py-2">{{ formatInt(row.prompt_tokens) }}</td>
                <td class="px-3 py-2">{{ formatInt(row.completion_tokens) }}</td>
                <td class="px-3 py-2">{{ formatInt(row.total_tokens) }}</td>
                <td class="px-3 py-2">{{ formatUsd(row.total_cost_usd, 6) }}</td>
                <td class="px-3 py-2">{{ formatUsd(row.cost_per_token_usd, 9) }}</td>
                <td class="px-3 py-2">{{ formatUsd(row.cost_per_1m_tokens_usd, 3) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="platformMessagesLoading" class="text-sm text-slate-500 py-4">Loading message history...</div>
        <div v-else-if="platformMessages.length === 0" class="text-sm text-slate-500 py-4">No messages found for the selected filters.</div>
        <div v-else class="space-y-3 max-h-[36rem] overflow-y-auto pr-1">
          <article v-for="msg in platformMessages" :key="msg.message_id" class="rounded-2xl border border-slate-200 bg-white p-4">
            <div class="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-widest font-black text-slate-500">
              <span>#{{ msg.message_id }}</span>
              <span>{{ msg.direction }}</span>
              <span>{{ msg.channel }}</span>
              <span>tenant {{ msg.tenant_id }}</span>
              <span>lead {{ msg.lead_external_id || msg.lead_id }}</span>
              <span v-if="msg.llm_provider">provider {{ msg.llm_provider }}</span>
              <span v-if="msg.llm_model">model {{ msg.llm_model }}</span>
              <span v-if="getPromptTokens(msg) > 0">input {{ formatInt(getPromptTokens(msg)) }}</span>
              <span v-if="getCompletionTokens(msg) > 0">output {{ formatInt(getCompletionTokens(msg)) }}</span>
              <span v-if="getTotalTokens(msg) > 0">tokens {{ formatInt(getTotalTokens(msg)) }}</span>
              <span v-if="getCostUsd(msg) > 0">cost {{ formatUsd(getCostUsd(msg), 6) }}</span>
              <span v-if="getCostUsd(msg) > 0 && getTotalTokens(msg) > 0">$/token {{ formatUsd(getCostPerToken(msg), 9) }}</span>
              <span v-if="getCostUsd(msg) > 0 && getTotalTokens(msg) > 0">$/1M {{ formatUsd(getCostPer1M(msg), 3) }}</span>
            </div>
            <p class="mt-2 text-sm text-slate-800 whitespace-pre-wrap">{{ msg.text_content || '(empty)' }}</p>
            <pre class="mt-3 rounded-xl bg-slate-950 text-slate-100 text-[11px] leading-5 p-3 overflow-x-auto">{{ JSON.stringify(msg.ai_trace || {}, null, 2) }}</pre>
          </article>
        </div>
      </TuiCard>
    </main>
  </div>
</template>
