<script setup>
import { ref, onMounted, watch } from 'vue'
import { store } from '../store'
import { request } from '../services/api'

// Settings State
const crmControl = ref({
  timezone: 'UTC', // Frontend display placeholder, timezone logic can be added backend later if needed
  working_hours_start: '09:00',
  working_hours_end: '18:00',
  enabled: true,
  scan_frequency_messages: 4,
  aggressiveness: 'BALANCED',
  not_interested_strategy: 'GENTLE',
  rejected_strategy: 'BALANCED',
  double_reject_strategy: 'AGGRESSIVE',
  qualification_criteria: '', // Conceptual placeholder for UI mockup parity (can be added to backend model later)
  followup_steps: [ // Mock steps for the timeline UI as required by Stitch Design
    { id: 1, title: 'Wait 24 Hours', desc: 'If no response, send "Friendly Nudge" email template.', type: 'Email', tag: 'Template: Nudge_1' },
    { id: 2, title: 'Wait 3 Days', desc: 'Send LinkedIn connect & message with "Value Proposition".', type: 'Social', tag: 'Manual Task' },
  ]
})

const isLoading = ref(false)
const isSaving = ref(false)
const actionMessage = ref('')
const actionError = ref('')

// Load Control Profile
const fetchControl = async () => {
  if (!store.activeAgentId) {
    // Reset to defaults
    return
  }
  isLoading.value = true
  try {
    const data = await request(`/agents/${store.activeAgentId}/ai-crm/control`)
    if (data) {
        // Map backend to local state while keeping the mock UI elements intact for visual completeness
        crmControl.value = {
            ...crmControl.value,
            enabled: data.enabled ?? true,
            scan_frequency_messages: data.scan_frequency_messages ?? 4,
            aggressiveness: data.aggressiveness || 'BALANCED',
            not_interested_strategy: data.not_interested_strategy || 'GENTLE',
            rejected_strategy: data.rejected_strategy || 'BALANCED',
            double_reject_strategy: data.double_reject_strategy || 'AGGRESSIVE'
        }
    }
  } catch (e) {
    console.error('Failed to fetch CRM control', e)
  } finally {
    isLoading.value = false
  }
}

// Save Control Profile
const saveControl = async () => {
  if (!store.activeAgentId) return
  isSaving.value = true
  actionMessage.value = ''
  actionError.value = ''
  try {
    const payload = {
        enabled: crmControl.value.enabled,
        scan_frequency_messages: crmControl.value.scan_frequency_messages,
        aggressiveness: crmControl.value.aggressiveness,
        not_interested_strategy: crmControl.value.not_interested_strategy,
        rejected_strategy: crmControl.value.rejected_strategy,
        double_reject_strategy: crmControl.value.double_reject_strategy
    }
    
    await request(`/agents/${store.activeAgentId}/ai-crm/control`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
    
    actionMessage.value = 'Settings saved successfully'
  } catch (e) {
    actionError.value = 'Failed to save settings: ' + (e.message || 'Unknown error')
  } finally {
    isSaving.value = false
    setTimeout(() => { actionMessage.value = ''; actionError.value = '' }, 3000)
  }
}

const removeStep = (index) => {
    crmControl.value.followup_steps.splice(index, 1)
}

const addStep = () => {
    crmControl.value.followup_steps.push({
        id: Date.now(),
        title: 'Wait X Days',
        desc: 'New follow-up action definition.',
        type: 'Channel',
        tag: 'Action'
    })
}

onMounted(() => {
  if (store.activeAgentId) fetchControl()
})
watch(() => store.activeAgentId, fetchControl)
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-64px)] w-full relative text-slate-900 dark:text-slate-100 bg-background-light dark:bg-background-dark">
    
    <!-- Action Notification -->
    <div v-if="actionMessage || actionError" class="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 px-4 py-2 rounded-full shadow-lg text-sm font-semibold flex items-center gap-2 animate-in slide-in-from-top-2" :class="actionError ? 'bg-red-500 text-white' : 'bg-emerald-500 text-white'">
        <span class="material-symbols-outlined text-sm">{{ actionError ? 'error' : 'check_circle' }}</span>
        {{ actionError || actionMessage }}
    </div>

    <!-- Active Agent Check -->
    <div v-if="!store.activeAgentId" class="flex flex-col items-center justify-center flex-1 p-6 text-center max-w-md mx-auto">
        <span class="material-symbols-outlined text-6xl text-slate-300 dark:text-slate-700 mb-4">settings_suggest</span>
        <h3 class="text-lg font-bold">No Agent Linked</h3>
        <p class="text-sm text-slate-500 mt-2">Please select or create an agent from the sidebar drawer to configure their CRM Strategy.</p>
    </div>

    <!-- Main Content wrapper -->
    <main v-else class="flex-1 overflow-y-auto max-w-md mx-auto w-full pb-32 px-4 pt-6 space-y-6">

        <div v-if="isLoading" class="flex justify-center p-8">
            <span class="material-symbols-outlined animate-spin text-primary">sync</span>
        </div>
        
        <template v-else>
            <!-- Engine Toggle -->
            <section class="bg-white dark:bg-slate-900 rounded-xl p-5 shadow-sm border border-slate-200 dark:border-slate-800 flex justify-between items-center">
                <div class="flex items-center gap-3">
                    <span class="material-symbols-outlined" :class="crmControl.enabled ? 'text-green-500' : 'text-slate-400'">power_settings_new</span>
                    <div>
                        <h2 class="font-bold text-sm">AI CRM Engine</h2>
                        <span class="text-[10px] uppercase font-bold tracking-wider" :class="crmControl.enabled ? 'text-green-500' : 'text-slate-400'">{{ crmControl.enabled ? 'Active' : 'Paused' }}</span>
                    </div>
                </div>
                <!-- Toggle switch -->
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="crmControl.enabled" class="sr-only peer">
                    <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
                </label>
            </section>

            <!-- Base Configuration Matrix (Translating the old aggressiveness/strategies to the new UI style visually) -->
            <section class="bg-white dark:bg-slate-900 rounded-xl p-5 shadow-sm border border-slate-200 dark:border-slate-800 space-y-4">
                <div class="flex items-center gap-2 mb-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                    <span class="material-symbols-outlined text-primary">psychology</span>
                    <h2 class="font-bold text-lg">AI Sales Strategy</h2>
                </div>

                <div>
                    <label class="block text-sm font-medium mb-1 text-slate-600 dark:text-slate-400">Baseline Aggressiveness</label>
                    <div class="relative">
                        <select v-model="crmControl.aggressiveness" class="w-full appearance-none rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-4 py-3 text-sm font-semibold focus:ring-2 focus:ring-primary focus:border-primary outline-none text-slate-900 dark:text-white">
                            <option value="PASSIVE">Passive (Nurture Only)</option>
                            <option value="BALANCED">Balanced (Standard)</option>
                            <option value="AGGRESSIVE">Aggressive (Hard Close)</option>
                        </select>
                        <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">expand_more</span>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-3 pt-2">
                    <div>
                        <label class="block text-[11px] uppercase tracking-wider font-bold mb-1.5 text-slate-500">Not Interested</label>
                        <select v-model="crmControl.not_interested_strategy" class="w-full appearance-none rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 p-3 text-xs font-semibold focus:ring-2 focus:ring-primary focus:border-primary outline-none">
                            <option value="GENTLE">Gentle Retreat</option>
                            <option value="BALANCED">Counter Offer</option>
                            <option value="AGGRESSIVE">Push Details</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-[11px] uppercase tracking-wider font-bold mb-1.5 text-slate-500">Rejected</label>
                        <select v-model="crmControl.rejected_strategy" class="w-full appearance-none rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 p-3 text-xs font-semibold focus:ring-2 focus:ring-primary focus:border-primary outline-none">
                            <option value="GENTLE">Gentle Retreat</option>
                            <option value="BALANCED">Counter Offer</option>
                            <option value="AGGRESSIVE">Push Details</option>
                        </select>
                    </div>
                </div>
            </section>

            <!-- Global Settings Card (From Mockup) -->
            <section class="bg-white dark:bg-slate-900 rounded-xl p-5 shadow-sm border border-slate-200 dark:border-slate-800">
                <div class="flex items-center gap-2 mb-4">
                    <span class="material-symbols-outlined text-primary">settings</span>
                    <h2 class="font-bold text-lg">Global Parameters</h2>
                </div>
                <div class="space-y-4">
                    <!-- Time Zone (Visual Placeholder) -->
                    <div>
                        <label class="block text-sm font-medium mb-1.5 text-slate-600 dark:text-slate-400">Time Zone</label>
                        <div class="relative">
                            <select v-model="crmControl.timezone" disabled class="w-full appearance-none rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-4 py-3 text-sm focus:ring-2 focus:ring-primary focus:border-primary outline-none opacity-80">
                                <option value="UTC">Coordinated Universal Time (UTC)</option>
                                <option value="EST">Eastern Time (ET)</option>
                            </select>
                            <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">expand_more</span>
                        </div>
                    </div>
                    <!-- Analysis Frequency -->
                    <div>
                        <label class="block text-sm font-medium mb-1.5 text-slate-600 dark:text-slate-400">Analyze Every X Messages</label>
                        <div class="grid grid-cols-2 gap-3">
                            <div class="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 overflow-hidden">
                                <input type="number" min="3" max="10" v-model.number="crmControl.scan_frequency_messages" class="w-full bg-transparent border-none py-3 text-sm font-semibold focus:ring-0 px-0 outline-none text-slate-900 dark:text-white" />
                                <span class="material-symbols-outlined text-xs text-slate-400">sync</span>
                            </div>
                        </div>
                        <p class="mt-2 text-xs text-slate-500 italic">CRM calculates intent after this many messages in a thread.</p>
                    </div>
                </div>
            </section>

            <!-- Qualification Criteria (Visual Placeholder mapped from Mockup) -->
            <section class="bg-white dark:bg-slate-900 rounded-xl p-5 shadow-sm border border-slate-200 dark:border-slate-800 opacity-80" aria-disabled="true">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-primary">verified</span>
                        <h2 class="font-bold text-lg">Qualification Criteria</h2>
                    </div>
                    <span class="text-[10px] uppercase font-bold text-slate-400 tracking-widest border border-slate-300 dark:border-slate-700 px-2 py-0.5 rounded text-xs">Beta</span>
                </div>
                <textarea disabled v-model="crmControl.qualification_criteria" class="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 p-4 text-sm outline-none min-h-[80px] placeholder:text-slate-400 cursor-not-allowed" placeholder="Ideal lead profile description (Feature Coming Soon)..."></textarea>
            </section>

            <!-- Follow-up Rules Timeline (Mockup implementation) -->
            <section class="space-y-4">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-primary">alt_route</span>
                        <h2 class="font-bold text-lg text-slate-900 dark:text-slate-100">Workflow Rules</h2>
                    </div>
                    <button @click="addStep" class="text-primary text-sm font-bold flex items-center gap-1 active:scale-95 transition-transform">
                        <span class="material-symbols-outlined text-sm">add</span> Add Step
                    </button>
                </div>

                <div class="relative ml-4 space-y-6 before:absolute before:left-[11px] before:top-2 before:h-[calc(100%-16px)] before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
                    
                    <div v-for="(step, index) in crmControl.followup_steps" :key="step.id" class="relative pl-10 group">
                        <!-- Node timeline dot -->
                        <div class="absolute left-0 top-1 size-6 rounded-full border-4 border-white dark:border-slate-900 bg-primary z-10 transition-transform group-hover:scale-110"></div>
                        
                        <!-- Card -->
                        <div class="bg-white dark:bg-slate-900 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 transition-all hover:border-primary/50">
                            <div class="flex justify-between items-start mb-2">
                                <span class="text-xs font-bold text-primary uppercase tracking-wider">Step {{ index + 1 }}</span>
                                <button @click="removeStep(index)" class="text-slate-400 hover:text-red-500 transition-colors">
                                    <span class="material-symbols-outlined text-sm">close</span>
                                </button>
                            </div>
                            <!-- Editable titles to pretend functionality in UI view -->
                            <input v-model="step.title" class="font-bold text-sm mb-1 bg-transparent border-none p-0 outline-none w-full text-slate-900 dark:text-slate-100" />
                            <textarea v-model="step.desc" class="text-sm text-slate-600 dark:text-slate-400 bg-transparent border-none p-0 resize-none w-full h-10 outline-none"></textarea>
                            
                            <div class="mt-3 flex gap-2">
                                <span class="px-2 py-1 bg-primary/10 text-primary text-[10px] font-bold rounded uppercase cursor-pointer hover:bg-primary/20">{{ step.type }}</span>
                                <span class="px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-[10px] font-bold rounded uppercase cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-700">{{ step.tag }}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Empty state -->
                     <div v-if="crmControl.followup_steps.length === 0" class="pl-10 text-sm text-slate-500 italic">
                         No workflow rules defined. Add a step to guide the AI.
                     </div>
                </div>
            </section>
        </template>
    </main>

    <!-- Floating Save Button -->
    <div v-if="store.activeAgentId" class="fixed bottom-6 right-6 z-40">
        <button 
           @click="saveControl" 
           :disabled="isSaving"
           class="bg-primary text-white size-14 rounded-full shadow-lg shadow-primary/40 flex items-center justify-center hover:scale-105 active:scale-95 transition-transform disabled:opacity-50"
        >
           <span v-if="isSaving" class="material-symbols-outlined animate-spin">sync</span>
           <span v-else class="material-symbols-outlined">save</span>
        </button>
    </div>

  </div>
</template>

<style scoped>
/* Range slider accent color fallback */
input[type=range] {
    accent-color: var(--primary);
}
</style>
