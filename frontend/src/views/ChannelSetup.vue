<script setup>
import { onMounted, ref } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import { request } from '../services/api'

const message = ref('')
const waSessions = ref([])
const waLoading = ref(false)
const waConnectLoading = ref(false)
const waQrLoading = ref(false)
const waSessionKey = ref('primary')
const waDisplayName = ref('Primary WhatsApp')
const waSelectedSessionId = ref(null)
const waQrImage = ref('')
const waQrStatus = ref('')

const fetchWhatsAppSessions = async () => {
  waLoading.value = true
  try {
    waSessions.value = await request('/messaging/channels/whatsapp/sessions')
    if (!waSelectedSessionId.value && waSessions.value.length > 0) {
      waSelectedSessionId.value = waSessions.value[0].id
    }
  } catch (error) {
    message.value = `Load failed: ${error.message}`
    waSessions.value = []
  } finally {
    waLoading.value = false
  }
}

const connectWhatsApp = async () => {
  waConnectLoading.value = true
  message.value = 'Connecting WhatsApp session...'
  waQrImage.value = ''
  waQrStatus.value = ''
  try {
    const result = await request('/messaging/channels/whatsapp/connect', {
      method: 'POST',
      body: JSON.stringify({
        session_key: waSessionKey.value,
        display_name: waDisplayName.value
      })
    })
    waSelectedSessionId.value = result.channel_session_id
    waQrImage.value = result.remote?.qrImage || ''
    waQrStatus.value = result.remote?.status || result.status || 'initializing'
    message.value = 'Session initialized. Scan QR if shown.'
    await fetchWhatsAppSessions()
  } catch (error) {
    message.value = `Connect failed: ${error.message}`
  } finally {
    waConnectLoading.value = false
  }
}

const refreshWhatsAppSession = async () => {
  if (!waSelectedSessionId.value) return
  waQrLoading.value = true
  try {
    const result = await request(`/messaging/channels/whatsapp/${waSelectedSessionId.value}/refresh`, {
      method: 'POST'
    })
    waQrImage.value = result.remote?.qrImage || waQrImage.value
    waQrStatus.value = result.remote?.status || result.status || 'unknown'
    await fetchWhatsAppSessions()
  } catch (error) {
    message.value = `Refresh failed: ${error.message}`
  } finally {
    waQrLoading.value = false
  }
}

const fetchWhatsAppQr = async () => {
  if (!waSelectedSessionId.value) return
  waQrLoading.value = true
  try {
    const result = await request(`/messaging/channels/whatsapp/${waSelectedSessionId.value}/qr`)
    waQrImage.value = result.qrImage || ''
    waQrStatus.value = result.status || (result.qrImage ? 'qr_ready' : 'connected_or_not_ready')
  } catch (error) {
    message.value = `QR fetch failed: ${error.message}`
  } finally {
    waQrLoading.value = false
  }
}

const disconnectWhatsApp = async () => {
  if (!waSelectedSessionId.value) return
  waConnectLoading.value = true
  try {
    await request(`/messaging/channels/whatsapp/${waSelectedSessionId.value}`, {
      method: 'DELETE'
    })
    waQrImage.value = ''
    waQrStatus.value = 'disconnected'
    message.value = 'Session disconnected'
    await fetchWhatsAppSessions()
  } catch (error) {
    message.value = `Disconnect failed: ${error.message}`
  } finally {
    waConnectLoading.value = false
  }
}

onMounted(fetchWhatsAppSessions)
</script>

<template>
  <div class="relative min-h-screen">
    <main class="relative z-10 mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 lg:px-10 space-y-6">
      <header class="tui-surface rounded-3xl border border-slate-200 p-8 shadow-sm">
        <div class="space-y-2">
          <p class="text-[10px] uppercase font-black tracking-[0.32em] text-indigo-600">Messaging</p>
          <h1 class="text-3xl font-black text-slate-900 tracking-tight">Channel Setup</h1>
          <p class="text-sm text-slate-500 max-w-2xl">
            Tenant-level channel connection. Link WhatsApp session, scan QR, and keep status healthy for outbound/inbound flow.
          </p>
        </div>
      </header>

      <TuiCard title="WhatsApp Connection" subtitle="Connected through Baileys API server">
        <div class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <TuiInput v-model="waSessionKey" label="Session Key" placeholder="primary" />
            <TuiInput v-model="waDisplayName" label="Display Name" placeholder="Primary WhatsApp" />
          </div>

          <div class="flex flex-wrap gap-3">
            <TuiButton @click="connectWhatsApp" :loading="waConnectLoading">Initialize / Reconnect</TuiButton>
            <TuiButton variant="outline" @click="refreshWhatsAppSession" :loading="waQrLoading" :disabled="!waSelectedSessionId">Refresh Status</TuiButton>
            <TuiButton variant="outline" @click="fetchWhatsAppQr" :loading="waQrLoading" :disabled="!waSelectedSessionId">Fetch QR</TuiButton>
            <TuiButton variant="ghost" class="text-red-600" @click="disconnectWhatsApp" :disabled="!waSelectedSessionId">Disconnect</TuiButton>
          </div>

          <div class="rounded-xl border border-slate-200 p-3 bg-slate-50">
            <div class="flex items-center gap-2 mb-2">
              <TuiBadge :variant="waQrStatus && ['connected', 'active', 'live', 'ready'].includes(waQrStatus.toLowerCase()) ? 'success' : 'warning'">
                {{ waQrStatus || 'unknown' }}
              </TuiBadge>
              <span class="text-xs text-slate-500">Selected Session</span>
            </div>
            <select
              v-model="waSelectedSessionId"
              class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-200"
            >
              <option :value="null" disabled>Select a session</option>
              <option v-for="s in waSessions" :key="s.id" :value="s.id">
                {{ s.session_identifier }} ({{ s.status }})
              </option>
            </select>
          </div>

          <div v-if="waQrImage" class="rounded-xl border border-slate-200 p-4 bg-white">
            <p class="text-xs text-slate-500 mb-3">Scan with your tenant WhatsApp account</p>
            <img :src="waQrImage" alt="WhatsApp QR" class="w-56 h-56 object-contain border border-slate-100 rounded-lg" />
          </div>

          <p v-if="waLoading" class="text-xs text-slate-400">Loading sessions...</p>
        </div>
      </TuiCard>

      <p v-if="message" class="text-center text-sm font-bold text-indigo-600 animate-pulse">{{ message }}</p>
    </main>
  </div>
</template>
