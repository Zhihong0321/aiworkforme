<template>
  <div class="knowledge-vault-view relative min-h-screen">
    <main class="relative z-10 mx-auto w-full max-w-none px-5 lg:px-10 py-10 space-y-8">
      <header class="tui-surface rounded-xl border border-slate-200 p-6">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div class="space-y-2">
            <p class="text-xs uppercase tracking-[0.32em] text-slate-500">z.ai admin</p>
            <h1 class="text-3xl font-bold text-slate-900">Knowledge Vault for Agent: {{ agentId }}</h1>
            <p class="text-sm text-slate-600">
              Manage knowledge files, tags, and descriptions for this agent.
              These files will be used by the agent to answer questions dynamically.
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <TuiButton size="sm" variant="outline" @click="openAddModal">Add New Knowledge</TuiButton>
            <TuiBadge variant="info">/api/v1</TuiBadge>
            <TuiBadge variant="muted">base: dynamic (current host)</TuiBadge>
          </div>
        </div>
      </header>

      <section class="tui-surface rounded-xl border border-slate-200 p-6">
        <h2 class="text-xl font-semibold mb-4">Attached Knowledge Files</h2>
        <div v-if="isLoading" class="text-center py-8 text-slate-500">Loading knowledge files...</div>
        <div v-else-if="!knowledgeFiles.length" class="text-center py-8 text-slate-500">No knowledge files attached yet.</div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-slate-200">
            <thead class="bg-slate-50">
              <tr>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Filename</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Description</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Tags</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Last Triggered (Debug)</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-slate-200">
              <tr v-for="file in knowledgeFiles" :key="file.id">
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                  {{ file.filename }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                  {{ file.description || 'No description' }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                  <div class="flex flex-wrap gap-1">
                    <TuiBadge v-for="tag in parseJsonArray(file.tags)" :key="tag" variant="outline">{{ tag }}</TuiBadge>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                  <div class="flex flex-wrap gap-1">
                    <TuiBadge v-for="input in parseJsonArray(file.last_trigger_inputs)" :key="input" variant="muted" class="text-xs">{{ input }}</TuiBadge>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <TuiButton size="sm" variant="ghost" @click="openEditModal(file)" class="mr-2">Edit</TuiButton>
                  <TuiButton size="sm" variant="ghost" class="text-red-600" @click="deleteKnowledgeFile(file.id)">Delete</TuiButton>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>

    <!-- Add/Edit Knowledge Modal -->
    <div v-if="isModalOpen" class="fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-50 flex items-center justify-center">
      <div class="bg-white rounded-lg shadow-xl w-full max-w-lg p-6">
        <h2 class="text-xl font-bold mb-4">{{ editingFile ? 'Edit Knowledge File' : 'Add New Knowledge File' }}</h2>
        <form @submit.prevent="saveKnowledge">
          <div class="mb-4">
            <TuiInput label="Filename" v-model="form.filename" :disabled="!!editingFile" />
            <p v-if="editingFile" class="text-xs text-slate-500 mt-1">Filename cannot be changed after creation.</p>
          </div>
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-700 mb-1">Description</label>
            <textarea v-model="form.description" class="form-textarea mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"></textarea>
          </div>
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-700 mb-1">Tags (comma-separated)</label>
            <input
              type="text"
              v-model="form.tagsText"
              class="form-input mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
              placeholder="e.g., billing, policy, finance"
            >
          </div>
          <div v-if="!editingFile" class="mb-4">
            <label class="block text-sm font-medium text-slate-700 mb-1">Upload File</label>
            <input type="file" ref="fileInput" @change="handleFileUpload" class="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-violet-50 file:text-violet-700 hover:file:bg-violet-100"/>
          </div>
          <div v-else class="mb-4">
            <label class="block text-sm font-medium text-slate-700 mb-1">File Content</label>
            <textarea v-model="form.content" rows="10" class="form-textarea mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"></textarea>
          </div>
          <div class="flex justify-end gap-2">
            <TuiButton type="button" variant="outline" @click="closeModal">Cancel</TuiButton>
            <TuiButton type="submit" :loading="isSaving">{{ editingFile ? 'Save Changes' : 'Upload & Add' }}</TuiButton>
          </div>
          <p v-if="message" class="text-sm mt-4 text-center" :class="{ 'text-red-500': message.includes('failed'), 'text-green-500': !message.includes('failed') }">{{ message }}</p>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
import { ref, reactive, onMounted, watchEffect } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiInput from '../components/ui/TuiInput.vue' // Reusing TuiInput for filename

const API_BASE = `${window.location.origin}/api/v1`

const route = useRoute()
const agentId = ref(null)
const knowledgeFiles = ref([])
const isLoading = ref(true)
const isSaving = ref(false)
const isModalOpen = ref(false)
const editingFile = ref(null) // Stores the file being edited, or null for add
const currentFile = ref(null) // For file upload input
const message = ref('')
const fileInput = ref(null)

const form = reactive({
  id: null,
  filename: '',
  description: '',
  tagsText: '', // Comma-separated tags (single source of truth)
  content: '' // For editing existing file content
})

const parseJsonArray = (value) => {
  if (Array.isArray(value)) {
    return value.filter((item) => typeof item === 'string')
  }
  if (typeof value !== 'string') return []

  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
  } catch (e) {
    // Defensive fallback for non-JSON strings (e.g., Python repr "['a', 'b']").
    // Best-effort only; if it still fails, show no tags rather than crashing.
    try {
      const normalized = value.includes("'") && !value.includes('"') ? value.replaceAll("'", '"') : value
      const parsed = JSON.parse(normalized)
      return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
    } catch (_) {
      return []
    }
  }
}

const loadKnowledgeFiles = async (id) => {
  if (!id) {
    knowledgeFiles.value = []
    return
  }
  isLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/agents/${id}/knowledge`)
    if (!res.ok) throw new Error('Failed to load knowledge files')
    const data = await res.json()
    knowledgeFiles.value = data
  } catch (error) {
    console.error('Error loading knowledge files:', error)
    message.value = `Failed to load knowledge files: ${error.message}`
  } finally {
    isLoading.value = false
  }
}

const openAddModal = () => {
  editingFile.value = null
  form.id = null
  form.filename = ''
  form.description = ''
  form.tagsText = ''
  form.content = ''
  currentFile.value = null
  isModalOpen.value = true
  message.value = ''
}

const openEditModal = (file) => {
  editingFile.value = file
  form.id = file.id
  form.filename = file.filename
  form.description = file.description
  form.tagsText = parseJsonArray(file.tags).join(', ')
  form.content = file.content
  currentFile.value = null // Clear file input when editing existing
  isModalOpen.value = true
  message.value = ''
}

const closeModal = () => {
  isModalOpen.value = false
  message.value = ''
  // Reset file input explicitly if it exists
  if (fileInput.value) {
    fileInput.value.value = null;
  }
}

const normalizeTags = (raw) => {
  if (!raw) return []
  return raw
    .split(',')
    .map((tag) => tag.trim())
    .filter((tag) => tag)
}

const handleFileUpload = (event) => {
  currentFile.value = event.target.files?.[0] || null
}

const saveKnowledge = async () => {
  isSaving.value = true
  message.value = ''
  try {
    const tagsForSave = [...new Set(normalizeTags(form.tagsText))]

    let url = ''
    let method = ''
    let body = null
    const headers = {}

    if (editingFile.value) {
      // Editing existing file
      url = `${API_BASE}/knowledge/${form.id}`
      method = 'PATCH'
      headers['Content-Type'] = 'application/json'
      body = JSON.stringify({
        filename: form.filename,
        content: form.content,
        description: form.description,
        tags: tagsForSave
      })
    } else {
      // Adding new file
      url = `${API_BASE}/agents/${agentId.value}/knowledge`
      method = 'POST'
      if (!currentFile.value) throw new Error('No file selected for upload.')
      const formData = new FormData()
      formData.append('description', form.description)
      formData.append('tags', JSON.stringify(tagsForSave)) // Send tags as JSON string
      formData.append('file', currentFile.value)
      body = formData
    }

    const res = await fetch(url, {
      method,
      headers,
      body
    })

    if (!res.ok) {
      let errorText = `HTTP ${res.status}`
      try {
        const errorData = await res.json()
        errorText = errorData.detail || JSON.stringify(errorData)
      } catch (_) {
        try {
          errorText = await res.text()
        } catch (_) {
          // ignore
        }
      }
      throw new Error(errorText || 'Failed to save knowledge file')
    }

    message.value = editingFile.value ? 'Knowledge file updated successfully.' : 'Knowledge file added successfully.'
    closeModal()
    await loadKnowledgeFiles(agentId.value)
  } catch (error) {
    console.error('Error saving knowledge file:', error)
    message.value = `Error: ${error.message}`
  } finally {
    isSaving.value = false
  }
}

const deleteKnowledgeFile = async (fileId) => {
  if (!confirm('Are you sure you want to delete this knowledge file?')) return
  
  try {
    const res = await fetch(`${API_BASE}/agents/${agentId.value}/knowledge/${fileId}`, {
      method: 'DELETE'
    })

    if (!res.ok) throw new Error('Failed to delete knowledge file')

    message.value = 'Knowledge file deleted successfully.'
    await loadKnowledgeFiles(agentId.value)
  } catch (error) {
    console.error('Error deleting knowledge file:', error)
    message.value = `Error: ${error.message}`
  }
}


watchEffect(() => {
  agentId.value = route.params.agentId
  if (agentId.value) {
    loadKnowledgeFiles(agentId.value)
  } else {
    knowledgeFiles.value = []
  }
})

onMounted(() => {
  // Initial load if agentId is already present on mount
  if (route.params.agentId) {
    agentId.value = route.params.agentId
    loadKnowledgeFiles(agentId.value)
  }
})
</script>

<style scoped>
/* Scoped styles */
.form-input, .form-textarea {
  @apply block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50;
}
</style>
