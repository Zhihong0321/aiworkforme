<script setup>
import { computed, onMounted, ref } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import PlatformAdminShell from '../components/platform/PlatformAdminShell.vue'
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
  } catch (error) {
    message.value = `Error: ${error.message}`
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
  <PlatformAdminShell>
    <template #sidebar>
      <div class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/92 p-5 shadow-panel">
        <p class="text-[10px] font-black uppercase tracking-[0.3em] text-ink-subtle">Platform Admin</p>
        <h2 class="mt-2 text-2xl font-bold text-ink">Message Review</h2>
        <p class="mt-2 text-sm text-ink-muted">A focused review lane for message history, costs, and trace payloads.</p>
        <div class="mt-5 space-y-2">
          <a href="/settings" class="block rounded-2xl border border-line/70 bg-surface px-4 py-3 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-primary/5">Back to console</a>
          <a href="/settings/benchmark" class="block rounded-2xl border border-line/70 bg-surface px-4 py-3 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-primary/5">Benchmark</a>
        </div>
      </div>
    </template>

    <section class="rounded-[1.9rem] border border-line/80 bg-[linear-gradient(140deg,_rgb(var(--panel-elevated-rgb)_/_0.96),_rgb(var(--accent-soft-rgb)_/_0.18))] p-6 shadow-panel">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p class="text-[10px] font-black uppercase tracking-[0.32em] text-aurora">Platform Admin</p>
          <h1 class="mt-2 text-3xl font-black tracking-tight text-ink lg:text-4xl">Message history</h1>
          <p class="mt-2 max-w-3xl text-sm text-ink-muted">Review inbound and outbound messages with token usage, cost breakdowns, and trace metadata.</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <TuiBadge variant="info" size="sm">Desktop optimized</TuiBadge>
          <TuiButton @click="fetchPlatformMessages" :loading="platformMessagesLoading">Refresh</TuiButton>
        </div>
      </div>
      <p v-if="message" class="mt-4 rounded-2xl border border-danger/20 bg-danger/10 px-4 py-3 text-sm font-semibold text-danger">{{ message }}</p>
    </section>

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
          <TuiButton @click="fetchPlatformMessages" :loading="platformMessagesLoading" size="sm">Refresh history</TuiButton>
        </div>
      </div>
    </TuiCard>

    <div class="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
      <TuiCard title="Cost Summary" subtitle="Aggregate by model">
        <div v-if="!platformMessagesLoading && modelSummary.length > 0" class="overflow-x-auto">
          <table class="min-w-full text-xs">
            <thead>
              <tr class="border-b border-line/70 text-left text-ink-subtle">
                <th class="py-2 pr-3">Model</th>
                <th class="py-2 pr-3">Provider</th>
                <th class="py-2 pr-3">Msgs</th>
                <th class="py-2 pr-3">Input</th>
                <th class="py-2 pr-3">Output</th>
                <th class="py-2 pr-3">Total</th>
                <th class="py-2 pr-3">Cost</th>
                <th class="py-2 pr-3">$/Token</th>
                <th class="py-2 pr-3">$/1M</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in modelSummary" :key="`${row.provider}:${row.model}`" class="border-b border-line/40">
                <td class="py-2 pr-3 font-semibold text-ink">{{ row.model }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.provider }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ formatInt(row.message_count) }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ formatInt(row.prompt_tokens) }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ formatInt(row.completion_tokens) }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ formatInt(row.total_tokens) }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ formatUsd(row.total_cost_usd, 6) }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ formatUsd(row.cost_per_token_usd, 9) }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ formatUsd(row.cost_per_1m_tokens_usd, 3) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else-if="platformMessagesLoading" class="py-4 text-sm text-ink-muted">Loading message history...</div>
        <div v-else class="py-4 text-sm text-ink-muted">No messages found for the selected filters.</div>
      </TuiCard>

      <TuiCard title="Messages" subtitle="Latest platform message records">
        <div v-if="platformMessagesLoading" class="py-4 text-sm text-ink-muted">Loading message history...</div>
        <div v-else-if="platformMessages.length === 0" class="py-4 text-sm text-ink-muted">No messages found for the selected filters.</div>
        <div v-else class="space-y-3 max-h-[38rem] overflow-y-auto pr-1">
          <article v-for="msg in platformMessages" :key="msg.message_id" class="rounded-2xl border border-line/70 bg-surface px-4 py-4">
            <div class="flex flex-wrap items-center gap-2 text-[10px] font-black uppercase tracking-widest text-ink-subtle">
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
            <p class="mt-2 whitespace-pre-wrap text-sm text-ink">{{ msg.text_content || '(empty)' }}</p>
            <pre class="mt-3 overflow-x-auto rounded-xl bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">{{ JSON.stringify(msg.ai_trace || {}, null, 2) }}</pre>
          </article>
        </div>
      </TuiCard>
    </div>
  </PlatformAdminShell>
</template>
