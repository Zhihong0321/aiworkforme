<script setup>
import { ref, onMounted, watch } from 'vue'
import { store } from '../store'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'

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
    // We assume the workspace endpoint can tell us about its strategy or we fetch from workspace-specific endpoint
    const res = await fetch(`${API_BASE}/workspaces/${store.activeWorkspaceId}/strategy`)
    if (res.ok) {
       const data = await res.json()
       if (data) strategy.value = data
    } else {
       // Reset if not found
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

<template>
  <div class="p-8 max-w-4xl mx-auto">
    <header class="mb-8">
      <h1 class="text-2xl font-bold mb-2">Outreach Strategy</h1>
      <p class="text-slate-500 text-sm">Design how your AI agent approaches and converts leads for {{ store.activeWorkspace?.name }}.</p>
    </header>

    <div v-if="isLoading" class="p-12 text-center text-slate-400">Loading strategy...</div>

    <div v-else class="space-y-6">
      <TuiCard title="Messaging Persona" subtitle="Agent Identity">
        <div class="space-y-4">
          <div>
            <label class="block text-xs font-bold uppercase mb-1 text-slate-500">Tone & Voice</label>
            <textarea v-model="strategy.tone" class="w-full border border-slate-200 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-100 outline-none" rows="3" placeholder="e.g. Professional yet friendly, focused on value..."></textarea>
          </div>
          <div>
            <label class="block text-xs font-bold uppercase mb-1 text-slate-500">Main Objectives</label>
            <textarea v-model="strategy.objectives" class="w-full border border-slate-200 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-100 outline-none" rows="2" placeholder="What is the goal of the conversation?"></textarea>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-bold uppercase mb-1 text-slate-500">Follow-up Cadence</label>
              <select v-model="strategy.followup_preset" class="w-full border border-slate-200 rounded-lg p-3 text-sm bg-white">
                <option value="GENTLE">Gentle (3 days)</option>
                <option value="BALANCED">Balanced (2 days)</option>
                <option value="AGGRESSIVE">Aggressive (1 day)</option>
              </select>
            </div>
          </div>
        </div>
      </TuiCard>

      <TuiCard title="Safety & Guardrails" subtitle="Rules for the AI">
         <div class="space-y-4">
            <div>
              <label class="block text-xs font-bold uppercase mb-1 text-slate-500">Call-to-Action Rules</label>
              <textarea v-model="strategy.cta_rules" class="w-full border border-slate-200 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-100 outline-none" rows="2" placeholder="e.g. Always ask for a phone number after the second message."></textarea>
            </div>
            <div>
              <label class="block text-xs font-bold uppercase mb-1 text-slate-500">Objection Handling</label>
              <textarea v-model="strategy.objection_handling" class="w-full border border-slate-200 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-100 outline-none" rows="2" placeholder="How to respond when the user says 'no' or 'not interested'."></textarea>
            </div>
         </div>
      </TuiCard>

      <div class="flex flex-col items-end gap-3">
        <p v-if="message" class="text-xs font-bold text-indigo-600">{{ message }}</p>
        <TuiButton @click="saveStrategy" :loading="isSaving" class="px-12">Activate Strategy</TuiButton>
      </div>
    </div>
  </div>
</template>
