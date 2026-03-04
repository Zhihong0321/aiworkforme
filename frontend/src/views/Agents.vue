<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { request } from '../services/api'
import { store } from '../store'

const mcpServers = ref([])
const isSaving = ref(false)
const message = ref('')

const form = reactive({
  id: null,
  name: '',
  system_prompt: '',
  linkedMcpId: '',
  mimic_human_typing: false,
  emoji_level: 'none',
  segment_delay_ms: 800,
})

const extractLinkedMcpIds = (agent) => {
  if (!agent) return []
  if (Array.isArray(agent.linked_mcp_ids)) return agent.linked_mcp_ids
  if (Array.isArray(agent.linkedMcpIds)) return agent.linkedMcpIds
  if (agent.linkedMcpId) return [agent.linkedMcpId]
  if (agent.linked_mcp_id) return [agent.linked_mcp_id]
  return []
}

const loadMcpServers = async () => {
  try {
    const data = await request('/mcp/servers')
    mcpServers.value = Array.isArray(data)
      ? data.map((server, index) => ({
          id: server.id ?? index,
          name: server.name ?? 'server',
          status: (server.status ?? 'online').toLowerCase(),
          endpoint: server.endpoint ?? server.script ?? '',
          description: server.description || `Tool access via ${server.name}`
      }))
      : []
  } catch (error) {
    console.error('Failed to load mcp servers', error)
  }
}

const initForm = (agent) => {
  if (!agent) return
  const linkedIds = extractLinkedMcpIds(agent)
  form.id = agent.id
  form.name = agent.name ?? ''
  form.system_prompt = agent.system_prompt ?? agent.systemPrompt ?? ''
  form.linkedMcpId = linkedIds[0] ?? ''
  form.mimic_human_typing = agent.mimic_human_typing ?? false
  form.emoji_level = agent.emoji_level ?? 'none'
  form.segment_delay_ms = agent.segment_delay_ms ?? 800
}

watch(
    () => store.activeAgent,
    (newAgent) => {
        initForm(newAgent)
    },
    { immediate: true }
)

const toggleSkill = async (serverId) => {
  if (!form.id) return
  // If no skill linked, or different skill linked, link it.
  // Note: Only 1 MCP is supported right now, we keep it as a dropdown conceptually, but visual design shows multiple switches
  // For simplicity, we just swap it if checked, or unlink if unchecked.
  if (form.linkedMcpId === serverId) {
      form.linkedMcpId = '' // Deselect
  } else {
      form.linkedMcpId = serverId
      try {
        await request(`/agents/${form.id}/link-mcp/${serverId}`, { method: 'POST' })
        message.value = 'Skill updated.'
        await store.fetchAgents()
      } catch (e) {
        console.error('Link update failed', e)
      }
  }
}

const saveChanges = async () => {
  isSaving.value = true
  message.value = ''
  try {
    const method = form.id ? 'PUT' : 'POST'
    const path = form.id ? `/agents/${form.id}` : `/agents/`
    const payload = {
      name: form.name,
      system_prompt: form.system_prompt,
      mimic_human_typing: form.mimic_human_typing,
      emoji_level: form.emoji_level,
      segment_delay_ms: form.segment_delay_ms,
    }

    const savedData = await request(path, {
      method,
      body: JSON.stringify(payload)
    })

    message.value = 'Agent configuration saved successfully'
    await store.fetchAgents()
  } catch (error) {
    console.error('Save failed', error)
    message.value = `Save failed: ${error.message}`
  } finally {
    isSaving.value = false
    setTimeout(() => { message.value = '' }, 3000)
  }
}

onMounted(() => {
  if (store.agents.length === 0) {
    store.fetchAgents()
  }
  loadMcpServers()
})
</script>

<template>
  <div class="flex flex-col gap-6 w-full max-w-md mx-auto relative pb-24 text-slate-900 dark:text-slate-100">
    <!-- Success Message Overlay -->
    <div v-if="message" class="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 bg-emerald-500 text-white px-4 py-2 rounded-full shadow-lg text-sm font-semibold flex items-center gap-2 animate-pulse">
        <span class="material-symbols-outlined text-sm">check_circle</span>
        {{ message }}
    </div>

    <!-- Avatar Upload Section -->
    <section class="flex flex-col items-center py-6">
      <div class="relative group cursor-pointer">
        <div class="bg-primary/10 dark:bg-slate-800 aspect-square rounded-full h-32 w-32 flex items-center justify-center border-4 border-white dark:border-slate-800 shadow-sm overflow-hidden text-5xl font-bold text-primary">
            {{ form.name ? form.name.charAt(0).toUpperCase() : 'A' }}
        </div>
        <div class="absolute inset-0 bg-black/40 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
          <span class="material-symbols-outlined text-white text-3xl">photo_camera</span>
        </div>
      </div>
      <div class="mt-4 text-center">
        <p class="text-slate-900 dark:text-slate-100 text-xl font-bold leading-tight tracking-tight">Upload Avatar</p>
        <p class="text-slate-500 dark:text-slate-400 text-sm mt-1">PNG or JPG up to 5MB</p>
      </div>
    </section>

    <!-- Inputs -->
    <div class="space-y-4">
      <div class="flex flex-col gap-2">
        <label class="text-slate-900 dark:text-slate-100 text-sm font-semibold px-1">Agent Name</label>
        <input 
          v-model="form.name"
          class="w-full rounded-xl border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 h-14 px-4 focus:ring-2 focus:ring-primary focus:border-primary transition-all placeholder:text-slate-400" 
          placeholder="e.g. Personal Assistant" 
          type="text" 
        />
      </div>
      <div class="flex flex-col gap-2">
        <div class="flex justify-between items-center px-1">
            <label class="text-slate-900 dark:text-slate-100 text-sm font-semibold">System Instructions</label>
            <span class="text-xs text-slate-500 font-mono hidden sm:inline">system_prompt</span>
        </div>
        <textarea 
          v-model="form.system_prompt"
          class="w-full rounded-xl border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 min-h-[160px] p-4 focus:ring-2 focus:ring-primary focus:border-primary transition-all placeholder:text-slate-400 resize-none" 
          placeholder="Describe how the agent should behave..."
        ></textarea>
      </div>
    </div>

    <!-- Behaviour Tweaks -->
    <section class="space-y-4">
      <h3 class="text-slate-900 dark:text-slate-100 text-lg font-bold px-1 pt-2">Advanced Behaviour</h3>
      <div class="bg-white dark:bg-slate-900 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 p-4 space-y-6">
        
        <!-- Toggle: Mimic Human Typing -->
        <div class="flex items-center justify-between">
            <div class="flex flex-col">
            <span class="font-medium text-slate-800 dark:text-slate-200">Mimic Human Typing</span>
            <span class="text-[11px] text-slate-500 mt-0.5">Short replies · casual tone · WhatsApp style</span>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
                <input v-model="form.mimic_human_typing" class="sr-only peer" type="checkbox"/>
                <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
            </label>
        </div>

        <!-- Emoji Level -->
        <div class="space-y-2">
            <div class="flex items-center gap-2">
            <span class="font-medium text-slate-800 dark:text-slate-200">Emoji Frequency</span>
            </div>
            <div class="flex gap-2">
            <button
                v-for="opt in [{ val: 'none', label: '🚫 None' }, { val: 'low', label: '🙂 Low' }, { val: 'high', label: '🎉 High' }]"
                :key="opt.val"
                type="button"
                @click="form.emoji_level = opt.val"
                class="flex-1 py-2 px-3 rounded-lg text-xs font-bold border transition-colors"
                :class="form.emoji_level === opt.val
                ? 'bg-primary text-white border-primary shadow-sm'
                : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700'"
            >
                {{ opt.label }}
            </button>
            </div>
        </div>

        <!-- Segment Delay -->
        <div class="space-y-2">
            <div class="flex justify-between items-center">
            <span class="font-medium text-slate-800 dark:text-slate-200">Segment Delay</span>
            <span class="text-xs font-mono text-primary font-bold">{{ form.segment_delay_ms }}ms</span>
            </div>
            <input
            type="range"
            min="200"
            max="3000"
            step="100"
            v-model.number="form.segment_delay_ms"
            class="w-full h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer"
            />
        </div>

      </div>
    </section>

    <!-- Skills List -->
    <section class="space-y-4">
      <h3 class="text-slate-900 dark:text-slate-100 text-lg font-bold px-1 pt-2">Skills</h3>
      <div v-if="mcpServers.length === 0" class="text-slate-500 text-sm px-1">
          No skills registered in the system yet.
      </div>
      <div v-else class="bg-white dark:bg-slate-900 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800">
        
        <div 
            v-for="(server, index) in mcpServers" 
            :key="server.id"
            class="flex items-center justify-between p-4"
            :class="{'border-b border-slate-100 dark:border-slate-800': index !== mcpServers.length - 1}"
        >
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg flex items-center justify-center text-primary" :class="form.linkedMcpId === server.id ? 'bg-primary/20' : 'bg-primary/5'">
              <span class="material-symbols-outlined">{{ form.linkedMcpId === server.id ? 'check_circle' : 'extension' }}</span>
            </div>
            <div class="flex flex-col">
                <span class="font-medium text-slate-800 dark:text-slate-200">{{ server.name }}</span>
                <span class="text-xs text-slate-500">{{ server.description }}</span>
            </div>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input 
                :checked="form.linkedMcpId === server.id" 
                @change="toggleSkill(server.id)"
                class="sr-only peer" 
                type="checkbox"
            />
            <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
          </label>
        </div>

      </div>
    </section>

    <!-- Sticky Footer -->
    <footer class="fixed bottom-0 left-0 right-0 p-4 bg-background-light/80 dark:bg-background-dark/80 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 z-40">
      <div class="max-w-md mx-auto">
        <button 
            @click="saveChanges"
            :disabled="isSaving"
            class="w-full bg-primary hover:bg-primary/90 text-white font-bold h-14 rounded-xl shadow-lg shadow-primary/25 flex items-center justify-center transition-transform active:scale-[0.98] disabled:opacity-50"
        >
            <div v-if="isSaving" class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            <span v-else>Save Changes</span>
        </button>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* Range slider accent color fallback */
input[type=range] {
    accent-color: var(--primary);
}
</style>