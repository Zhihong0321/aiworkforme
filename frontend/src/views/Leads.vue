<script setup>
import { ref, onMounted, watch } from 'vue'
import { store } from '../store'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'

const API_BASE = `${window.location.origin}/api/v1`
const leads = ref([])
const isLoading = ref(false)

const fetchLeads = async () => {
  if (!store.activeWorkspaceId) return
  isLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/workspaces/${store.activeWorkspaceId}/leads`)
    if (res.ok) {
      leads.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to fetch leads', e)
  } finally {
    isLoading.value = false
  }
}

const getStageVariant = (stage) => {
  if (['NEW', 'CONTACTED'].includes(stage)) return 'info'
  if (['ENGAGED', 'QUALIFIED'].includes(stage)) return 'success'
  if (['TAKE_OVER'].includes(stage)) return 'warning'
  return 'muted'
}

onMounted(fetchLeads)
watch(() => store.activeWorkspaceId, fetchLeads)
</script>

<template>
  <div class="p-8">
    <header class="mb-8 flex justify-between items-center">
      <div>
        <h1 class="text-2xl font-bold mb-2">Lead Pipeline</h1>
        <p class="text-slate-500 text-sm">Managing {{ leads.length }} real leads in {{ store.activeWorkspace?.name || 'Workspace' }}.</p>
      </div>
      <TuiButton>+ Import Leads</TuiButton>
    </header>

    <div v-if="isLoading" class="p-12 text-center text-slate-400 animate-pulse">
      Syncing pipeline with CRM...
    </div>

    <div v-else-if="leads.length === 0" class="p-20 text-center border-2 border-dashed rounded-2xl bg-slate-50">
      <h3 class="text-slate-900 font-bold mb-2">No Leads Found</h3>
      <p class="text-slate-500 text-sm mb-6">Start by importing leads or connecting your CRM.</p>
      <TuiButton variant="outline">Import Sample Data</TuiButton>
    </div>

    <div v-else class="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
      <table class="w-full text-left text-sm">
        <thead class="bg-slate-50 border-b border-slate-200 uppercase text-[10px] tracking-wider font-bold text-slate-500">
          <tr>
            <th class="px-6 py-4">Lead Contact</th>
            <th class="px-6 py-4">Pipeline Stage</th>
            <th class="px-6 py-4">Last Follow-up</th>
            <th class="px-6 py-4">Schedule</th>
            <th class="px-6 py-4 text-right">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="lead in leads" :key="lead.id" class="hover:bg-slate-50 transition-colors">
            <td class="px-6 py-4">
              <div class="font-bold text-slate-900">{{ lead.name || 'Anonymous' }}</div>
              <div class="text-[10px] text-slate-500 font-mono">{{ lead.external_id }}</div>
            </td>
            <td class="px-6 py-4">
              <TuiBadge :variant="getStageVariant(lead.stage)">{{ lead.stage }}</TuiBadge>
            </td>
            <td class="px-6 py-4">
               <span v-if="lead.last_follow_up_at" class="text-slate-600">
                 {{ new Date(lead.last_follow_up_at).toLocaleTimeString() }}
               </span>
               <span v-else class="text-slate-400 text-[10px] italic">Never contacted</span>
            </td>
            <td class="px-6 py-4">
               <span v-if="lead.next_followup_at" class="text-indigo-600 font-bold">
                 Due {{ new Date(lead.next_followup_at).toLocaleTimeString() }}
               </span>
               <span v-else class="text-slate-400 text-[10px]">Manual skip</span>
            </td>
            <td class="px-6 py-4 text-right">
              <TuiButton variant="outline" size="sm">Open</TuiButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
