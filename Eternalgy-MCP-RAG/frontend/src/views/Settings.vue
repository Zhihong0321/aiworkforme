<script setup>
import { computed, onMounted, ref } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import { useTheme } from '../composables/theme'

const API_BASE = `${window.location.origin}/api/v1`

const apiKey = ref('')
const maskedKey = ref('')
const status = ref('unknown')
const message = ref('')
const isSaving = ref(false)
const isLoading = ref(true)

const statusVariant = () => (status.value === 'set' ? 'success' : 'warning')

const { theme, toggleTheme, setTheme } = useTheme()
const themeLabel = computed(() => (theme.value === 'dark' ? 'Dark' : 'Light'))
const nextThemeLabel = computed(() => (theme.value === 'dark' ? 'Light' : 'Dark'))

const fetchStatus = async () => {
  isLoading.value = true
  message.value = ''
  try {
    const res = await fetch(`${API_BASE}/settings/zai-key`)
    if (!res.ok) throw new Error('Failed to fetch key status')
    const data = await res.json()
    status.value = data.status || 'unknown'
    maskedKey.value = data.masked_key || ''
  } catch (error) {
    console.error('Failed to load key status', error)
    status.value = 'error'
    message.value = 'Failed to load key status.'
  } finally {
    isLoading.value = false
  }
}

const saveKey = async () => {
  if (!apiKey.value) {
    message.value = 'Enter an API key before saving.'
    return
  }
  isSaving.value = true
  message.value = ''
  try {
    const res = await fetch(`${API_BASE}/settings/zai-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey.value })
    })
    if (!res.ok) throw new Error('Failed to update key')
    message.value = 'System API Key Updated'
    apiKey.value = ''
    await fetchStatus()
  } catch (error) {
    console.error('Failed to update key', error)
    message.value = 'Update failed. Check backend connectivity.'
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
            <p class="text-xs uppercase tracking-[0.32em] text-slate-500">z.ai admin</p>
            <h1 class="text-3xl font-bold text-slate-900">Settings</h1>
            <p class="text-sm text-slate-600">
              Manage frontend-managed secrets. API key stored locally until backend integration is finalized.
            </p>
            <div class="flex flex-wrap items-center gap-2">
              <TuiBadge variant="info">placeholder</TuiBadge>
              <TuiBadge variant="muted">frontend storage</TuiBadge>
            </div>
          </div>
          <div class="flex flex-wrap gap-2 text-xs text-slate-700">
            <TuiBadge variant="muted">Z.ai API</TuiBadge>
          </div>
        </div>
      </header>

      <TuiCard title="Appearance" subtitle="theme">
        <div class="space-y-3">
          <div class="flex flex-wrap items-center gap-3">
            <TuiBadge :variant="theme === 'dark' ? 'success' : 'muted'">Theme: {{ themeLabel }}</TuiBadge>
            <TuiButton @click="toggleTheme">Switch to {{ nextThemeLabel }}</TuiButton>
            <TuiButton size="sm" variant="outline" @click="setTheme('light')">Light</TuiButton>
            <TuiButton size="sm" variant="outline" @click="setTheme('dark')">Dark</TuiButton>
          </div>
          <p class="text-xs text-slate-600">
            Applies instantly and persists locally on this device.
          </p>
        </div>
      </TuiCard>

      <TuiCard title="Z.ai API Key" subtitle="credentials">
        <div class="space-y-4">
          <div class="flex flex-wrap items-center gap-2">
            <TuiBadge :variant="statusVariant()">
              {{ status === 'set' ? 'Connected' : status === 'error' ? 'Error' : 'Missing' }}
            </TuiBadge>
            <TuiBadge variant="muted" v-if="maskedKey">masked: {{ maskedKey }}</TuiBadge>
            <TuiBadge variant="muted" v-if="isLoading">loading...</TuiBadge>
          </div>
          <TuiInput
            label="API Key"
            placeholder="Enter Z.ai API key"
            v-model="apiKey"
            type="password"
          />
          <p class="text-xs text-slate-600">
            On save, POSTs to /api/v1/settings/zai-key. When set, backend serves a masked value via GET /settings/zai-key.
          </p>
          <div class="flex flex-wrap gap-3">
            <TuiButton :loading="isSaving" @click="saveKey">Save</TuiButton>
            <TuiButton variant="outline" @click="fetchStatus">Refresh</TuiButton>
          </div>
          <p v-if="message" class="text-xs text-slate-700">{{ message }}</p>
        </div>
      </TuiCard>
    </main>
  </div>
</template>
