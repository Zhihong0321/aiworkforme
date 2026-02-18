<script setup>
import { ref, onMounted, watch } from 'vue'
import { store } from '../store'
import { request } from '../services/api'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiInput from '../components/ui/TuiInput.vue'

const documents = ref([])
const isLoading = ref(false)
const isUploading = ref(false)
const fileInput = ref(null)

// Editor State
const isEditing = ref(false)
const editingDoc = ref({ id: null, filename: '', content: '' })
const isSaving = ref(false)

const fetchKnowledge = async () => {
  if (!store.activeWorkspace?.agent_id) {
    documents.value = []
    return
  }
  isLoading.value = true
  try {
    const data = await request(`/agents/${store.activeWorkspace.agent_id}/knowledge`)
    documents.value = data
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
    await request(`/agents/${store.activeWorkspace.agent_id}/knowledge`, {
      method: 'POST',
      body: formData
    })
    
    await fetchKnowledge()
  } catch (e) {
    console.error('Upload failed', e)
  } finally {
    isUploading.value = false
  }
}

const openEditor = (doc) => {
  editingDoc.value = { ...doc }
  isEditing.value = true
}

const createNewText = () => {
  editingDoc.value = { id: null, filename: 'new_source.txt', content: '' }
  isEditing.value = true
}

const saveEditor = async () => {
  if (!editingDoc.value.filename) return
  isSaving.value = true
  try {
    const isNew = !editingDoc.value.id
    const method = isNew ? 'POST' : 'PUT'
    
    // For manual text creation, we use form data as backend expects it for knowledge updates
    const formData = new FormData()
    formData.append('filename', editingDoc.value.filename)
    formData.append('content', editingDoc.value.content)
    
    // Note: Our backend 'update' and 'upload' have different paths
    const path = isNew 
      ? `/agents/${store.activeWorkspace.agent_id}/knowledge/text`
      : `/agents/knowledge/${editingDoc.value.id}`

    // We use fetch directly for FormData to be safe
    await request(path, {
      method,
      body: formData
    })

    isEditing.value = false
    await fetchKnowledge()
  } catch (e) {
    console.error('Failed to save knowledge', e)
    alert('Failed to save: ' + e.message)
  } finally {
    isSaving.value = false
  }
}

const deleteDoc = async (id) => {
  if (!confirm('Permanently delete this knowledge source?')) return
  try {
    await request(`/agents/${store.activeWorkspace.agent_id}/knowledge/${id}`, { method: 'DELETE' })
    await fetchKnowledge()
    if (editingDoc.value.id === id) isEditing.value = false
  } catch (e) {
    console.error('Delete failed', e)
  }
}

const getFileTypeIcon = (filename) => {
    const ext = filename.split('.').pop().toLowerCase()
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return '🖼️'
    if (ext === 'pdf') return '📕'
    if (ext === 'json') return '🔢'
    return '📄'
}

onMounted(fetchKnowledge)
watch(() => store.activeWorkspaceId, fetchKnowledge)
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto">
    <header class="mb-12 flex justify-between items-end">
      <div>
        <h1 class="text-3xl font-black text-slate-900 tracking-tight mb-2">Knowledge Base</h1>
        <p class="text-slate-500 text-sm">Upload documentation or images for Agent to reference during conversations.</p>
      </div>
      <div class="flex gap-3">
        <TuiButton variant="outline" @click="createNewText">
          + New Text
        </TuiButton>
        <input type="file" ref="fileInput" class="hidden" @change="handleUpload" accept=".txt,.pdf,.json,image/*" />
        <TuiButton @click="fileInput.click()" :loading="isUploading" class="bg-indigo-600 shadow-lg shadow-indigo-600/20">
          + Upload Source
        </TuiButton>
      </div>
    </header>

    <div v-if="!store.activeWorkspace?.agent_id" class="p-20 text-center border-2 border-dashed border-slate-200 rounded-[2rem] bg-slate-50/50">
      <div class="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-6">
          <svg class="w-8 h-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
      </div>
      <h3 class="text-slate-900 font-bold mb-2">No Agent Linked</h3>
      <p class="text-slate-500 text-sm max-w-sm mx-auto">Configure an agent for this workspace to start building your knowledge base.</p>
    </div>

    <div v-else class="grid grid-cols-1 xl:grid-cols-4 gap-8">
      <!-- Source List -->
      <div class="xl:col-span-3">
        <div class="bg-white border border-slate-200 rounded-[2rem] overflow-hidden shadow-xl shadow-slate-200/50">
            <div class="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <span class="text-[10px] uppercase font-black tracking-widest text-slate-400">Agent Memory Vault</span>
               <TuiBadge variant="info" size="sm">{{ documents.length }} Sources</TuiBadge>
            </div>
            
            <div v-if="isLoading" class="p-20 text-center">
                <div class="inline-flex gap-2 mb-4">
                    <span class="w-2 h-2 rounded-full bg-indigo-600 animate-bounce"></span>
                    <span class="w-2 h-2 rounded-full bg-indigo-600 animate-bounce [animation-delay:0.2s]"></span>
                    <span class="w-2 h-2 rounded-full bg-indigo-600 animate-bounce [animation-delay:0.4s]"></span>
                </div>
                <p class="text-[10px] text-slate-400 font-black uppercase tracking-widest">Indexing knowledge...</p>
            </div>
            
            <div v-else-if="documents.length === 0" class="p-20 text-center">
               <p class="text-slate-400 text-sm">Your agent's brain is currently empty. Upload some sources to get started.</p>
            </div>

            <div v-else class="divide-y divide-slate-50">
              <div v-for="doc in documents" :key="doc.id" 
                class="p-6 flex justify-between items-center hover:bg-slate-50/80 transition-all group pointer-cursor"
                @click="openEditor(doc)"
              >
                 <div class="flex items-center gap-5">
                   <div class="w-12 h-12 bg-white border border-slate-100 shadow-sm flex items-center justify-center rounded-2xl text-xl group-hover:scale-110 transition-transform">
                     {{ getFileTypeIcon(doc.filename) }}
                   </div>
                   <div>
                      <div class="text-sm font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">{{ doc.filename }}</div>
                      <div class="text-[10px] text-slate-400 font-medium mt-0.5">
                        {{ new Date(doc.created_at).toLocaleDateString() }} • {{ (doc.content.length / 1024).toFixed(1) }} KB
                      </div>
                   </div>
                 </div>
                 <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <TuiButton variant="outline" size="sm" class="!rounded-xl border-slate-200">Open Editor</TuiButton>
                    <TuiButton variant="outline" size="sm" class="!rounded-xl border-slate-200 text-red-500 hover:bg-red-50" @click.stop="deleteDoc(doc.id)">Delete</TuiButton>
                 </div>
              </div>
            </div>
        </div>
      </div>

      <!-- Stats / Right Bar -->
      <div class="space-y-6">
        <div class="bg-indigo-600 p-8 rounded-[2rem] text-white shadow-xl shadow-indigo-600/30 relative overflow-hidden">
           <div class="relative z-10">
               <h4 class="text-[10px] font-black uppercase tracking-widest opacity-60 mb-4">RAG Engine Status</h4>
               <div class="text-3xl font-black mb-1">98.2%</div>
               <div class="text-[10px] font-bold opacity-80 uppercase tracking-tight">Search Accuracy</div>
               <div class="mt-8 flex items-center gap-2">
                 <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                 <span class="text-xs font-bold uppercase tracking-tighter">Vector Database Online</span>
               </div>
           </div>
           <div class="absolute -right-4 -bottom-4 w-32 h-32 bg-white/10 rounded-full blur-3xl"></div>
        </div>
      </div>
    </div>

    <!-- Editor Drawer (Overlay) -->
    <div v-if="isEditing" class="fixed inset-0 z-50 flex justify-end">
        <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" @click="isEditing = false"></div>
        <div class="relative w-full max-w-2xl bg-white h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
            <header class="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <div>
                   <h3 class="font-black text-slate-900 uppercase tracking-tight">{{ editingDoc.id ? 'Edit Source' : 'New Source' }}</h3>
                   <div class="text-[10px] text-slate-400 font-bold uppercase tracking-widest">Knowledge Material</div>
                </div>
                <button @click="isEditing = false" class="text-slate-400 hover:text-slate-600 transition-colors">
                    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
            </header>
            
            <div class="p-8 flex-1 overflow-y-auto space-y-6">
                <div>
                    <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest mb-2">Filename</label>
                    <TuiInput v-model="editingDoc.filename" placeholder="documentation.txt" class="!rounded-2xl" />
                </div>
                <div class="flex-1 flex flex-col h-[500px]">
                    <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest mb-2">Content</label>
                    <textarea 
                        v-model="editingDoc.content" 
                        class="flex-1 w-full p-6 bg-slate-50 border border-slate-200 rounded-3xl text-sm font-medium text-slate-700 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all resize-none"
                        placeholder="Enter documentation content here..."
                    ></textarea>
                </div>
            </div>

            <footer class="p-6 border-t border-slate-100 flex gap-4 bg-slate-50/50">
                <TuiButton @click="isEditing = false" variant="outline" class="flex-1 !rounded-2xl">Cancel</TuiButton>
                <TuiButton @click="saveEditor" :loading="isSaving" class="flex-1 !rounded-2xl bg-indigo-600 shadow-lg shadow-indigo-600/20">
                    {{ editingDoc.id ? 'Update Memory' : 'Save as Source' }}
                </TuiButton>
            </footer>
        </div>
    </div>
  </div>
</template>

