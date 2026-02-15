<script setup>
import { ref, onMounted, watch } from 'vue'
import { store } from '../store'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'

const API_BASE = `${window.location.origin}/api/v1`
const documents = ref([])
const isLoading = ref(false)
const isUploading = ref(false)
const fileInput = ref(null)

const fetchKnowledge = async () => {
  if (!store.activeWorkspace?.agent_id) {
    documents.value = []
    return
  }
  isLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/agents/${store.activeWorkspace.agent_id}/knowledge`)
    if (res.ok) {
      documents.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to fetch knowledge', e)
  } finally {
    isLoading.value = false
  }
}

const handleUpload = async (event) => {
  const file = event.target.files[0]
  if (!file || !store.activeWorkspace?.agent_id) return
  
  isUploading.value = true
  const formData = new FormData()
  formData.append('file', file)
  formData.append('tags', '["manual_upload"]')
  
  try {
    const res = await fetch(`${API_BASE}/agents/${store.activeWorkspace.agent_id}/knowledge`, {
      method: 'POST',
      body: formData
    })
    if (res.ok) {
      await fetchKnowledge()
    }
  } catch (e) {
    console.error('Upload failed', e)
  } finally {
    isUploading.value = false
  }
}

onMounted(fetchKnowledge)
watch(() => store.activeWorkspaceId, fetchKnowledge)
</script>

<template>
  <div class="p-8">
    <header class="mb-8 flex justify-between items-center">
      <div>
        <h1 class="text-2xl font-bold mb-2">Knowledge Base</h1>
        <p class="text-slate-500 text-sm">Upload documentation for Agent #{{ store.activeWorkspace?.agent_id || '?' }} to reference.</p>
      </div>
      <div class="flex gap-3">
        <input type="file" ref="fileInput" class="hidden" @change="handleUpload" accept=".txt,.pdf,.json" />
        <TuiButton @click="fileInput.click()" :loading="isUploading">
          + Upload Source
        </TuiButton>
      </div>
    </header>

    <div v-if="!store.activeWorkspace?.agent_id" class="p-12 text-center border-2 border-dashed rounded-xl">
      <p class="text-slate-500">This workspace has no AI Agent linked. Go to Settings or Agents to link one.</p>
    </div>

    <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Source List -->
      <div class="lg:col-span-2 bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
        <div class="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
           <span class="text-xs font-bold uppercase text-slate-500">Document Library</span>
           <span class="text-[10px] text-slate-400">{{ documents.length }} Sources</span>
        </div>
        
        <div v-if="isLoading" class="p-8 text-center text-slate-400 animate-pulse">Scanning knowledge vault...</div>
        
        <div v-else-if="documents.length === 0" class="p-12 text-center">
           <p class="text-slate-400 text-sm">No knowledge files found for this agent.</p>
        </div>

        <div v-else class="divide-y divide-slate-100">
          <div v-for="doc in documents" :key="doc.id" class="p-4 flex justify-between items-center hover:bg-slate-50 transition-colors">
             <div class="flex items-center gap-3">
               <div class="w-10 h-10 bg-indigo-50 text-indigo-600 flex items-center justify-center rounded font-bold text-[10px]">
                 {{ doc.filename.split('.').pop().toUpperCase() }}
               </div>
               <div>
                  <div class="text-sm font-bold text-slate-900">{{ doc.filename }}</div>
                  <div class="text-[10px] text-slate-500">
                    Uploaded {{ new Date(doc.created_at).toLocaleDateString() }} • {{ doc.content.length }} chars
                  </div>
               </div>
             </div>
             <TuiButton variant="outline" size="sm">View</TuiButton>
          </div>
        </div>
      </div>

      <!-- Health/Stats -->
      <div class="space-y-6">
        <div class="bg-white p-6 border border-slate-200 rounded-lg shadow-sm">
           <h4 class="text-xs font-bold uppercase mb-4 text-slate-500 tracking-wider">Retrieval Status</h4>
           <div class="space-y-4">
             <div class="flex justify-between items-end">
               <span class="text-sm text-slate-600">Vector Status</span>
               <TuiBadge variant="success">Active</TuiBadge>
             </div>
             <div class="flex justify-between items-end">
               <span class="text-sm text-slate-600">Sources Synced</span>
               <span class="font-bold text-slate-900">{{ documents.length }}</span>
             </div>
           </div>
        </div>
      </div>
    </div>
  </div>
</template>
