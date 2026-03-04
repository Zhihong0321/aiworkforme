<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { store } from '../store'
import { request } from '../services/api'
import TuiInput from '../components/ui/TuiInput.vue'

const documents = ref([])
const isLoading = ref(false)
const isUploading = ref(false)
const fileInput = ref(null)

const activeTab = ref('files') // 'files' or 'faq'

// Editor State
const isEditing = ref(false)
const editingDoc = ref({ id: null, filename: '', content: '' })
const isSaving = ref(false)

// FAQ State
const faqDoc = ref(null)
const faqs = ref([])
const isSavingFaq = ref(false)
const isEditingFaq = ref(false)
const editingFaqIndex = ref(-1)
const editingFaqItem = ref({ q: '', a: '' })
const expandedFaqs = ref({}) // Track which FAQs are expanded

const standardDocuments = computed(() => {
  return documents.value.filter(d => {
    try {
      const tags = d.tags || '[]'
      return !tags.includes('fundamental_context') && !tags.includes('agent_goal') && !tags.includes('faq')
    } catch(e) { return true }
  })
})

const fetchKnowledge = async () => {
  if (!store.activeAgentId) {
    documents.value = []
    faqs.value = []
    return
  }
  isLoading.value = true
  try {
    const data = await request(`/agents/${store.activeAgentId}/knowledge`)
    documents.value = data
    
    faqDoc.value = data.find(d => d.tags && d.tags.includes('faq'))
    if (faqDoc.value) {
        try {
            faqs.value = JSON.parse(faqDoc.value.content)
        } catch(e) { faqs.value = [] }
    } else {
        faqs.value = []
    }
  } catch (e) {
    console.error('Failed to fetch knowledge', e)
  } finally {
    isLoading.value = false
  }
}

const handleUpload = async (event) => {
  const file = event.target.files[0]
  if (!file || !store.activeAgentId) return
  
  isUploading.value = true
  const formData = new FormData()
  formData.append('file', file)
  formData.append('tags', '["manual_upload"]')
  
  try {
    // using fetch directly for FormData
    const res = await fetch(`${window.location.origin}/api/v1/agents/${store.activeAgentId}/knowledge`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'X-Tenant-Id': localStorage.getItem('tenant_id') || ''
        },
        body: formData
    })
    
    if(!res.ok) throw new Error('Upload failed')
    await fetchKnowledge()
  } catch (e) {
    console.error('Upload failed', e)
    alert('Upload failed: ' + e.message)
  } finally {
    isUploading.value = false
    if(fileInput.value) fileInput.value.value = ''
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
    
    const formData = new FormData()
    formData.append('filename', editingDoc.value.filename)
    formData.append('content', editingDoc.value.content)
    
    const path = isNew 
      ? `/agents/${store.activeAgentId}/knowledge/text`
      : `/agents/knowledge/${editingDoc.value.id}`

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

const deleteDoc = async (id, event) => {
  if (event) event.stopPropagation();
  if (!confirm('Permanently delete this knowledge source?')) return
  try {
    await request(`/agents/${store.activeAgentId}/knowledge/${id}`, { method: 'DELETE' })
    await fetchKnowledge()
    if (editingDoc.value.id === id) isEditing.value = false
  } catch (e) {
    console.error('Delete failed', e)
  }
}

const saveSpecialDoc = async (docRef, contentValue, filename, tag, isSavingRef) => {
  isSavingRef.value = true
  try {
    const isNew = !docRef.value
    const method = isNew ? 'POST' : 'PUT'
    
    const formData = new FormData()
    formData.append('filename', filename)
    formData.append('content', contentValue)
    if (method === 'PUT') {
        const rawTags = docRef.value.tags || '[]'
        formData.append('tags', rawTags)
    } else {
        formData.append('tags', `["${tag}"]`)
    }
    
    const path = isNew 
      ? `/agents/${store.activeAgentId}/knowledge/text`
      : `/agents/knowledge/${docRef.value.id}`

    await request(path, { method, body: formData })
    await fetchKnowledge()
  } catch(e) {
    console.error(e)
    alert('Failed to save')
  } finally {
    isSavingRef.value = false
  }
}

const createNewFaq = () => {
    editingFaqItem.value = { q: '', a: '' }
    editingFaqIndex.value = -1
    isEditingFaq.value = true
}

const editFaq = (index, event) => {
    if (event) event.stopPropagation();
    editingFaqItem.value = { ...faqs.value[index] }
    editingFaqIndex.value = index
    isEditingFaq.value = true
}

const deleteFaq = async (index, event) => {
    if (event) event.stopPropagation();
    if(!confirm('Delete this FAQ?')) return
    const newFaqs = [...faqs.value]
    newFaqs.splice(index, 1)
    await saveSpecialDoc(faqDoc, JSON.stringify(newFaqs), 'faq.json', 'faq', isSavingFaq)
}

const saveFaqItem = async () => {
    const newFaqs = [...faqs.value]
    if (editingFaqIndex.value >= 0) {
        newFaqs[editingFaqIndex.value] = editingFaqItem.value
    } else {
        newFaqs.push(editingFaqItem.value)
    }
    isEditingFaq.value = false
    await saveSpecialDoc(faqDoc, JSON.stringify(newFaqs), 'faq.json', 'faq', isSavingFaq)
}

const toggleFaq = (index) => {
    expandedFaqs.value[index] = !expandedFaqs.value[index]
}

const getFileIcon = (filename) => {
    const ext = filename.split('.').pop().toLowerCase()
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) {
        return { icon: 'image', colorUrl: 'text-amber-600 dark:text-amber-400', bgUrl: 'bg-amber-100 dark:bg-amber-900/30' }
    }
    if (ext === 'pdf') {
        return { icon: 'picture_as_pdf', colorUrl: 'text-red-600 dark:text-red-400', bgUrl: 'bg-red-100 dark:bg-red-900/30' }
    }
    if (ext === 'doc' || ext === 'docx') {
        return { icon: 'article', colorUrl: 'text-blue-600 dark:text-blue-400', bgUrl: 'bg-blue-100 dark:bg-blue-900/30' }
    }
    return { icon: 'description', colorUrl: 'text-slate-600 dark:text-slate-400', bgUrl: 'bg-slate-200 dark:bg-slate-700/50' }
}

const formatBytes = (bytes, decimals = 1) => {
    if (!+bytes) return '0 Bytes'
    const k = 1024
    const dm = decimals < 0 ? 0 : decimals
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

onMounted(() => {
    if (store.activeAgentId) fetchKnowledge()
})
watch(() => store.activeAgentId, fetchKnowledge)
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-64px)] w-full max-w-md mx-auto relative text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-900">
    
    <div v-if="!store.activeAgentId" class="flex flex-col items-center justify-center flex-1 p-6 text-center">
        <span class="material-symbols-outlined text-6xl text-slate-300 mb-4">smart_toy</span>
        <h3 class="text-lg font-bold">No Agent Linked</h3>
        <p class="text-sm text-slate-500 mt-2">Please select or create an agent from the sidebar drawer to manage knowledge.</p>
    </div>

    <template v-else>
        <!-- Header & Tabs -->
        <div class="sticky top-0 z-10 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md pt-2">
            <!-- Swipeable Tabs -->
            <div class="flex px-4 border-b border-slate-200 dark:border-slate-800">
                <button 
                  @click="activeTab = 'files'"
                  class="flex-1 flex flex-col items-center justify-center py-3 transition-colors border-b-2"
                  :class="activeTab === 'files' ? 'border-primary text-primary font-bold' : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 font-medium'"
                >
                  <span class="text-sm">Files</span>
                </button>
                <button 
                  @click="activeTab = 'faq'"
                  class="flex-1 flex flex-col items-center justify-center py-3 transition-colors border-b-2"
                  :class="activeTab === 'faq' ? 'border-primary text-primary font-bold' : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 font-medium'"
                >
                  <span class="text-sm">FAQ</span>
                </button>
            </div>
        </div>

        <!-- Main Content Area -->
        <main class="flex-1 overflow-y-auto w-full">
            
            <!-- Tab Content: Files -->
            <div v-show="activeTab === 'files'" class="p-4 space-y-6 animate-in fade-in duration-300">
                <!-- Upload Card -->
                <div class="relative group" @click="fileInput.click()">
                  <input type="file" ref="fileInput" class="hidden" @change="handleUpload" accept=".txt,.pdf,.json,.doc,.docx,image/*" />
                  <div class="absolute -inset-1 bg-gradient-to-r from-primary/20 to-primary/10 rounded-xl blur opacity-25 group-hover:opacity-50 transition duration-1000"></div>
                  <div class="relative flex flex-col items-center justify-center border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-xl p-8 bg-white dark:bg-slate-800 text-center hover:border-primary transition-colors cursor-pointer w-full box-border">
                      <div v-if="isUploading" class="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                          <span class="material-symbols-outlined text-primary text-3xl animate-spin">sync</span>
                      </div>
                      <div v-else class="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4 text-primary group-hover:scale-110 transition-transform">
                          <span class="material-symbols-outlined text-3xl">cloud_upload</span>
                      </div>
                      <h3 class="text-lg font-bold">{{ isUploading ? 'Uploading...' : 'Tap to Upload' }}</h3>
                      <p class="text-slate-500 dark:text-slate-400 text-sm mt-1 mb-4">Upload your documents to train the AI (PDF, DOCX, TXT)</p>
                      <button :disabled="isUploading" class="bg-primary hover:bg-primary/90 text-white px-6 py-2 rounded-lg font-semibold text-sm transition-all active:scale-95 disabled:opacity-50 pointer-events-none">
                          {{ isUploading ? 'Please Wait' : 'Select Files' }}
                      </button>
                  </div>
                </div>

                <!-- Recent Files List -->
                <div class="space-y-4">
                    <div class="flex items-center justify-between">
                        <h3 class="text-base font-bold">Recent Files ({{ standardDocuments.length }})</h3>
                        <button class="text-primary text-sm font-semibold" @click="fetchKnowledge" :class="{'opacity-50': isLoading}">
                            <span class="material-symbols-outlined text-sm align-middle" :class="{'animate-spin': isLoading}">refresh</span> Refresh
                        </button>
                    </div>

                    <div v-if="standardDocuments.length === 0" class="text-center p-6 border border-slate-100 dark:border-slate-800 rounded-xl bg-slate-50 dark:bg-slate-800/20">
                        <p class="text-sm text-slate-500">No files uploaded yet.</p>
                    </div>

                    <div v-else class="space-y-3 pb-24">
                        <div 
                          v-for="doc in standardDocuments" 
                          :key="doc.id"
                          @click="openEditor(doc)"
                          class="flex items-center gap-4 p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer transition-colors group box-border w-full"
                        >
                            <div class="p-2 rounded shrink-0 h-10 w-10 flex items-center justify-center" :class="getFileIcon(doc.filename).bgUrl">
                                <span class="material-symbols-outlined" :class="getFileIcon(doc.filename).colorUrl">{{ getFileIcon(doc.filename).icon }}</span>
                            </div>
                            <div class="flex-1 min-w-0 pr-2">
                                <p class="text-sm font-semibold truncate">{{ doc.filename }}</p>
                                <p class="text-xs text-slate-500 truncate">{{ formatBytes((doc.content || '').length) }} • {{ new Date(doc.created_at).toLocaleDateString() }}</p>
                            </div>
                            
                            <!-- Delete button (appears on hover or always on touch screens) -->
                            <button @click.stop="deleteDoc(doc.id, $event)" class="shrink-0 text-slate-400 hover:text-red-500 p-2 rounded-full hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100">
                                <span class="material-symbols-outlined text-sm">delete</span>
                            </button>
                            <!-- Status badge -->
                            <span class="flex items-center gap-1 px-2 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-[10px] font-bold uppercase tracking-wider shrink-0 transition-opacity group-hover:opacity-0 absolute right-4 pointer-events-none">
                                <span class="material-symbols-outlined text-[12px]">check_circle</span>
                                Ready
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab Content: FAQ -->
            <div v-show="activeTab === 'faq'" class="p-4 space-y-4 animate-in fade-in duration-300 pb-24">
                <div v-if="faqs.length === 0" class="text-center p-8 border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-xl bg-slate-50 dark:bg-slate-800/20 w-full box-border">
                    <span class="material-symbols-outlined text-4xl text-slate-300 mb-2">quiz</span>
                    <h3 class="text-sm font-bold">No FAQs</h3>
                    <p class="text-xs text-slate-500 mt-1">Add frequent questions to help your agent answer correctly.</p>
                </div>

                <div v-for="(faq, index) in faqs" :key="index" class="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-white dark:bg-slate-900 w-full box-border">
                    <div 
                      class="p-4 bg-slate-50 dark:bg-slate-800 flex justify-between items-center cursor-pointer select-none relative group"
                      @click="toggleFaq(index)"
                    >
                        <p class="text-sm font-semibold pr-8">{{ faq.q }}</p>
                        <span class="material-symbols-outlined transition-transform duration-200 shrink-0" :class="{'rotate-180': expandedFaqs[index]}">expand_more</span>
                    </div>
                    <!-- Collapsible Answer -->
                    <div 
                      v-show="expandedFaqs[index]" 
                      class="p-4 border-t border-slate-100 dark:border-slate-800 text-sm text-slate-600 dark:text-slate-300 animate-in slide-in-from-top-2 duration-200"
                    >
                        <p class="whitespace-pre-wrap">{{ faq.a }}</p>
                        <div class="mt-4 flex gap-2 justify-end border-t border-slate-100 dark:border-slate-800 pt-3">
                            <button @click.stop="editFaq(index, $event)" class="text-xs font-semibold text-primary px-3 py-1.5 rounded bg-primary/10 hover:bg-primary/20 transition-colors">Edit</button>
                            <button @click.stop="deleteFaq(index, $event)" class="text-xs font-semibold text-red-600 px-3 py-1.5 rounded bg-red-100 dark:bg-red-900/30 hover:bg-red-200 transition-colors">Remove</button>
                        </div>
                    </div>
                </div>
            </div>
        </main>

        <!-- Floating Action Button (New Text / New FAQ) -->
        <button 
          @click="activeTab === 'files' ? createNewText() : createNewFaq()"
          class="fixed right-6 size-14 bg-primary text-white rounded-full shadow-lg shadow-primary/40 flex items-center justify-center hover:scale-105 transition-transform active:scale-95 z-30 bottom-8">
            <span class="material-symbols-outlined text-2xl" :class="activeTab === 'files' ? 'edit_document' : 'add'">{{ activeTab === 'files' ? 'edit_document' : 'add' }}</span>
        </button>


        <!-- Editor Modals (Sliding Drawer Style) -->
        <div v-if="isEditing || isEditingFaq" class="fixed inset-0 z-50 flex flex-col justify-end">
            <!-- Backdrop -->
            <div class="absolute inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity" @click="isEditing = false; isEditingFaq = false"></div>
            
            <!-- Modal Content (Slides up from bottom on mobile, right on desktop conceptually) -->
            <div class="relative w-full max-w-md mx-auto bg-white dark:bg-slate-900 h-[85vh] rounded-t-2xl shadow-2xl flex flex-col animate-in slide-in-from-bottom duration-300 z-10 box-border">
                
                <!-- Drag Handle -->
                <div class="w-full flex justify-center pt-3 pb-1">
                    <div class="w-12 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full"></div>
                </div>

                <header class="px-6 pb-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
                    <div>
                        <h3 class="font-bold text-lg">
                            <template v-if="isEditing">{{ editingDoc.id ? 'Edit Text File' : 'New Text File' }}</template>
                            <template v-if="isEditingFaq">{{ editingFaqIndex >= 0 ? 'Edit FAQ' : 'New FAQ' }}</template>
                        </h3>
                    </div>
                    <button @click="isEditing = false; isEditingFaq = false" class="p-2 -mr-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-colors">
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </header>

                <!-- TEXT EDITOR BODY -->
                <div v-if="isEditing" class="p-6 flex-1 overflow-y-auto flex flex-col gap-4">
                    <div class="flex flex-col gap-1.5">
                        <label class="text-xs font-semibold text-slate-600 dark:text-slate-400">Filename</label>
                        <TuiInput v-model="editingDoc.filename" placeholder="notepad.txt" class="!rounded-xl" />
                    </div>
                    <div class="flex-1 flex flex-col gap-1.5 min-h-[200px]">
                        <label class="text-xs font-semibold text-slate-600 dark:text-slate-400">Content</label>
                        <textarea 
                            v-model="editingDoc.content" 
                            class="flex-1 w-full p-4 bg-slate-50 dark:bg-slate-800 border-none rounded-xl text-sm font-medium text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-primary outline-none transition-all resize-none"
                            placeholder="Type document content here..."
                        ></textarea>
                    </div>
                </div>

                <!-- FAQ EDITOR BODY -->
                <div v-if="isEditingFaq" class="p-6 flex-1 overflow-y-auto flex flex-col gap-4">
                    <div class="flex flex-col gap-1.5">
                        <label class="text-xs font-semibold text-slate-600 dark:text-slate-400">Question</label>
                        <TuiInput v-model="editingFaqItem.q" placeholder="What are your hours?" class="!rounded-xl" />
                    </div>
                    <div class="flex-1 flex flex-col gap-1.5 min-h-[200px]">
                        <label class="text-xs font-semibold text-slate-600 dark:text-slate-400">Answer</label>
                        <textarea 
                            v-model="editingFaqItem.a" 
                            class="flex-1 w-full p-4 bg-slate-50 dark:bg-slate-800 border-none rounded-xl text-sm font-medium text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-primary outline-none transition-all resize-none"
                            placeholder="Type the exact answer the AI should use..."
                        ></textarea>
                    </div>
                </div>

                <!-- Footer Actions -->
                <footer class="p-4 border-t border-slate-100 dark:border-slate-800 safe-bottom">
                    <button 
                        @click="isEditing ? saveEditor() : saveFaqItem()" 
                        :disabled="isSaving || isSavingFaq"
                        class="w-full bg-primary hover:bg-primary/90 text-white font-bold h-12 rounded-xl shadow-lg shadow-primary/25 flex items-center justify-center transition-transform active:scale-[0.98] disabled:opacity-50"
                    >
                        {{ (isSaving || isSavingFaq) ? 'Saving...' : 'Save Changes' }}
                    </button>
                </footer>
            </div>
        </div>

    </template>
  </div>
</template>

<style scoped>
/* Mobile specific adjustments to ensure modals dont get stuck via keyboard push */
.safe-bottom {
    padding-bottom: max(env(safe-area-inset-bottom), 1rem);
}
</style>
