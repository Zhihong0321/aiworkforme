<template>
  <div class="min-h-[calc(100vh-64px)] w-full bg-onyx font-inter text-slate-200 pb-20 relative overflow-hidden flex flex-col">
    <!-- Aurora Background Effect -->
    <div class="absolute inset-0 bg-mobile-aurora z-0 pointer-events-none opacity-40"></div>

    <!-- Header Section -->
    <div class="p-5 border-b border-slate-800/50 glass-panel-light rounded-b-[2rem] sticky top-0 z-30 mb-4 relative">
       <div class="flex items-center gap-3 mb-2">
         <div class="w-10 h-10 rounded-xl bg-green-500/20 flex items-center justify-center border border-green-500/30 text-green-400 shrink-0">
             <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
         </div>
         <div>
           <h1 class="text-2xl font-bold text-white tracking-tight leading-none">Channel Setup</h1>
           <p class="text-[10px] text-aurora font-bold uppercase tracking-widest mt-1">Messaging Connectivity</p>
         </div>
       </div>
    </div>

    <!-- Main Content Area -->
    <main class="flex-grow px-4 pb-10 relative z-10 w-full max-w-2xl mx-auto space-y-6">

      <!-- Status Banner -->
      <div v-if="message" class="glass-panel p-4 rounded-2xl border border-indigo-500/30 bg-indigo-500/10 flex items-center justify-center gap-2">
         <div class="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></div>
         <p class="text-xs font-bold text-indigo-300 tracking-wide">{{ message }}</p>
      </div>

      <!-- Main Config Card -->
      <div class="glass-panel rounded-3xl border border-slate-700/50 p-1 overflow-hidden relative">
         <div class="bg-slate-900/60 p-5 rounded-[1.35rem]">
            
            <div class="flex items-center justify-between mb-6">
               <h2 class="text-sm font-black uppercase tracking-widest text-white">WhatsApp Config</h2>
               <div v-if="waLoading" class="w-4 h-4 border-2 border-slate-500 border-t-white rounded-full animate-spin"></div>
            </div>

            <!-- Inputs -->
            <div class="space-y-4 mb-6">
               <div class="space-y-1.5">
                  <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Session Key</label>
                  <input v-model="waSessionKey" type="text" placeholder="e.g. primary" class="w-full bg-slate-800/80 border border-slate-700/50 rounded-2xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors" />
               </div>
               <div class="space-y-1.5">
                  <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Display Name</label>
                  <input v-model="waDisplayName" type="text" placeholder="e.g. Primary WhatsApp" class="w-full bg-slate-800/80 border border-slate-700/50 rounded-2xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors" />
               </div>
            </div>

            <!-- Session Selector & Status Display -->
            <div class="bg-slate-800/50 rounded-2xl p-4 border border-slate-700/50 mb-6 relative overflow-hidden">
               <div class="absolute left-0 top-0 bottom-0 w-1" :class="(waQrStatus && ['connected', 'active', 'live', 'ready'].includes(waQrStatus.toLowerCase())) ? 'bg-green-500' : 'bg-amber-500'"></div>
               
               <div class="flex items-center justify-between mb-3 pl-2">
                  <span class="text-xs font-bold text-slate-400">Current Session</span>
                  <div class="px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-widest"
                       :class="(waQrStatus && ['connected', 'active', 'live', 'ready'].includes(waQrStatus.toLowerCase())) ? 'bg-green-500/20 text-green-400' : 'bg-amber-500/20 text-amber-400'">
                     {{ waQrStatus || 'Unknown' }}
                  </div>
               </div>

               <div class="relative pl-2">
                  <select
                     v-model="waSelectedSessionId"
                     class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-4 py-3 text-sm font-semibold text-white focus:outline-none focus:border-purple-500 transition-colors appearance-none"
                  >
                     <option :value="null" disabled>Select saved session</option>
                     <option v-for="s in waSessions" :key="s.id" :value="s.id">
                        {{ s.session_identifier }} ({{ s.status }})
                     </option>
                  </select>
                  <div class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                     <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                  </div>
               </div>
            </div>

            <!-- QR Code Display -->
            <div v-if="waQrImage" class="glass-panel rounded-2xl border border-blue-500/30 p-5 flex flex-col items-center justify-center text-center space-y-4 mb-6 shadow-[0_0_30px_rgba(59,130,246,0.15)] relative overflow-hidden">
               <div class="absolute inset-0 bg-blue-500/5 pointer-events-none"></div>
               <div class="relative z-10 w-full max-w-[200px] aspect-square bg-white rounded-xl p-3 flex items-center justify-center border-4 border-slate-800">
                  <img :src="waQrImage" alt="WhatsApp QR" class="w-full h-full object-contain mix-blend-multiply" />
               </div>
               <div class="relative z-10">
                  <h3 class="text-sm font-bold text-white tracking-tight">Scan to Connect</h3>
                  <p class="text-xs text-slate-400 mt-1">Open WhatsApp on your phone and link device.</p>
               </div>
            </div>

            <!-- Action Buttons (Grid layout for mobile) -->
            <div class="grid grid-cols-2 gap-3">
               <button 
                  @click="connectWhatsApp" 
                  :disabled="waConnectLoading"
                  class="col-span-2 py-3.5 bg-aurora-gradient text-white rounded-xl font-bold text-sm shadow-lg shadow-purple-500/20 active:scale-[0.98] transition-transform disabled:opacity-50 flex items-center justify-center gap-2"
               >
                  <span v-if="!waConnectLoading">Initialize / Link</span>
                  <div v-else class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
               </button>
               
               <button 
                  @click="refreshWhatsAppSession" 
                  :disabled="!waSelectedSessionId || waQrLoading"
                  class="py-3 bg-slate-800 border border-slate-700 text-slate-300 rounded-xl font-semibold text-xs active:scale-95 transition-transform disabled:opacity-50 flex items-center justify-center gap-1.5"
               >
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                  Refresh
               </button>
               
               <button 
                  @click="fetchWhatsAppQr" 
                  :disabled="!waSelectedSessionId || waQrLoading"
                  class="py-3 bg-slate-800 border border-slate-700 text-slate-300 rounded-xl font-semibold text-xs active:scale-95 transition-transform disabled:opacity-50 flex items-center justify-center gap-1.5"
               >
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                  Get QR
               </button>

               <button 
                  @click="disconnectWhatsApp" 
                  :disabled="!waSelectedSessionId"
                  class="col-span-2 py-3 mt-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl font-bold uppercase tracking-widest text-[10px] active:scale-[0.98] transition-transform disabled:opacity-50 flex items-center justify-center gap-2"
               >
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" /></svg>
                  Disconnect Session
               </button>
            </div>

         </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
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
