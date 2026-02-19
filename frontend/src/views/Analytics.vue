<template>
  <div class="p-8">
    <header class="mb-6 flex items-end justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold mb-2">Analytics</h1>
        <p class="text-[var(--muted)]">Tenant-scoped telemetry and denial monitoring.</p>
      </div>
      <div class="flex items-center gap-2">
        <label class="text-xs uppercase tracking-wide text-[var(--muted)]">Window</label>
        <select
          v-model.number="windowHours"
          class="border border-[var(--border)] rounded px-2 py-1 text-sm bg-white"
          @change="loadAnalytics"
        >
          <option :value="6">6h</option>
          <option :value="24">24h</option>
          <option :value="72">72h</option>
          <option :value="168">7d</option>
        </select>
        <button
          class="px-3 py-1.5 text-sm border border-[var(--border)] rounded bg-white hover:bg-slate-50"
          @click="loadAnalytics"
        >
          Refresh
        </button>
      </div>
    </header>

    <div
      v-if="error"
      class="mb-6 border border-red-200 text-red-700 bg-red-50 rounded-lg px-4 py-3 text-sm"
    >
      {{ error }}
    </div>

    <div v-if="isLoading" class="text-sm text-[var(--muted)] mb-8">Loading analytics...</div>

    <div v-else class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="bg-white p-4 border border-[var(--border)] rounded-lg shadow-sm"
      >
        <div class="text-[10px] font-bold uppercase text-[var(--muted)] mb-2">{{ stat.label }}</div>
        <div class="text-2xl font-bold">{{ stat.value }}</div>
      </div>
    </div>

    <div v-if="summary?.llm_cost_window" class="bg-white p-6 border border-[var(--border)] rounded-lg shadow-sm mb-8">
      <div class="flex items-center justify-between mb-4">
        <h4 class="font-bold text-sm">LLM Cost Analysis</h4>
        <span class="text-xs text-[var(--muted)]">Window {{ windowHours }}h</span>
      </div>

      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div class="rounded border border-[var(--border)] p-3">
          <p class="text-[10px] uppercase tracking-wide text-[var(--muted)]">Total Cost</p>
          <p class="text-lg font-semibold">{{ formatUsd(summary.llm_cost_window.total_cost_usd, 6) }}</p>
        </div>
        <div class="rounded border border-[var(--border)] p-3">
          <p class="text-[10px] uppercase tracking-wide text-[var(--muted)]">Total Tokens</p>
          <p class="text-lg font-semibold">{{ formatNumber(summary.llm_cost_window.total_tokens) }}</p>
        </div>
        <div class="rounded border border-[var(--border)] p-3">
          <p class="text-[10px] uppercase tracking-wide text-[var(--muted)]">Cost / Token</p>
          <p class="text-lg font-semibold">{{ formatUsd(summary.llm_cost_window.cost_per_token_usd, 9) }}</p>
        </div>
        <div class="rounded border border-[var(--border)] p-3">
          <p class="text-[10px] uppercase tracking-wide text-[var(--muted)]">Cost / 1M Tokens</p>
          <p class="text-lg font-semibold">{{ formatUsd(summary.llm_cost_window.cost_per_1m_tokens_usd, 3) }}</p>
        </div>
      </div>

      <div v-if="!summary.llm_cost_window.models || summary.llm_cost_window.models.length === 0" class="text-sm text-[var(--muted)] italic">
        No model usage in selected window.
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border)]">
              <th class="py-2 pr-3">Model</th>
              <th class="py-2 pr-3">Provider</th>
              <th class="py-2 pr-3">Messages</th>
              <th class="py-2 pr-3">Prompt Tokens</th>
              <th class="py-2 pr-3">Completion Tokens</th>
              <th class="py-2 pr-3">Total Tokens</th>
              <th class="py-2 pr-3">Total Cost</th>
              <th class="py-2 pr-3">Cost / Token</th>
              <th class="py-2 pr-3">Cost / 1M</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in summary.llm_cost_window.models"
              :key="`${row.provider}:${row.model}`"
              class="border-b border-[var(--border)] last:border-b-0"
            >
              <td class="py-2 pr-3 font-medium">{{ row.model }}</td>
              <td class="py-2 pr-3">{{ row.provider || 'unknown' }}</td>
              <td class="py-2 pr-3">{{ formatNumber(row.message_count) }}</td>
              <td class="py-2 pr-3">{{ formatNumber(row.prompt_tokens) }}</td>
              <td class="py-2 pr-3">{{ formatNumber(row.completion_tokens) }}</td>
              <td class="py-2 pr-3">{{ formatNumber(row.total_tokens) }}</td>
              <td class="py-2 pr-3">{{ formatUsd(row.total_cost_usd, 6) }}</td>
              <td class="py-2 pr-3">{{ formatUsd(row.cost_per_token_usd, 9) }}</td>
              <td class="py-2 pr-3">{{ formatUsd(row.cost_per_1m_tokens_usd, 3) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="bg-white p-6 border border-[var(--border)] rounded-lg shadow-sm">
      <div class="flex items-center justify-between mb-4">
        <h4 class="font-bold text-sm">Recent Security Events</h4>
        <span class="text-xs text-[var(--muted)]">{{ events.length }} records</span>
      </div>

      <div v-if="events.length === 0" class="text-sm text-[var(--muted)] italic">
        No security events in the selected window.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border)]">
              <th class="py-2 pr-3">Time</th>
              <th class="py-2 pr-3">Endpoint</th>
              <th class="py-2 pr-3">Method</th>
              <th class="py-2 pr-3">Status</th>
              <th class="py-2 pr-3">Reason</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="evt in events"
              :key="evt.id"
              class="border-b border-[var(--border)] last:border-b-0"
            >
              <td class="py-2 pr-3 whitespace-nowrap">{{ formatTs(evt.created_at) }}</td>
              <td class="py-2 pr-3 font-mono text-xs">{{ evt.endpoint }}</td>
              <td class="py-2 pr-3">{{ evt.method }}</td>
              <td class="py-2 pr-3">{{ evt.status_code }}</td>
              <td class="py-2 pr-3">{{ evt.reason }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const API_BASE = `${window.location.origin}/api/v1/analytics`

const windowHours = ref(24)
const isLoading = ref(false)
const error = ref('')
const summary = ref(null)
const events = ref([])

const stats = computed(() => {
  if (!summary.value) return []
  return [
    { label: 'Workspaces', value: summary.value.workspace_count },
    { label: 'Agents', value: summary.value.agent_count },
    { label: 'Leads', value: summary.value.lead_count },
    { label: 'Policy Blocks', value: summary.value.policy_blocks_window },
    { label: 'Denied Access', value: summary.value.denied_events_window }
  ]
})

function formatTs(value) {
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function formatUsd(value, digits = 6) {
  return `$${Number(value || 0).toFixed(digits)}`
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString()
}

async function loadAnalytics() {
  isLoading.value = true
  error.value = ''
  try {
    const [summaryRes, eventsRes] = await Promise.all([
      fetch(`${API_BASE}/summary?window_hours=${windowHours.value}`),
      fetch(`${API_BASE}/security-events?window_hours=${windowHours.value}&limit=20`)
    ])

    if (!summaryRes.ok) {
      const msg = await summaryRes.text()
      throw new Error(msg || 'Failed to load analytics summary')
    }
    if (!eventsRes.ok) {
      const msg = await eventsRes.text()
      throw new Error(msg || 'Failed to load security events')
    }

    summary.value = await summaryRes.json()
    events.value = await eventsRes.json()
  } catch (e) {
    error.value = e?.message || 'Failed to load analytics'
    summary.value = null
    events.value = []
  } finally {
    isLoading.value = false
  }
}

onMounted(loadAnalytics)
</script>
