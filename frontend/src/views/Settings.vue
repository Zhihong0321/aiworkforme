<script setup>
import { computed, onMounted, ref } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import { useTheme } from '../composables/theme'

const API_BASE = `${window.location.origin}/api/v1`

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

const message = ref('')
const isSaving = ref(false)

const { theme, toggleTheme, setTheme } = useTheme()
const themeLabel = computed(() => (theme.value === 'dark' ? 'Dark' : 'Light'))
const nextThemeLabel = computed(() => (theme.value === 'dark' ? 'Light' : 'Dark'))

const fetchStatus = async () => {
  zaiLoading.value = true
  uniLoading.value = true
  try {
    const [zaiRes, uniRes] = await Promise.all([
      fetch(`${API_BASE}/settings/zai-key`),
      fetch(`${API_BASE}/settings/uniapi-key`)
    ])
    
    const zaiData = await zaiRes.json()
    zaiStatus.value = zaiData.status
    zaiMasked.value = zaiData.masked_key

    const uniData = await uniRes.json()
    uniStatus.value = uniData.status
    uniMasked.value = uniData.masked_key
    
  } catch (error) {
    console.error('Failed to load keys', error)
  } finally {
    zaiLoading.value = false
    uniLoading.value = false
  }
}

const saveZai = async () => {
  if (!zaiKey.value) return
  isSaving.value = true
  message.value = 'Saving...'
  try {
    const res = await fetch(`${API_BASE}/settings/zai-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: zaiKey.value })
    })
    
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}))
      throw new Error(errorData.detail || 'Failed to save Z.ai key')
    }
    
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
    const res = await fetch(`${API_BASE}/settings/uniapi-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: uniKey.value })
    })
    
    if (!res.ok) {
       const errorData = await res.json().catch(() => ({}))
       throw new Error(errorData.detail || 'Failed to save UniAPI key')
    }

    uniKey.value = ''
    message.value = 'UniAPI Key Updated'
    await fetchStatus()
  } catch (e) {
    message.value = `Error: ${e.message}`
  } finally {
    isSaving.value = false
  }
}

onMounted(() => {
  fetchStatus()
})
</script>

<template>
  <div class="relative min-h-screen">
    <main class="relative z-10 mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 lg:px-10 space-y-6">
      <header class="tui-surface rounded-xl border border-slate-200 p-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="space-y-2">
            <p class="text-xs uppercase tracking-[0.32em] text-slate-500">System Admin</p>
            <h1 class="text-3xl font-bold text-slate-900">Settings</h1>
            <p class="text-sm text-slate-600">
              Configure system-wide secrets and provider credentials. 
            </p>
          </div>
          <div class="flex flex-wrap gap-2 text-xs text-slate-700">
            <TuiBadge variant="info">Production Ready</TuiBadge>
          </div>
        </div>
      </header>

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
          </div>
        </TuiCard>
      </div>

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
