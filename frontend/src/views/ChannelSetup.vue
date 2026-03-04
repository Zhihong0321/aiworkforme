<template>
  <div class="flex flex-col h-[calc(100vh-64px)] w-full max-w-md mx-auto relative text-slate-900 dark:text-slate-100 bg-background-light dark:bg-background-dark overflow-hidden">
    
    <!-- TopAppBar -->
    <header class="p-6 border-b border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md sticky top-0 z-30 shrink-0">
        <div class="flex items-center gap-4">
            <div class="size-12 rounded-2xl bg-green-500/20 flex items-center justify-center text-green-500 border border-green-500/20 shadow-sm relative overflow-hidden">
                <span class="absolute inset-0 bg-green-500/10 blur-xl"></span>
                <span class="material-symbols-outlined relative z-10 text-2xl">sensors</span>
            </div>
            
            <div class="flex flex-col text-left">
                <h2 class="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Channel Setup</h2>
                <p class="text-[11px] text-green-500 font-bold uppercase tracking-widest mt-1">Messaging Connectivity</p>
            </div>
        </div>
    </header>

    <!-- Main Content Area -->
    <main class="flex-1 overflow-y-auto p-4 md:p-6 pb-24 scroll-smooth scrollbar-none relative">
      <div v-if="message" class="bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/30 text-indigo-700 dark:text-indigo-300 shadow-sm p-4 rounded-2xl flex items-center gap-3 mb-6 animate-in slide-in-from-top duration-300">
         <span class="relative flex h-2.5 w-2.5 shrink-0">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span>
         </span>
         <p class="text-sm font-semibold tracking-wide flex-1">{{ message }}</p>
         <button @click="message = ''" class="text-indigo-400 hover:text-indigo-600 dark:hover:text-indigo-200">
            <span class="material-symbols-outlined text-sm">close</span>
         </button>
      </div>

      <!-- Main Config Card -->
      <div class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm rounded-3xl p-6 relative overflow-hidden group">
         
         <div class="flex items-center justify-between mb-8">
            <h2 class="text-xs font-black uppercase tracking-widest text-slate-500 dark:text-slate-400 flex items-center gap-2">
               <span class="material-symbols-outlined text-[16px]">forum</span>
               WhatsApp Configuration
            </h2>
            <div v-if="waLoading" class="w-4 h-4 border-2 border-slate-300 dark:border-slate-600 border-t-primary rounded-full animate-spin"></div>
         </div>

         <!-- Input Section -->
         <div class="space-y-4 mb-8">
            <div class="space-y-1.5 flex flex-col">
               <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 dark:text-slate-400 pl-1">Session Mapping Key</label>
               <input v-model="waSessionKey" type="text" placeholder="e.g. primary" class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-3 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow" />
            </div>
            <div class="space-y-1.5 flex flex-col">
               <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 dark:text-slate-400 pl-1">Display Label</label>
               <input v-model="waDisplayName" type="text" placeholder="e.g. Primary Support Number" class="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-3 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow" />
            </div>
         </div>

         <!-- Status Board -->
         <div class="bg-slate-50 dark:bg-slate-900 rounded-2xl p-5 border border-slate-200 dark:border-slate-800 mb-8 relative overflow-hidden transition-colors">
            <!-- Indicator Bar -->
            <div class="absolute left-0 top-0 bottom-0 w-1.5 transition-colors duration-500" 
                 :class="(waQrStatus && ['connected', 'active', 'live', 'ready', 'open'].includes(waQrStatus.toLowerCase())) ? 'bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.5)]' : 'bg-amber-400'">
            </div>
            
            <div class="flex items-center justify-between mb-4 pl-2">
               <span class="text-xs font-bold text-slate-600 dark:text-slate-400">Current Session State</span>
               <div class="px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest flex items-center gap-1.5 shadow-sm"
                    :class="(waQrStatus && ['connected', 'active', 'live', 'ready', 'open'].includes(waQrStatus.toLowerCase())) ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'">
                  <span v-if="(waQrStatus && ['connected', 'active', 'live', 'ready', 'open'].includes(waQrStatus.toLowerCase()))" class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  {{ waQrStatus || 'Disconnected' }}
               </div>
            </div>

            <div class="relative pl-2">
               <select
                  v-model="waSelectedSessionId"
                  @change="fetchWhatsAppQr"
                  class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm font-semibold text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow appearance-none"
               >
                  <option :value="null" disabled>Select saved session profile</option>
                  <option v-for="s in waSessions" :key="s.id" :value="s.id">
                     {{ s.display_name || s.session_identifier }} ({{ s.status }})
                  </option>
               </select>
               <div class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                  <span class="material-symbols-outlined text-[18px]">expand_more</span>
               </div>
            </div>
         </div>

         <!-- QR Container -->
         <div v-if="waQrImage && !(['connected', 'active', 'live', 'ready', 'open'].includes(waQrStatus?.toLowerCase()))" class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl p-6 flex flex-col items-center justify-center text-center space-y-4 mb-8 shadow-inner relative overflow-hidden group/qr">
            <!-- Scan Overlay Pulse -->
            <div class="absolute inset-x-0 h-1 bg-primary/30 top-0 left-0 animate-[scan_3s_ease-in-out_infinite] z-20"></div>

            <div class="relative z-10 w-full max-w-[220px] aspect-square bg-white rounded-[1.5rem] p-4 flex items-center justify-center border-[6px] border-slate-100 dark:border-slate-800 shadow-md">
               <img :src="waQrImage" alt="WhatsApp QR Code" class="w-full h-full object-contain mix-blend-multiply transition-transform duration-500 group-hover/qr:scale-105" />
            </div>
            
            <div class="relative z-10 flex flex-col items-center">
               <div class="flex items-center gap-2 mb-1">
                  <span class="material-symbols-outlined text-primary text-[18px]">qr_code_scanner</span>
                  <h3 class="text-sm font-bold text-slate-900 dark:text-white tracking-tight">Scan to Authenticate</h3>
               </div>
               <p class="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed max-w-[200px]">Open WhatsApp on your device, navigate to Linked Devices, and point your camera.</p>
            </div>
         </div>

         <div v-if="waQrStatus && ['connected', 'active', 'live', 'ready', 'open'].includes(waQrStatus.toLowerCase())" class="bg-emerald-50 dark:bg-emerald-900/10 border border-emerald-200 dark:border-emerald-800 shadow-sm rounded-2xl p-6 flex flex-col items-center justify-center text-center space-y-3 mb-8 relative overflow-hidden">
             <div class="size-16 rounded-full bg-emerald-100 dark:bg-emerald-900/50 flex items-center justify-center text-emerald-500 mb-2">
                 <span class="material-symbols-outlined text-3xl">check_circle</span>
             </div>
             <div>
                 <h3 class="text-sm font-bold text-slate-900 dark:text-white tracking-tight">Device Linked Successfully</h3>
                 <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-1 pb-2">WhatsApp channel is active and listening for inbound traffic.</p>
             </div>
         </div>

         <!-- Action Controls Grid -->
         <div class="grid grid-cols-2 gap-3 pb-safe">
            <button 
               @click="connectWhatsApp" 
               :disabled="waConnectLoading"
               class="col-span-2 py-3.5 bg-primary text-white shadow-lg hover:bg-primary/90 hover:shadow-primary/30 rounded-xl font-bold text-sm active:scale-[0.98] transition-all disabled:opacity-50 disabled:grayscale flex items-center justify-center gap-2"
            >
               <span v-if="!waConnectLoading" class="flex items-center gap-2">
                   <span class="material-symbols-outlined text-[18px]">link</span>
                   Initialize / Generate Link
               </span>
               <div v-else class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            </button>
            
            <button 
               @click="refreshWhatsAppSession" 
               :disabled="!waSelectedSessionId || waQrLoading"
               class="py-3 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-xl font-bold text-[11px] uppercase tracking-wider active:scale-95 transition-transform disabled:opacity-50 flex items-center justify-center gap-2 hover:bg-slate-200 dark:hover:bg-slate-700"
            >
               <span class="material-symbols-outlined text-[16px]">sync</span>
               Sync Status
            </button>
            
            <button 
               @click="fetchWhatsAppQr" 
               :disabled="!waSelectedSessionId || waQrLoading"
               class="py-3 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-xl font-bold text-[11px] uppercase tracking-wider active:scale-95 transition-transform disabled:opacity-50 flex items-center justify-center gap-2 hover:bg-slate-200 dark:hover:bg-slate-700"
            >
               <span class="material-symbols-outlined text-[16px]">qr_code</span>
               Fetch QR
            </button>

            <button 
               @click="disconnectWhatsApp" 
               :disabled="!waSelectedSessionId"
               class="col-span-2 py-3 mt-1 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-600 dark:text-red-400 rounded-xl font-bold uppercase tracking-widest text-[10px] active:scale-[0.98] transition-transform disabled:opacity-50 flex items-center justify-center gap-2 hover:bg-red-100 dark:hover:bg-red-500/20"
            >
               <span class="material-symbols-outlined text-[14px]">link_off</span>
               Terminate Connection
            </button>
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
    message.value = 'Synchronized connection state'
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
  message.value = ''
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
  if (!confirm("Are you sure you want to terminate this WhatsApp binding?")) return
  
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

<style scoped>
.scrollbar-none::-webkit-scrollbar {
  display: none;
}
.scrollbar-none {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
@keyframes scan {
  0% { transform: translateY(0); opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { transform: translateY(220px); opacity: 0; } /* Adjust 220px based on QR container height */
}
</style>
