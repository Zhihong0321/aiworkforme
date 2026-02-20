<template>
  <div class="min-h-[calc(100vh-64px)] w-full bg-onyx font-inter text-slate-200 pb-20 relative overflow-hidden">
    <!-- Aurora Background Effect -->
    <div class="absolute inset-0 bg-mobile-aurora z-0 pointer-events-none opacity-40"></div>

    <div class="relative z-10 px-4 pt-6 pb-8 space-y-6 max-w-5xl mx-auto">
      
      <!-- Header Area -->
      <header class="glass-panel-light p-6 rounded-3xl border border-slate-700/50 relative overflow-hidden">
        <div class="absolute -right-10 -top-10 w-40 h-40 bg-purple-500/20 blur-3xl rounded-full"></div>
        
        <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between relative z-10">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <svg class="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
              <h1 class="text-2xl font-bold tracking-tight text-white">Performance Metrics</h1>
            </div>
            <p class="text-[13px] text-slate-400 font-medium">Monitor your agent's impact and usage.</p>
          </div>
          
          <div class="flex items-center gap-3 bg-slate-900/50 p-1.5 rounded-2xl border border-slate-700/50">
            <select
              v-model.number="windowHours"
              class="bg-transparent text-white text-sm font-semibold pl-3 pr-8 py-2 outline-none appearance-none cursor-pointer"
              @change="loadAnalytics"
            >
              <option :value="6" class="bg-onyx">Last 6 Hours</option>
              <option :value="24" class="bg-onyx">Last 24 Hours</option>
              <option :value="72" class="bg-onyx">Last 3 Days</option>
              <option :value="168" class="bg-onyx">Last 7 Days</option>
            </select>
            <button
              class="h-9 w-9 flex items-center justify-center rounded-xl bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors active:scale-95 border border-slate-600/50 shrink-0"
              @click="loadAnalytics"
            >
              <svg class="w-4 h-4" :class="{'animate-spin text-purple-400': isLoading}" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            </button>
          </div>
        </div>
      </header>

      <div v-if="error" class="glass-panel border-red-500/30 text-red-200 bg-red-500/10 rounded-2xl px-5 py-4 text-sm font-medium flex items-center gap-3">
         <svg class="w-5 h-5 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        {{ error }}
      </div>

      <!-- Key KPI Cards -->
      <section v-if="!isLoading && summary" class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-for="(stat, idx) in stats" :key="stat.label" 
             class="glass-panel p-5 rounded-3xl border border-slate-700/50 relative overflow-hidden group">
          <div class="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div class="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2">{{ stat.label }}</div>
          <div class="text-3xl font-black text-white tracking-tight" :class="{'text-purple-400': idx === 0, 'text-emerald-400': idx === 2}">
             {{ stat.value }}
          </div>
        </div>
      </section>

      <!-- Shimmer loading state -->
      <section v-if="isLoading" class="grid grid-cols-2 md:grid-cols-4 gap-4">
         <div v-for="i in 4" :key="i" class="glass-panel h-28 rounded-3xl border border-slate-700/30 animate-pulse bg-slate-800/20"></div>
      </section>

      <!-- Investment & Usage (LLM Cost) -->
      <section v-if="summary?.llm_cost_window && !isLoading" class="space-y-4">
        <h2 class="text-sm font-bold uppercase tracking-widest text-slate-400 ml-2">Operation Cost</h2>
        
        <div class="glass-panel p-1 rounded-3xl border border-slate-700/50">
          <!-- Overview row -->
          <div class="grid grid-cols-2 gap-px bg-slate-700/30 rounded-[22px] overflow-hidden">
             <div class="bg-slate-900/80 p-5 flex flex-col justify-center">
               <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Total Inv.</span>
               <span class="text-2xl font-black text-white">{{ formatUsd(summary.llm_cost_window.total_cost_usd, 4) }}</span>
             </div>
             <div class="bg-slate-900/80 p-5 flex flex-col justify-center">
               <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Tokens Used</span>
               <span class="text-2xl font-black text-white">{{ formatNumber(summary.llm_cost_window.total_tokens) }}</span>
             </div>
          </div>

          <!-- detailed breakdown per model (Mobile friendly vertical list) -->
          <div class="p-4" v-if="summary.llm_cost_window.models && summary.llm_cost_window.models.length > 0">
            <p class="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-3 px-2">Model Breakdown</p>
            <div class="space-y-2">
               <div v-for="row in summary.llm_cost_window.models" :key="row.model" class="bg-slate-800/40 border border-slate-700/30 rounded-2xl p-4 flex flex-col gap-2">
                 <div class="flex justify-between items-center">
                   <span class="font-bold text-sm text-white">{{ row.model }}</span>
                   <span class="text-xs font-semibold text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full">{{ formatUsd(row.total_cost_usd, 4) }}</span>
                 </div>
                 <div class="flex items-center gap-4 text-xs text-slate-400">
                    <span class="flex items-center gap-1">
                      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                      {{ formatNumber(row.message_count) }} msgs
                    </span>
                    <span class="flex items-center gap-1">
                      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                      {{ formatNumber(row.total_tokens) }} tkns
                    </span>
                 </div>
               </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Security / System Events (Vertical Cards) -->
      <section v-if="!isLoading" class="space-y-4 pt-4">
        <div class="flex items-center justify-between ml-2">
          <h2 class="text-sm font-bold uppercase tracking-widest text-slate-400">System Activity</h2>
          <span v-if="events.length" class="text-[10px] font-bold uppercase tracking-widest text-purple-400 bg-purple-400/10 px-2 py-1 rounded-full">{{ events.length }} events</span>
        </div>

        <div v-if="events.length === 0" class="glass-panel p-8 rounded-3xl border border-slate-700/50 text-center">
           <svg class="w-10 h-10 text-slate-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
           <p class="text-sm font-medium text-slate-400">No unusual activity detected.</p>
        </div>

        <div v-else class="space-y-3">
          <div v-for="evt in events" :key="evt.id" class="glass-panel p-4 rounded-2xl border border-slate-700/50 flex gap-4 overflow-hidden relative">
            <!-- decorative status line -->
            <div class="absolute left-0 top-0 bottom-0 w-1" :class="evt.status_code >= 400 ? 'bg-red-500' : 'bg-emerald-500'"></div>
            
            <div class="flex-grow min-w-0 pl-1">
               <div class="flex justify-between items-start mb-1">
                 <span class="text-xs font-bold text-white uppercase tracking-wider">{{ evt.method }}</span>
                 <span class="text-[10px] text-slate-500">{{ formatTs(evt.created_at) }}</span>
               </div>
               <p class="text-[13px] text-slate-300 font-mono truncate mb-2 opacity-80">{{ evt.endpoint }}</p>
               <div class="flex items-center gap-2">
                 <span class="text-[10px] font-bold px-2 py-0.5 rounded-md" :class="evt.status_code >= 400 ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'">
                   {{ evt.status_code }}
                 </span>
                 <span class="text-xs text-slate-400 truncate">{{ evt.reason || 'No specific reason provided' }}</span>
               </div>
            </div>
          </div>
        </div>
      </section>

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
  if (!summary.value) return [
    { label: 'Conversations', value: '0' },
    { label: 'Agents Online', value: '0' },
    { label: 'Total Leads', value: '0' },
    { label: 'Blocks', value: '0' }
  ]
  
  return [
    { label: 'Conversations', value: summary.value.conversation_count || summary.value.lead_count || 0 },
    { label: 'Agents Online', value: summary.value.agent_count || 0 },
    { label: 'Total Leads', value: summary.value.lead_count || 0 },
    { label: 'Policy Blocks', value: summary.value.policy_blocks_window || 0 }
  ]
})

function formatTs(value) {
  try {
    const d = new Date(value)
    // Mobile friendly short time
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  } catch {
    return value
  }
}

function formatUsd(value, digits = 4) {
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
      fetch(`${API_BASE}/security-events?window_hours=${windowHours.value}&limit=10`)
    ])

    if (!summaryRes.ok) {
        throw new Error('Failed to load summary stats')
    }
    summary.value = await summaryRes.json()

    if (eventsRes.ok) {
        events.value = await eventsRes.json()
    } else {
        events.value = [] // Non fatal
    }
    
  } catch (e) {
    error.value = e?.message || 'Failed to load performance metrics.'
    summary.value = null
    events.value = []
  } finally {
    isLoading.value = false
  }
}

onMounted(loadAnalytics)
</script>
