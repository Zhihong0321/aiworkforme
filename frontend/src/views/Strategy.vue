<template>
  <div class="min-h-[calc(100vh-64px)] w-full bg-onyx font-inter text-slate-200 pb-20 relative overflow-hidden flex flex-col">
    <!-- Aurora Background Effect -->
    <div class="absolute inset-0 bg-mobile-aurora z-0 pointer-events-none opacity-40"></div>

    <!-- Header Section -->
    <div class="p-5 border-b border-slate-800/50 glass-panel-light rounded-b-[2rem] sticky top-0 z-30 mb-4 relative shadow-lg">
       <div class="flex items-center gap-3 mb-2">
         <div class="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center border border-purple-500/30 text-purple-400 shrink-0">
             <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
         </div>
         <div>
           <h1 class="text-2xl font-bold text-white tracking-tight leading-none">Strategy</h1>
           <p class="text-[10px] text-aurora font-bold uppercase tracking-widest mt-1">AI Outreach Playbook</p>
         </div>
       </div>
    </div>

    <!-- Main Content Area -->
    <main class="flex-grow px-4 pb-10 relative z-10 w-full max-w-2xl mx-auto space-y-6">
      
      <div v-if="isLoading" class="flex justify-center items-center py-20">
         <div class="w-8 h-8 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin"></div>
      </div>

      <div v-else class="space-y-6 animate-fade-in mt-2">
        
        <!-- Messaging Persona Panel -->
        <div class="glass-panel p-5 rounded-[2rem] border border-slate-700/50">
           <div class="flex items-center gap-2 mb-5">
              <svg class="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" /></svg>
              <h3 class="text-xs font-bold uppercase tracking-widest text-white">Messaging Persona</h3>
           </div>

           <div class="space-y-4">
              <div class="space-y-1.5">
                 <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Tone & Voice</label>
                 <textarea v-model="strategy.tone" rows="3" placeholder="e.g. Professional yet friendly, focused on value..." class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3.5 text-sm font-semibold text-white focus:outline-none focus:border-purple-500 transition-colors resize-none"></textarea>
              </div>
              
              <div class="space-y-1.5">
                 <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Main Objectives</label>
                 <textarea v-model="strategy.objectives" rows="2" placeholder="What is the goal of the conversation?" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3.5 text-sm font-semibold text-white focus:outline-none focus:border-purple-500 transition-colors resize-none"></textarea>
              </div>
              
              <div class="space-y-1.5">
                 <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Follow-up Cadence</label>
                 <div class="relative">
                    <select v-model="strategy.followup_preset" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3.5 text-sm font-semibold text-white focus:outline-none focus:border-purple-500 transition-colors appearance-none">
                      <option value="GENTLE">Gentle (3 days)</option>
                      <option value="BALANCED">Balanced (2 days)</option>
                      <option value="AGGRESSIVE">Aggressive (1 day)</option>
                    </select>
                    <div class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                       <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                    </div>
                 </div>
              </div>
           </div>
        </div>

        <!-- Safety & Guardrails -->
        <div class="glass-panel p-5 rounded-[2rem] border border-slate-700/50 relative overflow-hidden">
           <div class="absolute -right-10 -top-10 w-32 h-32 bg-blue-500/10 blur-2xl rounded-full pointer-events-none"></div>

           <div class="flex items-center gap-2 mb-5 relative z-10">
              <svg class="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
              <h3 class="text-xs font-bold uppercase tracking-widest text-white">Safety & Guardrails</h3>
           </div>

           <div class="space-y-4 relative z-10">
              <div class="space-y-1.5">
                 <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Call-to-Action Rules</label>
                 <textarea v-model="strategy.cta_rules" rows="2" placeholder="e.g. Always ask for a phone number after the second message." class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3.5 text-sm font-semibold text-white focus:outline-none focus:border-blue-500 transition-colors resize-none"></textarea>
              </div>
              <div class="space-y-1.5">
                 <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Objection Handling</label>
                 <textarea v-model="strategy.objection_handling" rows="2" placeholder="How to respond when the user says 'no' or 'not interested'." class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3.5 text-sm font-semibold text-white focus:outline-none focus:border-blue-500 transition-colors resize-none"></textarea>
              </div>
           </div>
        </div>

        <!-- Sticky Mobile Actions -->
        <div class="pt-2 pb-safe bg-onyx/80 backdrop-blur-md sticky bottom-16 z-20 mx--4 px-4 sm:mx-0 sm:px-0 sm:static sm:bg-transparent -mx-4">
           <div v-if="message" class="mb-3 flex justify-center">
              <span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20 text-[10px] font-bold text-green-400 uppercase tracking-widest">
                 <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                 {{ message }}
              </span>
           </div>
           
           <button 
              @click="saveStrategy" 
              :disabled="isSaving"
              class="w-full py-4 bg-aurora-gradient text-white rounded-2xl font-bold uppercase tracking-widest text-sm shadow-lg shadow-purple-500/20 active:scale-[0.98] transition-transform disabled:opacity-50 flex items-center justify-center gap-2"
           >
              <span v-if="!isSaving">Activate Strategy</span>
              <div v-else class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
           </button>
        </div>

      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { store } from '../store'

const API_BASE = `${window.location.origin}/api/v1`
const strategy = ref({
  tone: '',
  objectives: '',
  objection_handling: '',
  cta_rules: '',
  followup_preset: 'BALANCED'
})
const isLoading = ref(false)
const isSaving = ref(false)
const message = ref('')

const fetchStrategy = async () => {
  if (!store.activeWorkspaceId) return
  isLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/workspaces/${store.activeWorkspaceId}/strategy`)
    if (res.ok) {
       const data = await res.json()
       if (data) strategy.value = data
    } else {
       strategy.value = { tone: '', objectives: '', objection_handling: '', cta_rules: '', followup_preset: 'BALANCED' }
    }
  } catch (e) {
    console.error('Failed to fetch strategy', e)
  } finally {
    isLoading.value = false
  }
}

const saveStrategy = async () => {
  if (!store.activeWorkspaceId) return
  isSaving.value = true
  message.value = ''
  try {
    const res = await fetch(`${API_BASE}/workspaces/${store.activeWorkspaceId}/strategy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(strategy.value)
    })
    if (res.ok) {
      message.value = 'Strategy Updated and Activated'
    }
  } catch (e) {
    message.value = 'Failed to save'
  } finally {
    isSaving.value = false
  }
}

onMounted(fetchStrategy)
watch(() => store.activeWorkspaceId, fetchStrategy)
</script>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out forwards;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
