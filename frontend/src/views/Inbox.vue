<script setup>
import { ref, onMounted, watch } from 'vue'
import { store } from '../store'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'

const API_BASE = `${window.location.origin}/api/v1`
const conversations = ref([])
const messages = ref([])
const selectedId = ref(null)
const isLoading = ref(false)
const isSending = ref(false)
const composer = ref('')

const fetchConversations = async () => {
  isLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/chat/conversations`)
    if (res.ok) {
      conversations.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to fetch conversations', e)
  } finally {
    isLoading.value = false
  }
}

const fetchMessages = async (id) => {
  selectedId.value = id
  try {
    const res = await fetch(`${API_BASE}/chat/${id}/messages`)
    if (res.ok) {
      messages.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to fetch messages', e)
  }
}

const sendMessage = async () => {
  if (!composer.value.trim() || !selectedId.value) return
  
  const conversation = conversations.value.find(c => c.id === selectedId.value)
  if (!conversation) return

  isSending.value = true
  const text = composer.value
  composer.value = ''
  
  try {
    const res = await fetch(`${API_BASE}/chat/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        agent_id: conversation.agent_id, 
        message: text 
      })
    })
    if (res.ok) {
      await fetchMessages(selectedId.value)
    }
  } catch (e) {
    console.error('Send failed', e)
  } finally {
    isSending.value = false
  }
}

onMounted(fetchConversations)
</script>

<template>
  <div class="flex h-[calc(100vh-64px)] overflow-hidden bg-slate-50">
    <!-- Lead List -->
    <div class="w-80 border-r border-slate-200 bg-white flex flex-col">
      <div class="p-4 border-b border-slate-200 bg-slate-50">
        <h2 class="font-bold text-slate-800 tracking-tight">Active Chats</h2>
        <p class="text-[10px] text-slate-500 uppercase font-bold mt-1">Real-time Outreach</p>
      </div>
      
      <div v-if="isLoading && conversations.length === 0" class="p-8 text-center text-slate-400 animate-pulse">
        Loading sessions...
      </div>
      
      <div v-else-if="conversations.length === 0" class="p-8 text-center text-slate-400 italic text-sm">
        No active conversations.
      </div>

      <div class="flex-grow overflow-y-auto divide-y divide-slate-100">
        <div 
          v-for="c in conversations" 
          :key="c.id"
          @click="fetchMessages(c.id)"
          class="p-4 cursor-pointer hover:bg-slate-50 transition-colors"
          :class="{ 'bg-indigo-50 border-l-4 border-indigo-600': selectedId === c.id }"
        >
          <div class="flex justify-between items-start mb-1">
            <span class="font-bold text-sm text-slate-900">Session #{{ c.id }}</span>
            <span class="text-[9px] text-slate-400 font-mono">{{ new Date(c.updated_at).toLocaleTimeString() }}</span>
          </div>
          <div class="text-[11px] text-slate-500 truncate leading-relaxed">{{ c.last_message }}</div>
          <div class="mt-2 flex gap-2">
            <TuiBadge variant="info">Agent #{{ c.agent_id }}</TuiBadge>
          </div>
        </div>
      </div>
    </div>

    <!-- Chat Area -->
    <div class="flex-grow flex flex-col">
      <div v-if="selectedId" class="flex flex-col h-full bg-white shadow-inner">
        <!-- Header -->
        <div class="p-4 border-b border-slate-200 bg-white flex justify-between items-center">
          <div>
            <h3 class="font-bold text-slate-900">Conversation History</h3>
            <p class="text-[10px] text-slate-500 uppercase">Interactive Session Control</p>
          </div>
          <div class="flex gap-2">
            <TuiButton variant="outline" size="sm" @click="fetchMessages(selectedId)">Refresh</TuiButton>
            <TuiButton variant="ghost" size="sm" class="text-red-600">Takeover</TuiButton>
          </div>
        </div>

        <!-- Messages -->
        <div class="flex-grow p-6 overflow-y-auto space-y-6 bg-slate-50">
          <div 
            v-for="msg in messages" 
            :key="msg.id" 
            :class="[
              'max-w-[85%] p-4 rounded-2xl shadow-sm text-sm leading-relaxed',
              msg.role === 'user' ? 'bg-white border border-slate-200 self-start' : 'bg-indigo-600 text-white self-end ml-auto'
            ]"
          >
            <div class="flex justify-between items-center mb-1">
               <span class="text-[9px] font-bold uppercase tracking-tighter" :class="msg.role === 'user' ? 'text-slate-400' : 'text-indigo-200'">
                 {{ msg.role }}
               </span>
               <span class="text-[9px]" :class="msg.role === 'user' ? 'text-slate-300' : 'text-indigo-300'">
                 {{ new Date(msg.created_at).toLocaleTimeString() }}
               </span>
            </div>
            <p>{{ msg.content }}</p>
            
            <!-- Tool Calls -->
            <div v-if="msg.tool_calls" class="mt-2 pt-2 border-t border-indigo-500">
               <TuiBadge variant="warning" class="bg-indigo-700 text-white border-none">TOOL EXECUTION</TuiBadge>
            </div>
          </div>
        </div>

        <!-- Composer -->
        <div class="p-4 bg-white border-t border-slate-200">
          <div class="max-w-4xl mx-auto flex flex-col gap-3">
            <textarea 
              v-model="composer"
              class="w-full p-4 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-100 outline-none transition-all resize-none"
              placeholder="Type a message as the agent..."
              rows="2"
              @keyup.enter.ctrl="sendMessage"
            ></textarea>
            <div class="flex justify-between items-center">
              <span class="text-[10px] text-slate-400 italic">Press Ctrl+Enter to send</span>
              <TuiButton :loading="isSending" @click="sendMessage">Send Message</TuiButton>
            </div>
          </div>
        </div>
      </div>
      
      <div v-else class="flex-grow flex flex-col items-center justify-center text-slate-400 bg-slate-50">
        <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mb-4">
           <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
        </div>
        <p class="text-sm font-medium">Select a conversation to start management</p>
      </div>
    </div>
  </div>
</template>
