<script setup>
import { computed, onMounted, ref } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import { useTheme } from '../composables/theme'

import { request } from '../services/api'

// ZAI Key
const zaiKey = ref('')
const zaiMasked = ref('')
const zaiStatus = ref('unknown')
const zaiLoading = ref(true)

// UniAPI Key
const uniKey = ref('')
const uniMasked = ref('')
const uniStatus = ref('unknown')
const uniLoading = ref(true)
const zaiValidationStatus = ref('unknown')
const zaiValidationDetail = ref('')
const uniValidationStatus = ref('unknown')
const uniValidationDetail = ref('')

const message = ref('')
const isSaving = ref(false)
const isValidating = ref(false)

// LLM Routing
const llmTasks = ref([])
const llmProviders = ref([])
const llmRouting = ref({})
const llmRoutingLoading = ref(true)

const { theme, toggleTheme, setTheme } = useTheme()
const themeLabel = computed(() => (theme.value === 'dark' ? 'Dark' : 'Light'))
const nextThemeLabel = computed(() => (theme.value === 'dark' ? 'Light' : 'Dark'))

const fetchStatus = async () => {
  zaiLoading.value = true
  uniLoading.value = true
  llmRoutingLoading.value = true
  try {
    const [zaiData, uniData, tasksData, providersData, routingData] = await Promise.all([
      request('/settings/zai-key'),
      request('/settings/uniapi-key'),
      request('/platform/llm/tasks'),
      request('/platform/llm/providers'),
      request('/platform/llm/routing')
    ])
    
    zaiStatus.value = zaiData.status
    zaiMasked.value = zaiData.masked_key

    uniStatus.value = uniData.status
    uniMasked.value = uniData.masked_key

    llmTasks.value = tasksData
    llmProviders.value = providersData
    llmRouting.value = routingData
    
  } catch (error) {
    console.error('Failed to load settings', error)
  } finally {
    zaiLoading.value = false
    uniLoading.value = false
    llmRoutingLoading.value = false
  }
}

const saveZai = async () => {
  if (!zaiKey.value) return
  isSaving.value = true
  message.value = 'Saving...'
  try {
    await request('/settings/zai-key', {
      method: 'POST',
      body: JSON.stringify({ api_key: zaiKey.value })
    })
    
    zaiKey.value = ''
    message.value = 'Z.ai Key Updated'
    await fetchStatus()
  } catch (e) {
    message.value = `Error: ${e.message}`
  } finally {
    isSaving.value = false
  }
}

const saveUni = async () => {
  if (!uniKey.value) return
  isSaving.value = true
  message.value = 'Saving...'
  try {
    await request('/settings/uniapi-key', {
      method: 'POST',
      body: JSON.stringify({ api_key: uniKey.value })
    })

    uniKey.value = ''
    message.value = 'UniAPI Key Updated'
    await fetchStatus()
  } catch (e) {
    message.value = `Error: ${e.message}`
  } finally {
    isSaving.value = false
  }
}

const saveRouting = async () => {
  isSaving.value = true
  message.value = 'Saving...'
  try {
    await request('/platform/llm/routing', {
      method: 'POST',
      body: JSON.stringify({ config: llmRouting.value })
    })

    message.value = 'LLM Routing Strategy Updated'
    await fetchStatus()
  } catch (e) {
    message.value = `Error: ${e.message}`
  } finally {
    isSaving.value = false
  }
}

const validateProviderKey = async (provider) => {
  isValidating.value = true
  message.value = `Validating ${provider} key...`
  try {
    const payload = {}
    if (provider === 'zai' && zaiKey.value.trim()) payload.api_key = zaiKey.value.trim()
    if (provider === 'uniapi' && uniKey.value.trim()) payload.api_key = uniKey.value.trim()
    const data = await request(`/platform/api-keys/${provider}/validate`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
    if (provider === 'zai') {
      zaiValidationStatus.value = data.status || 'unknown'
      zaiValidationDetail.value = data.detail || ''
    } else {
      uniValidationStatus.value = data.status || 'unknown'
      uniValidationDetail.value = data.detail || ''
    }
    message.value = `${provider.toUpperCase()} validation: ${data.status}`
  } catch (e) {
    if (provider === 'zai') {
      zaiValidationStatus.value = 'invalid'
      zaiValidationDetail.value = e.message || 'Validation failed'
    } else {
      uniValidationStatus.value = 'invalid'
      uniValidationDetail.value = e.message || 'Validation failed'
    }
    message.value = `Validation error: ${e.message}`
  } finally {
    isValidating.value = false
  }
}

onMounted(() => {
  fetchStatus()
})
</script>

<template>
  <div class="relative min-h-screen">
    <main class="relative z-10 mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 lg:px-10 space-y-6">
      <header class="tui-surface rounded-3xl border border-slate-200 p-8 shadow-sm">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="space-y-2">
            <p class="text-[10px] uppercase font-black tracking-[0.32em] text-indigo-600">Pillar 4</p>
            <h1 class="text-3xl font-black text-slate-900 tracking-tight">Inbound Reactive Command</h1>
            <p class="text-sm text-slate-500 max-w-xl">
              Decide how your AI teammate should react when someone reaches out. Should they take over immediately, or wait for your approval?
            </p>
          </div>
        </div>
      </header>

      <div class="grid grid-cols-1 gap-6">
        <!-- INBOUND MODE CARD -->
        <TuiCard title="Reactive Reaction Mode" subtitle="Set the guardrails for inbound leads">
          <div class="space-y-6">
            <div class="flex items-center justify-between p-4 rounded-2xl border border-indigo-100 bg-indigo-50/50">
               <div>
                  <p class="text-xs font-black uppercase tracking-widest text-indigo-600 mb-1">Manual Approval</p>
                  <p class="text-[11px] text-slate-500">I want to review every message before it goes out.</p>
               </div>
               <div class="w-12 h-6 bg-slate-200 rounded-full relative cursor-not-allowed">
                  <div class="absolute left-1 top-1 w-4 h-4 bg-white rounded-full shadow-sm"></div>
               </div>
            </div>

            <div class="flex items-center justify-between p-4 rounded-2xl border border-green-100 bg-green-50/50">
               <div>
                  <p class="text-xs font-black uppercase tracking-widest text-green-600 mb-1">Fully Autonomous</p>
                  <p class="text-[11px] text-slate-500">The Teammate can talk to new customers 24/7 without asking me.</p>
               </div>
               <div class="w-12 h-6 bg-green-500 rounded-full relative cursor-pointer">
                  <div class="absolute right-1 top-1 w-4 h-4 bg-white rounded-full shadow-sm"></div>
               </div>
            </div>

            <div class="pt-4 border-t border-slate-100">
               <label class="text-[10px] font-black uppercase tracking-widest text-slate-400 block mb-2">Assigned Inbound Teammate</label>
               <select class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 transition-all outline-none">
                  <option>AI Teammate (Primary)</option>
               </select>
               <p class="text-[10px] text-slate-400 mt-2 italic">Who should handle new people reaching out?</p>
            </div>
          </div>
        </TuiCard>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Z.AI CARD -->
        <TuiCard title="Z.ai (Primary)" subtitle="used for AI Coding & Agent turns">
          <div class="space-y-4">
            <div class="flex items-center gap-2">
              <TuiBadge :variant="zaiStatus === 'set' ? 'success' : 'warning'">
                {{ zaiStatus === 'set' ? 'Connected' : 'Missing' }}
              </TuiBadge>
              <span v-if="zaiMasked" class="text-[10px] text-slate-400 font-mono">{{ zaiMasked }}</span>
            </div>
            <TuiInput v-model="zaiKey" type="password" placeholder="sk-..." label="API Key" />
            <TuiButton @click="saveZai" :loading="isSaving" class="w-full">Update Z.ai Key</TuiButton>
            <TuiButton @click="validateProviderKey('zai')" :loading="isValidating" variant="outline" class="w-full">Validate Z.ai Key</TuiButton>
            <p v-if="zaiValidationStatus !== 'unknown'" class="text-[11px] font-semibold" :class="zaiValidationStatus === 'valid' ? 'text-emerald-700' : zaiValidationStatus === 'not_set' ? 'text-amber-700' : 'text-red-700'">
              {{ zaiValidationStatus.toUpperCase() }}: {{ zaiValidationDetail }}
            </p>
          </div>
        </TuiCard>

        <!-- UNIAPI CARD -->
        <TuiCard title="UniAPI (Fallback)" subtitle="targeting Google Gemini models">
          <div class="space-y-4">
            <div class="flex items-center gap-2">
              <TuiBadge :variant="uniStatus === 'set' ? 'success' : 'warning'">
                {{ uniStatus === 'set' ? 'Connected' : 'Missing' }}
              </TuiBadge>
              <span v-if="uniMasked" class="text-[10px] text-slate-400 font-mono">{{ uniMasked }}</span>
            </div>
            <TuiInput v-model="uniKey" type="password" placeholder="Key..." label="UniAPI Key" />
            <TuiButton @click="saveUni" :loading="isSaving" variant="outline" class="w-full">Update UniAPI Key</TuiButton>
            <TuiButton @click="validateProviderKey('uniapi')" :loading="isValidating" variant="outline" class="w-full">Validate UniAPI Key</TuiButton>
            <p v-if="uniValidationStatus !== 'unknown'" class="text-[11px] font-semibold" :class="uniValidationStatus === 'valid' ? 'text-emerald-700' : uniValidationStatus === 'not_set' ? 'text-amber-700' : 'text-red-700'">
              {{ uniValidationStatus.toUpperCase() }}: {{ uniValidationDetail }}
            </p>
          </div>
        </TuiCard>
      </div>

      <!-- LLM ROUTING CARD -->
      <TuiCard title="LLM Routing Strategy" subtitle="Control which provider handles specific tasks">
        <div v-if="llmRoutingLoading" class="text-sm text-slate-500 py-4">Loading strategy...</div>
        <div v-else class="space-y-6">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div v-for="task in llmTasks" :key="task" class="space-y-2">
              <label class="text-xs font-bold uppercase tracking-wider text-slate-700 block">{{ task }}</label>
              <select 
                v-model="llmRouting[task]"
                class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-200"
              >
                <option v-for="provider in llmProviders" :key="provider" :value="provider">
                  {{ provider }}
                </option>
              </select>
            </div>
          </div>
          <div class="pt-4 border-t border-slate-100 flex justify-end">
            <TuiButton @click="saveRouting" :loading="isSaving" size="sm">Save Routing Strategy</TuiButton>
          </div>
        </div>
      </TuiCard>

      <TuiCard title="Appearance" subtitle="Theme selection">
        <div class="flex items-center gap-4">
          <TuiButton @click="toggleTheme">{{ themeLabel }} Mode Active</TuiButton>
          <p class="text-xs text-slate-500">Persists locally on this browser.</p>
        </div>
      </TuiCard>

      <p v-if="message" class="text-center text-sm font-bold text-indigo-600 animate-pulse">{{ message }}</p>
    </main>
  </div>
</template>
