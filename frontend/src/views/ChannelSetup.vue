<template>
  <div class="flex flex-col h-[calc(100vh-64px)] w-full max-w-md mx-auto relative text-slate-900 dark:text-slate-100 bg-background-light dark:bg-background-dark overflow-hidden">
    <header class="p-6 border-b border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md sticky top-0 z-30 shrink-0">
      <div class="flex items-center gap-4">
        <div class="size-12 rounded-2xl bg-green-500/15 flex items-center justify-center text-green-600 border border-green-500/20 shadow-sm">
          <span class="material-symbols-outlined text-2xl">qr_code_2</span>
        </div>

        <div class="flex flex-col text-left">
          <h2 class="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Channel Onboarding</h2>
          <p class="text-[11px] text-green-600 font-bold uppercase tracking-widest mt-1">WhatsApp Setup Flow</p>
        </div>
      </div>
    </header>

    <main class="flex-1 overflow-y-auto p-4 md:p-6 pb-24 scroll-smooth scrollbar-none relative space-y-5">
      <div v-if="message" class="bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-emerald-800 dark:text-emerald-200 shadow-sm p-4 rounded-2xl flex items-start gap-3 animate-in slide-in-from-top duration-300">
        <span class="material-symbols-outlined text-[18px] mt-0.5">info</span>
        <p class="text-sm font-semibold tracking-wide flex-1">{{ message }}</p>
        <button @click="message = ''" class="text-emerald-500 hover:text-emerald-700 dark:hover:text-emerald-100">
          <span class="material-symbols-outlined text-sm">close</span>
        </button>
      </div>

      <section class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm rounded-3xl p-6 overflow-hidden relative">
        <div class="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-500 via-lime-400 to-teal-500"></div>
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="text-[10px] uppercase tracking-[0.35em] font-black text-slate-400 dark:text-slate-500">Setup Goal</p>
            <h3 class="text-xl font-bold text-slate-900 dark:text-white mt-2">Connect once, then use the WhatsApp number as the channel identity.</h3>
            <p class="text-sm text-slate-500 dark:text-slate-400 mt-2 leading-relaxed">
              The internal key is only for Baileys. Once the device is linked, this app will promote the real WhatsApp number to the channel ID and keep your typed label as the description.
            </p>
          </div>
          <div class="rounded-2xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 px-3 py-2 text-right min-w-[110px]">
            <p class="text-[10px] uppercase tracking-[0.25em] font-bold text-slate-400 dark:text-slate-500">Current State</p>
            <p class="mt-2 text-sm font-bold" :class="statusToneClass(activeStatus)">
              {{ statusHeadline }}
            </p>
          </div>
        </div>

        <button
          @click="startNewChannelFlow"
          class="mt-5 inline-flex items-center gap-2 rounded-2xl border border-primary/20 bg-primary/10 px-4 py-2 text-[11px] font-black uppercase tracking-[0.25em] text-primary transition-colors hover:bg-primary/15"
        >
          <span class="material-symbols-outlined text-[16px]">add_circle</span>
          Add New Channel
        </button>

        <div class="grid grid-cols-3 gap-3 mt-6">
          <div v-for="step in onboardingSteps" :key="step.id" class="rounded-2xl border px-3 py-4 transition-colors" :class="stepCardClass(step.state)">
            <p class="text-[10px] uppercase tracking-[0.25em] font-black">{{ step.eyebrow }}</p>
            <p class="mt-2 text-sm font-bold leading-snug">{{ step.title }}</p>
            <p class="mt-1 text-[11px] leading-relaxed opacity-80">{{ step.caption }}</p>
          </div>
        </div>
      </section>

      <section ref="setupFormSection" class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm rounded-3xl p-6">
        <div class="flex items-start justify-between gap-4 mb-6">
          <div>
            <p class="text-[10px] uppercase tracking-[0.35em] font-black text-slate-400 dark:text-slate-500">Step 1</p>
            <h3 class="text-lg font-bold text-slate-900 dark:text-white mt-2">Add a new channel profile</h3>
            <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">Each submit creates a new WhatsApp channel. After connection, the WhatsApp number becomes the channel ID shown across the app.</p>
          </div>
          <div v-if="waConnectLoading" class="w-5 h-5 border-2 border-slate-300 dark:border-slate-600 border-t-primary rounded-full animate-spin shrink-0 mt-1"></div>
        </div>

        <div class="space-y-4">
          <div class="space-y-1.5">
            <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 dark:text-slate-400 pl-1">Internal Connection Key</label>
            <input
              v-model="waSessionKey"
              type="text"
              placeholder="e.g. primary"
              class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-3 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow"
            />
            <p class="text-[11px] text-slate-500 dark:text-slate-400 pl-1">This only helps the provider create the connection. It is not the long-term channel identity.</p>
          </div>

          <div class="space-y-1.5">
            <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 dark:text-slate-400 pl-1">Description</label>
            <input
              v-model="waDescription"
              type="text"
              placeholder="e.g. Primary Sales Number"
              class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-3 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow"
            />
          </div>
        </div>

        <div class="mt-4 rounded-2xl border border-primary/15 bg-primary/5 px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
          Use a fresh internal connection key for each number, then click <span class="font-bold text-slate-900 dark:text-white">Add New WhatsApp Channel</span>.
        </div>

        <button
          @click="connectWhatsApp"
          :disabled="waConnectLoading"
          class="mt-6 w-full py-3.5 bg-primary text-white shadow-lg hover:bg-primary/90 hover:shadow-primary/30 rounded-2xl font-bold text-sm active:scale-[0.98] transition-all disabled:opacity-50 disabled:grayscale flex items-center justify-center gap-2"
        >
          <span v-if="!waConnectLoading" class="flex items-center gap-2">
            <span class="material-symbols-outlined text-[18px]">add_link</span>
            Add New WhatsApp Channel
          </span>
          <div v-else class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
        </button>
      </section>

      <section class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm rounded-3xl p-6">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="text-[10px] uppercase tracking-[0.35em] font-black text-slate-400 dark:text-slate-500">Live Session</p>
            <h3 class="text-lg font-bold text-slate-900 dark:text-white mt-2">
              {{ activeSession ? "Current onboarding state" : "No session selected" }}
            </h3>
            <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {{ activeSession ? sessionSupportText : "Select an existing channel below or start a new onboarding flow." }}
            </p>
          </div>

          <div v-if="waPolling" class="rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 px-3 py-1 text-[10px] font-black uppercase tracking-[0.25em]">
            Auto Checking
          </div>
        </div>

        <div v-if="activeSession" class="mt-6 space-y-4">
          <div class="rounded-[28px] border border-slate-200 dark:border-slate-700 bg-slate-50/90 dark:bg-slate-900/80 p-5">
            <div class="flex items-start justify-between gap-4">
              <div>
                <p class="text-[10px] uppercase tracking-[0.3em] font-black text-slate-400 dark:text-slate-500">Channel ID</p>
                <h4 class="mt-2 text-2xl font-black tracking-tight text-slate-900 dark:text-white break-all">{{ activeSessionIdentity }}</h4>
                <p class="mt-2 text-sm text-slate-500 dark:text-slate-400">
                  {{ activeSessionDescription || "No description saved yet." }}
                </p>
              </div>
              <div class="rounded-2xl px-3 py-2 text-right border" :class="statusBadgeClass(activeStatus)">
                <p class="text-[10px] uppercase tracking-[0.25em] font-black">Status</p>
                <p class="mt-1 text-sm font-bold">{{ activeStatusLabel }}</p>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3 mt-5">
              <div class="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-4 py-3">
                <p class="text-[10px] uppercase tracking-[0.25em] font-black text-slate-400 dark:text-slate-500">Provider Session</p>
                <p class="mt-2 text-sm font-bold text-slate-700 dark:text-slate-200 break-all">
                  {{ activeProviderSessionId }}
                </p>
              </div>
              <div class="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-4 py-3">
                <p class="text-[10px] uppercase tracking-[0.25em] font-black text-slate-400 dark:text-slate-500">Last Sync</p>
                <p class="mt-2 text-sm font-bold text-slate-700 dark:text-slate-200">
                  {{ activeLastSync }}
                </p>
              </div>
            </div>
          </div>

          <div
            v-if="waQrImage && !isConnectedStatus(waQrStatus)"
            class="rounded-[28px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 flex flex-col items-center text-center"
          >
            <div class="rounded-[24px] bg-white p-4 border-[6px] border-slate-100 shadow-md">
              <img :src="waQrImage" alt="WhatsApp QR Code" class="w-[220px] h-[220px] object-contain" />
            </div>
            <h4 class="mt-5 text-base font-bold text-slate-900 dark:text-white">Scan QR with WhatsApp</h4>
            <p class="mt-2 text-sm text-slate-500 dark:text-slate-400 max-w-[240px] leading-relaxed">
              Open Linked Devices in WhatsApp, scan this QR code, and keep this screen open while we confirm the connected number.
            </p>
          </div>

          <div
            v-else-if="isConnectedStatus(activeStatus)"
            class="rounded-[28px] border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-900/10 p-5"
          >
            <div class="flex items-start gap-4">
              <div class="size-14 rounded-2xl bg-emerald-500/15 flex items-center justify-center text-emerald-600 dark:text-emerald-300">
                <span class="material-symbols-outlined text-3xl">check_circle</span>
              </div>
              <div>
                <h4 class="text-base font-bold text-slate-900 dark:text-white">Connected and identity captured</h4>
                <p class="mt-1 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                  This channel is now keyed by <span class="font-bold">{{ activeSessionIdentity }}</span> inside the app. The internal provider session remains available only for backend calls.
                </p>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <button
              @click="refreshWhatsAppSession"
              :disabled="!waSelectedSessionId || waQrLoading"
              class="py-3 bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-2xl font-bold text-[11px] uppercase tracking-[0.25em] active:scale-95 transition-transform disabled:opacity-50 flex items-center justify-center gap-2 hover:bg-slate-200 dark:hover:bg-slate-800"
            >
              <span class="material-symbols-outlined text-[16px]">sync</span>
              Refresh Status
            </button>

            <button
              @click="fetchWhatsAppQr"
              :disabled="!waSelectedSessionId || waQrLoading"
              class="py-3 bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-2xl font-bold text-[11px] uppercase tracking-[0.25em] active:scale-95 transition-transform disabled:opacity-50 flex items-center justify-center gap-2 hover:bg-slate-200 dark:hover:bg-slate-800"
            >
              <span class="material-symbols-outlined text-[16px]">qr_code</span>
              Load QR
            </button>

            <button
              @click="disconnectWhatsApp"
              :disabled="!waSelectedSessionId"
              class="col-span-2 py-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-600 dark:text-red-400 rounded-2xl font-bold text-[11px] uppercase tracking-[0.25em] active:scale-[0.98] transition-transform disabled:opacity-50 flex items-center justify-center gap-2 hover:bg-red-100 dark:hover:bg-red-500/20"
            >
              <span class="material-symbols-outlined text-[14px]">link_off</span>
              Disconnect Channel
            </button>
          </div>
        </div>
      </section>

      <section class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm rounded-3xl p-6">
        <div class="flex items-start justify-between gap-4 mb-5">
          <div>
            <p class="text-[10px] uppercase tracking-[0.35em] font-black text-slate-400 dark:text-slate-500">Saved Channels</p>
            <h3 class="text-lg font-bold text-slate-900 dark:text-white mt-2">Use the real WhatsApp number as the channel ID</h3>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="startNewChannelFlow"
              class="rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.25em] text-primary transition-colors hover:bg-primary/15"
            >
              Add New
            </button>
            <button
              @click="fetchWhatsAppSessions"
              :disabled="waLoading"
              class="rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.25em] text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
            >
              Reload
            </button>
          </div>
        </div>

        <div v-if="waSessions.length === 0" class="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
          No WhatsApp channels saved yet.
        </div>

        <div v-else class="space-y-3">
          <button
            v-for="session in orderedSessions"
            :key="session.id"
            @click="selectSession(session)"
            class="w-full text-left rounded-[24px] border px-4 py-4 transition-all"
            :class="sessionCardClass(session)"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="min-w-0">
                <p class="text-[10px] uppercase tracking-[0.25em] font-black text-slate-400 dark:text-slate-500">Channel ID</p>
                <p class="mt-2 text-base font-bold text-slate-900 dark:text-white break-all">{{ getSessionIdentity(session) }}</p>
                <p class="mt-2 text-sm text-slate-500 dark:text-slate-400 break-all">
                  {{ getSessionDescription(session) || "No description" }}
                </p>
              </div>
              <div class="rounded-2xl px-3 py-2 border shrink-0" :class="statusBadgeClass(session.status)">
                <p class="text-[10px] uppercase tracking-[0.25em] font-black">Status</p>
                <p class="mt-1 text-sm font-bold">{{ formatStatusLabel(session.status) }}</p>
              </div>
            </div>

            <div class="mt-4 flex flex-wrap gap-2 text-[11px] text-slate-500 dark:text-slate-400">
              <span class="rounded-full bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 px-3 py-1">
                Provider: {{ getProviderSessionId(session) }}
              </span>
              <span v-if="getConnectedNumber(session)" class="rounded-full bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 px-3 py-1 text-emerald-700 dark:text-emerald-300">
                Number captured
              </span>
            </div>
          </button>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { request } from '../services/api'

const message = ref('')
const setupFormSection = ref(null)
const waSessions = ref([])
const waLoading = ref(false)
const waConnectLoading = ref(false)
const waQrLoading = ref(false)
const waPolling = ref(false)
const waSessionKey = ref('primary')
const waDescription = ref('Primary WhatsApp')
const waSelectedSessionId = ref(null)
const waQrImage = ref('')
const waQrStatus = ref('')

let waPollTimer = null

const normalizeStatus = (status) => String(status || '').trim().toLowerCase()
const isConnectedStatus = (status) => ['connected', 'active', 'live', 'ready', 'open'].includes(normalizeStatus(status))

const getSessionDescription = (session) => session?.session_metadata?.description || ''
const getConnectedNumber = (session) => (
  session?.session_metadata?.connected_number
  || session?.session_metadata?.phone_number
  || session?.session_metadata?.phone
  || ''
)

const getProviderSessionId = (session) => (
  session?.session_metadata?.provider_session_id
  || session?.session_identifier
  || 'Unavailable'
)

const getSessionIdentity = (session) => {
  const connectedNumber = getConnectedNumber(session)
  if (connectedNumber) {
    return connectedNumber
  }

  if (/^\d{8,15}$/.test(String(session?.session_identifier || '').trim())) {
    return session.session_identifier
  }

  if (/^\d{8,15}$/.test(String(session?.display_name || '').trim())) {
    return session.display_name
  }

  return session?.display_name || session?.session_identifier || 'Pending identity'
}

const activeSession = computed(() => (
  waSessions.value.find((session) => session.id === waSelectedSessionId.value) || null
))

const activeStatus = computed(() => activeSession.value?.status || waQrStatus.value || 'disconnected')
const activeStatusLabel = computed(() => formatStatusLabel(activeStatus.value))
const activeSessionIdentity = computed(() => getSessionIdentity(activeSession.value))
const activeSessionDescription = computed(() => getSessionDescription(activeSession.value))
const activeProviderSessionId = computed(() => getProviderSessionId(activeSession.value))
const activeLastSync = computed(() => {
  const timestamp = activeSession.value?.session_metadata?.last_refresh_at || activeSession.value?.session_metadata?.last_connect_at
  if (!timestamp) {
    return 'Not synced yet'
  }
  return new Date(timestamp).toLocaleString()
})

const statusHeadline = computed(() => {
  if (!activeSession.value) {
    return 'Not Started'
  }
  if (isConnectedStatus(activeStatus.value)) {
    return 'Connected'
  }
  if (waQrImage.value) {
    return 'Waiting For Scan'
  }
  return 'In Progress'
})

const sessionSupportText = computed(() => {
  if (isConnectedStatus(activeStatus.value)) {
    return 'The connected number has been captured and is now the channel identity used in the app.'
  }
  if (waQrImage.value) {
    return 'Scan the QR code and keep this page open while we confirm the linked number.'
  }
  return 'Use refresh if you already scanned the code from another device.'
})

const onboardingSteps = computed(() => [
  {
    id: 'profile',
    eyebrow: 'Step 1',
    title: 'Create Internal Session',
    caption: 'Prepare a provider connection key and save your description.',
    state: activeSession.value ? 'done' : 'current'
  },
  {
    id: 'scan',
    eyebrow: 'Step 2',
    title: 'Scan QR Code',
    caption: 'Link the device from WhatsApp Linked Devices.',
    state: isConnectedStatus(activeStatus.value) ? 'done' : (waQrImage.value ? 'current' : (activeSession.value ? 'pending' : 'pending'))
  },
  {
    id: 'identity',
    eyebrow: 'Step 3',
    title: 'Capture Number',
    caption: 'Promote the real WhatsApp number to the app channel ID.',
    state: isConnectedStatus(activeStatus.value) ? 'done' : 'pending'
  }
])

const orderedSessions = computed(() => (
  [...waSessions.value].sort((left, right) => {
    const leftConnected = isConnectedStatus(left.status) ? 1 : 0
    const rightConnected = isConnectedStatus(right.status) ? 1 : 0
    if (leftConnected !== rightConnected) {
      return rightConnected - leftConnected
    }
    return Number(right.id || 0) - Number(left.id || 0)
  })
))

const statusToneClass = (status) => {
  if (isConnectedStatus(status)) {
    return 'text-emerald-700 dark:text-emerald-300'
  }
  if (waQrImage.value) {
    return 'text-amber-600 dark:text-amber-300'
  }
  return 'text-slate-600 dark:text-slate-300'
}

const stepCardClass = (state) => {
  if (state === 'done') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/10 dark:text-emerald-200'
  }
  if (state === 'current') {
    return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-900/10 dark:text-amber-200'
  }
  return 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'
}

const statusBadgeClass = (status) => {
  if (isConnectedStatus(status)) {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/10 dark:text-emerald-300'
  }
  return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-900/10 dark:text-amber-300'
}

const sessionCardClass = (session) => {
  const selected = session.id === waSelectedSessionId.value
  if (selected) {
    return 'border-primary/40 bg-primary/5 dark:border-primary/30 dark:bg-primary/10 shadow-sm'
  }
  if (isConnectedStatus(session.status)) {
    return 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-800 dark:bg-emerald-900/10 hover:border-emerald-300'
  }
  return 'border-slate-200 bg-slate-50/80 dark:border-slate-700 dark:bg-slate-900/70 hover:border-slate-300 dark:hover:border-slate-600'
}

const formatStatusLabel = (status) => {
  const normalized = normalizeStatus(status)
  if (!normalized) {
    return 'Disconnected'
  }
  return normalized.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

const stopWhatsAppPolling = () => {
  if (waPollTimer) {
    clearInterval(waPollTimer)
    waPollTimer = null
  }
  waPolling.value = false
}

const startWhatsAppPolling = () => {
  stopWhatsAppPolling()
  if (!waSelectedSessionId.value) {
    return
  }

  waPolling.value = true
  waPollTimer = setInterval(async () => {
    try {
      await refreshWhatsAppSession({ silent: true })
      if (!isConnectedStatus(waQrStatus.value)) {
        await fetchWhatsAppQr({ silent: true })
      }
      if (isConnectedStatus(waQrStatus.value) || isConnectedStatus(activeSession.value?.status)) {
        stopWhatsAppPolling()
        message.value = `Connected. Channel ID captured as ${getSessionIdentity(activeSession.value)}.`
      }
    } catch (error) {
      stopWhatsAppPolling()
      message.value = `Auto-check stopped: ${error.message}`
    }
  }, 4000)
}

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

const startNewChannelFlow = () => {
  waSessionKey.value = `channel-${Date.now()}`
  waDescription.value = ''
  waSelectedSessionId.value = null
  waQrImage.value = ''
  waQrStatus.value = ''
  stopWhatsAppPolling()
  message.value = 'Fill in the new channel details below, then click Add New WhatsApp Channel.'
  setupFormSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const connectWhatsApp = async () => {
  waConnectLoading.value = true
  message.value = 'Creating WhatsApp channel and requesting QR...'
  waQrImage.value = ''
  waQrStatus.value = ''
  stopWhatsAppPolling()

  try {
    const result = await request('/messaging/channels/whatsapp/connect', {
      method: 'POST',
      body: JSON.stringify({
        session_key: waSessionKey.value,
        description: waDescription.value
      })
    })

    waSelectedSessionId.value = result.channel_session_id
    waQrImage.value = result.remote?.qrImage || ''
    waQrStatus.value = result.remote?.status || result.status || 'initializing'
    await fetchWhatsAppSessions()

    if (isConnectedStatus(waQrStatus.value) || isConnectedStatus(activeSession.value?.status)) {
      message.value = `Connected. Channel ID captured as ${getSessionIdentity(activeSession.value)}.`
      stopWhatsAppPolling()
    } else {
      message.value = 'QR generated. Scan it now and the app will keep checking until the number is captured.'
      startWhatsAppPolling()
    }
  } catch (error) {
    message.value = `Connect failed: ${error.message}`
  } finally {
    waConnectLoading.value = false
  }
}

const refreshWhatsAppSession = async ({ silent = false } = {}) => {
  if (!waSelectedSessionId.value) return
  waQrLoading.value = true
  try {
    const result = await request(`/messaging/channels/whatsapp/${waSelectedSessionId.value}/refresh`, {
      method: 'POST'
    })
    waQrImage.value = result.remote?.qrImage || waQrImage.value
    waQrStatus.value = result.remote?.status || result.status || 'unknown'
    await fetchWhatsAppSessions()
    if (!silent) {
      message.value = isConnectedStatus(waQrStatus.value)
        ? `Connected. Channel ID captured as ${getSessionIdentity(activeSession.value)}.`
        : 'Channel status synchronized.'
    }
  } catch (error) {
    if (!silent) {
      message.value = `Refresh failed: ${error.message}`
    }
    throw error
  } finally {
    waQrLoading.value = false
  }
}

const fetchWhatsAppQr = async ({ silent = false } = {}) => {
  if (!waSelectedSessionId.value) return
  waQrLoading.value = true
  if (!silent) {
    message.value = ''
  }
  try {
    const result = await request(`/messaging/channels/whatsapp/${waSelectedSessionId.value}/qr`)
    waQrImage.value = result.qrImage || ''
    waQrStatus.value = result.status || (result.qrImage ? 'qr_ready' : 'connected_or_not_ready')
    await fetchWhatsAppSessions()
    if (!silent && isConnectedStatus(waQrStatus.value)) {
      message.value = `Connected. Channel ID captured as ${getSessionIdentity(activeSession.value)}.`
    }
  } catch (error) {
    if (!silent) {
      message.value = `QR fetch failed: ${error.message}`
    }
    throw error
  } finally {
    waQrLoading.value = false
  }
}

const disconnectWhatsApp = async () => {
  if (!waSelectedSessionId.value) return
  if (!confirm('Are you sure you want to disconnect this WhatsApp channel?')) return

  waConnectLoading.value = true
  stopWhatsAppPolling()
  try {
    await request(`/messaging/channels/whatsapp/${waSelectedSessionId.value}`, {
      method: 'DELETE'
    })
    waQrImage.value = ''
    waQrStatus.value = 'disconnected'
    message.value = 'Channel disconnected.'
    await fetchWhatsAppSessions()
  } catch (error) {
    message.value = `Disconnect failed: ${error.message}`
  } finally {
    waConnectLoading.value = false
  }
}

const selectSession = async (session) => {
  waSelectedSessionId.value = session.id
  waQrStatus.value = session.status || waQrStatus.value
  waQrImage.value = ''
  stopWhatsAppPolling()

  if (!isConnectedStatus(session.status)) {
    try {
      await fetchWhatsAppQr({ silent: true })
      if (!isConnectedStatus(waQrStatus.value)) {
        startWhatsAppPolling()
      }
    } catch (error) {
      message.value = `Unable to load selected session QR: ${error.message}`
    }
  }
}

onMounted(fetchWhatsAppSessions)
onBeforeUnmount(stopWhatsAppPolling)
</script>

<style scoped>
.scrollbar-none::-webkit-scrollbar {
  display: none;
}

.scrollbar-none {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
