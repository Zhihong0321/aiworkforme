<script setup>
import { onMounted, ref } from 'vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import { request } from '../services/api'

const platformMessages = ref([])
const platformMessagesLoading = ref(true)
const historyDirection = ref('')
const historyAiOnly = ref(true)
const historyLimit = ref(100)
const message = ref('')

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
              <span v-if="msg.llm_total_tokens !== null && msg.llm_total_tokens !== undefined">tokens {{ msg.llm_total_tokens }}</span>
              <span v-if="msg.llm_estimated_cost_usd !== null && msg.llm_estimated_cost_usd !== undefined">cost ${{ Number(msg.llm_estimated_cost_usd).toFixed(6) }}</span>
            </div>
            <p class="mt-2 text-sm text-slate-800 whitespace-pre-wrap">{{ msg.text_content || '(empty)' }}</p>
            <pre class="mt-3 rounded-xl bg-slate-950 text-slate-100 text-[11px] leading-5 p-3 overflow-x-auto">{{ JSON.stringify(msg.ai_trace || {}, null, 2) }}</pre>
          </article>
        </div>
      </TuiCard>
    </main>
  </div>
</template>
