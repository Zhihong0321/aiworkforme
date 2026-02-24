<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import { request } from '../services/api'
import { store } from '../store'

const isLoading = ref(false)
const isSaving = ref(false)
const isScanning = ref(false)
const isTriggering = ref(false)
const pageMessage = ref('')
const errorMessage = ref('')

const control = ref({
  enabled: true,
  scan_frequency_messages: 4,
  aggressiveness: 'BALANCED',
  not_interested_strategy: 'PROMO',
  rejected_strategy: 'DISCOUNT',
  double_reject_strategy: 'STOP'
})

const threads = ref([])

const statusOrder = {
  DOUBLE_REJECT: 0,
  REJECTED: 1,
  NOT_INTERESTED: 2,
  CONSIDERING: 3,
  NO_RESPONSE: 4,
  POSITIVE: 5
}

const sortedThreads = computed(() => {
  return [...threads.value].sort((a, b) => {
    const sa = statusOrder[a.status] ?? 99
    const sb = statusOrder[b.status] ?? 99
    if (sa !== sb) return sa - sb
    const ta = a.next_followup_at ? new Date(a.next_followup_at).getTime() : Number.MAX_SAFE_INTEGER
    const tb = b.next_followup_at ? new Date(b.next_followup_at).getTime() : Number.MAX_SAFE_INTEGER
    return ta - tb
  })
})

const formatDate = (value) => {
  if (!value) return 'Not scheduled'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

const statusLabel = (status) => {
  const labels = {
    NO_RESPONSE: 'No Response',
    CONSIDERING: 'Considering',
    POSITIVE: 'Positive',
    NOT_INTERESTED: 'Not Interested',
    REJECTED: 'Rejected',
    DOUBLE_REJECT: 'Double Reject'
  }
  return labels[status] || status
}

const statusVariant = (status) => {
  if (status === 'POSITIVE') return 'success'
  if (status === 'CONSIDERING') return 'info'
  if (status === 'NO_RESPONSE') return 'muted'
  return 'warning'
}

const strategyLabel = (value) => {
  return value === 'STOP' ? 'Stop' : value === 'PROMO' ? 'Promo' : value === 'DISCOUNT' ? 'Discount' : 'Other'
}

const traceText = (trace) => {
  if (!trace || typeof trace !== 'object') return 'No trace recorded yet.'
  try {
    return JSON.stringify(trace, null, 2)
  } catch {
    return 'Trace unavailable.'
  }
}

const ensureWorkspace = async () => {
  if (!store.activeWorkspaceId) {
    await store.fetchWorkspaces()
  }
  if (!store.activeWorkspaceId) {
    throw new Error('No active workspace found')
  }
  return store.activeWorkspaceId
}

const fetchControl = async () => {
  const workspaceId = await ensureWorkspace()
  control.value = await request(`/workspaces/${workspaceId}/ai-crm/control`)
}

const fetchThreads = async () => {
  const workspaceId = await ensureWorkspace()
  threads.value = await request(`/workspaces/${workspaceId}/ai-crm/threads`)
}

const loadAll = async () => {
  isLoading.value = true
  errorMessage.value = ''
  try {
    await Promise.all([fetchControl(), fetchThreads()])
  } catch (e) {
    errorMessage.value = e.message || 'Failed to load AI CRM data'
  } finally {
    isLoading.value = false
  }
}

const saveControl = async () => {
  isSaving.value = true
  errorMessage.value = ''
  pageMessage.value = ''
  try {
    const workspaceId = await ensureWorkspace()
    const payload = {
      ...control.value,
      scan_frequency_messages: Number(control.value.scan_frequency_messages || 4)
    }
    control.value = await request(`/workspaces/${workspaceId}/ai-crm/control`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
    pageMessage.value = 'AI CRM settings saved'
  } catch (e) {
    errorMessage.value = e.message || 'Failed to save settings'
  } finally {
    isSaving.value = false
  }
}

const runScan = async (forceAll = false) => {
  isScanning.value = true
  errorMessage.value = ''
  pageMessage.value = ''
  try {
    const workspaceId = await ensureWorkspace()
    const result = await request(`/workspaces/${workspaceId}/ai-crm/scan`, {
      method: 'POST',
      body: JSON.stringify({ force_all: forceAll })
    })
    await fetchThreads()
    pageMessage.value = `Scan complete: scanned ${result.scanned_threads}, skipped ${result.skipped_threads}, scheduled ${result.next_followups_set}.`
    if (Array.isArray(result.errors) && result.errors.length > 0) {
      errorMessage.value = result.errors.join(' | ')
    }
  } catch (e) {
    errorMessage.value = e.message || 'Failed to run AI scan'
  } finally {
    isScanning.value = false
  }
}

const triggerDue = async () => {
  isTriggering.value = true
  errorMessage.value = ''
  pageMessage.value = ''
  try {
    const workspaceId = await ensureWorkspace()
    const result = await request(`/workspaces/${workspaceId}/ai-crm/trigger-due`, {
      method: 'POST'
    })
    await fetchThreads()
    pageMessage.value = `Triggered follow-ups: ${result.triggered}. Skipped: ${result.skipped}.`
    if (Array.isArray(result.errors) && result.errors.length > 0) {
      errorMessage.value = result.errors.join(' | ')
    }
  } catch (e) {
    errorMessage.value = e.message || 'Failed to trigger due follow-ups'
  } finally {
    isTriggering.value = false
  }
}

watch(
  () => store.activeWorkspaceId,
  async () => {
    if (store.activeWorkspaceId) {
      await loadAll()
    }
  }
)

onMounted(loadAll)
</script>

<template>
  <div class="bg-aurora min-h-screen">
    <main class="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-10 space-y-6">
      <header class="tui-surface rounded-3xl border border-slate-200 p-6">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="space-y-2">
            <p class="text-[10px] uppercase font-black tracking-[0.3em] text-orange-600">AI Control CRM</p>
            <h1 class="text-3xl font-black text-slate-900 tracking-tight">Conversation Scan + Follow-up Trigger</h1>
            <p class="text-sm text-slate-600 max-w-3xl">
              AI scans each conversation every N messages, classifies lead status, and schedules follow-up timing with passive, balanced, or aggressive behavior.
            </p>
          </div>
          <div class="flex gap-2">
            <TuiButton @click="runScan(false)" :loading="isScanning">Scan Eligible Threads</TuiButton>
            <TuiButton @click="runScan(true)" :loading="isScanning" variant="outline">Force Full Scan</TuiButton>
            <TuiButton @click="triggerDue" :loading="isTriggering" variant="outline">Trigger Due Now</TuiButton>
          </div>
        </div>
      </header>

      <TuiCard title="AI CRM Controls" subtitle="Set scan frequency, follow-up aggressiveness, and rejected-lead strategy">
        <div v-if="isLoading" class="text-sm text-slate-600 py-6">Loading AI CRM control...</div>
        <div v-else class="space-y-5">
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <label class="space-y-2">
              <span class="text-[10px] font-black uppercase tracking-widest text-slate-600">Enable AI CRM</span>
              <select v-model="control.enabled" class="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-800">
                <option :value="true">Enabled</option>
                <option :value="false">Disabled</option>
              </select>
            </label>
            <TuiInput
              v-model="control.scan_frequency_messages"
              type="number"
              label="Scan Every N Messages"
              hint="Min 3, max 10"
              :min="3"
              :max="10"
            />
            <label class="space-y-2">
              <span class="text-[10px] font-black uppercase tracking-widest text-slate-600">Follow-up Aggressiveness</span>
              <select v-model="control.aggressiveness" class="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-800">
                <option value="PASSIVE">Passive</option>
                <option value="BALANCED">Balanced</option>
                <option value="AGGRESSIVE">Aggressive</option>
              </select>
            </label>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <label class="space-y-2">
              <span class="text-[10px] font-black uppercase tracking-widest text-slate-600">Not Interested Strategy</span>
              <select v-model="control.not_interested_strategy" class="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-800">
                <option value="PROMO">Promo</option>
                <option value="DISCOUNT">Discount</option>
                <option value="OTHER">Other</option>
                <option value="STOP">Stop Follow-up</option>
              </select>
            </label>
            <label class="space-y-2">
              <span class="text-[10px] font-black uppercase tracking-widest text-slate-600">Rejected Strategy</span>
              <select v-model="control.rejected_strategy" class="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-800">
                <option value="DISCOUNT">Discount</option>
                <option value="PROMO">Promo</option>
                <option value="OTHER">Other</option>
                <option value="STOP">Stop Follow-up</option>
              </select>
            </label>
            <label class="space-y-2">
              <span class="text-[10px] font-black uppercase tracking-widest text-slate-600">Double Reject Strategy</span>
              <select v-model="control.double_reject_strategy" class="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-800">
                <option value="STOP">Stop Follow-up</option>
                <option value="DISCOUNT">Discount</option>
                <option value="PROMO">Promo</option>
                <option value="OTHER">Other</option>
              </select>
            </label>
          </div>

          <div class="pt-3 border-t border-slate-200 flex justify-end">
            <TuiButton @click="saveControl" :loading="isSaving">Save AI CRM Controls</TuiButton>
          </div>
        </div>
      </TuiCard>

      <TuiCard title="Thread Status" subtitle="Live AI classification and follow-up schedule per conversation">
        <div v-if="isLoading" class="text-sm text-slate-600 py-6">Loading conversation states...</div>
        <div v-else-if="sortedThreads.length === 0" class="text-sm text-slate-600 py-6">No active conversation threads found in this workspace.</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full min-w-[1400px] text-sm">
            <thead>
              <tr class="text-left text-[10px] uppercase tracking-[0.2em] text-slate-600 border-b border-slate-200">
                <th class="py-3 pr-3">Lead</th>
                <th class="py-3 pr-3">Status</th>
                <th class="py-3 pr-3">Reaction</th>
                <th class="py-3 pr-3">Strategy</th>
                <th class="py-3 pr-3">Reject Count</th>
                <th class="py-3 pr-3">Messages</th>
                <th class="py-3 pr-3">Next Follow-up</th>
                <th class="py-3 pr-3">Last Scan</th>
                <th class="py-3">Summary</th>
                <th class="py-3">Reason Trace</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in sortedThreads" :key="row.thread_id" class="border-b border-slate-100 align-top">
                <td class="py-3 pr-3">
                  <p class="font-bold text-slate-900">{{ row.lead_name || `Lead #${row.lead_id}` }}</p>
                  <p class="text-[11px] text-slate-600">{{ row.lead_external_id }}</p>
                </td>
                <td class="py-3 pr-3">
                  <TuiBadge :variant="statusVariant(row.status)">{{ statusLabel(row.status) }}</TuiBadge>
                </td>
                <td class="py-3 pr-3 text-[11px] text-slate-600">{{ row.customer_reaction || '-' }}</td>
                <td class="py-3 pr-3 text-[11px] text-slate-700">{{ strategyLabel(row.followup_strategy) }} · {{ row.aggressiveness }}</td>
                <td class="py-3 pr-3 text-[11px] text-slate-700">{{ row.reject_count }}</td>
                <td class="py-3 pr-3">
                  <p class="text-[11px] text-slate-700">{{ row.total_messages }} total</p>
                  <p v-if="row.pending_scan" class="text-[10px] font-bold text-orange-600">Scan pending</p>
                </td>
                <td class="py-3 pr-3 text-[11px] text-slate-600">{{ formatDate(row.next_followup_at) }}</td>
                <td class="py-3 pr-3 text-[11px] text-slate-600">{{ formatDate(row.last_scanned_at) }}</td>
                <td class="py-3 text-[11px] text-slate-600">
                  <p>{{ row.summary || row.last_message_preview || '-' }}</p>
                </td>
                <td class="py-3 pl-3">
                  <details class="rounded-lg border border-slate-200 bg-slate-50/80">
                    <summary class="cursor-pointer px-3 py-2 text-[11px] font-bold text-slate-700">View Trace</summary>
                    <pre class="max-w-[360px] overflow-auto border-t border-slate-200 px-3 py-2 text-[10px] leading-5 text-slate-700">{{ traceText(row.reason_trace) }}</pre>
                  </details>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </TuiCard>

      <p v-if="pageMessage" class="text-sm font-bold text-emerald-700">{{ pageMessage }}</p>
      <p v-if="errorMessage" class="text-sm font-bold text-red-700">{{ errorMessage }}</p>
    </main>
  </div>
</template>
