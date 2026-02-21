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
  <div class="flex flex-col h-[calc(100vh-64px)] w-full overflow-hidden bg-white font-inter text-slate-700">
    
    <!-- ==================== LEAD LIST VIEW ==================== -->
    <div v-if="!selectedId" class="flex flex-col h-full w-full">
      <!-- Header & Filters -->
      <div class="p-5 border-b border-slate-200 z-10 bg-white border border-slate-200 shadow-sm rounded-b-3xl mb-2">
        <h2 class="text-3xl font-semibold text-slate-900 tracking-tight mb-5 mt-2">Inbox</h2>
        <div class="flex gap-3 overflow-x-auto pb-2 -mx-2 px-2 scrollbar-none [scrollbar-width:none]">
          <button class="px-5 py-2 rounded-full text-sm font-medium bg-blue-600 text-white shadow-sm hover:bg-blue-700 shadow-lg shadow-purple-500/25 shrink-0">All Chats</button>
          <button class="px-5 py-2 rounded-full text-sm font-medium bg-white border border-slate-200 shadow-sm text-slate-700 hover:text-slate-900 shrink-0">Unread</button>
          <button class="px-5 py-2 rounded-full text-sm font-medium bg-white border border-slate-200 shadow-sm text-slate-700 hover:text-slate-900 shrink-0">Needs Attention</button>
        </div>
      </div>
      
      <!-- Loading State -->
      <div v-if="isLoading && conversations.length === 0" class="flex-grow flex items-center justify-center text-slate-600 animate-pulse">
        <div class="flex flex-col items-center gap-3">
          <div class="w-8 h-8 rounded-full border-t-2 border-r-2 border-purple-500 animate-spin"></div>
          <p class="text-sm">Syncing latest messages...</p>
        </div>
      </div>
      
      <!-- Empty State -->
      <div v-else-if="conversations.length === 0" class="flex-grow flex items-center justify-center p-8 text-center text-slate-600 italic text-sm">
        No active conversations right now.
      </div>

      <!-- List -->
      <div class="flex-grow overflow-y-auto px-4 pb-20 space-y-3 scrollbar-none [scrollbar-width:none]">
        <div 
          v-for="c in conversations" 
          :key="c.id"
          @click="fetchMessages(c.id)"
          class="p-4 rounded-2xl cursor-pointer bg-white border border-slate-200 shadow-sm hover:bg-white transition-all active:scale-[0.98] border border-slate-200"
        >
          <div class="flex justify-between items-start mb-2">
            <span class="font-semibold text-base text-slate-900">Session #{{ c.id }}</span>
            <span class="text-[11px] text-slate-600 font-medium">{{ new Date(c.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</span>
          </div>
          <div class="text-sm text-slate-600 line-clamp-2 leading-relaxed">{{ c.last_message || 'No messages yet' }}</div>
          <div class="mt-3 flex gap-2">
            <span class="text-[10px] uppercase font-bold tracking-wider px-2 py-1 rounded bg-purple-500/20 text-purple-300 border border-purple-500/20">Agent #{{ c.agent_id }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== CHAT VIEW ==================== -->
    <div v-else class="flex flex-col h-full w-full hidden">
      <!-- Chat Header -->
      <div class="p-4 border-b border-slate-200 bg-white border border-slate-200 shadow-sm z-20 flex justify-between items-center rounded-b-[32px] shadow-lg">
        <div class="flex items-center gap-3">
          <button @click="selectedId = null" class="p-2 -ml-2 text-slate-600 hover:text-slate-900 rounded-full bg-white active:scale-95 transition-all">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 19l-7-7 7-7" /></svg>
          </button>
          <div class="flex flex-col">
            <h3 class="font-semibold text-slate-900 text-lg leading-tight">Session #{{ selectedId }}</h3>
            <p class="text-[10px] text-blue-600 font-bold uppercase tracking-wider">AI Handling</p>
          </div>
        </div>
        
        <!-- AI vs Human Toggle -->
        <div class="flex items-center gap-2">
          <span class="text-[10px] text-slate-600 font-bold uppercase">Human</span>
          <button class="relative inline-flex items-center h-7 rounded-full w-12 transition-colors focus:outline-none bg-blue-600 text-white shadow-sm hover:bg-blue-700 shadow-lg shadow-purple-500/30 ring-2 ring-purple-500/20">
            <span class="inline-block w-5 h-5 transform translate-x-6 bg-white rounded-full transition-transform shadow-sm"></span>
          </button>
          <span class="text-[10px] text-purple-300 font-bold uppercase">AI</span>
        </div>
      </div>

      <!-- Messages Area -->
      <div class="flex-grow p-4 overflow-y-auto space-y-5 flex flex-col scrollbar-none [scrollbar-width:none] pb-6">
        <div 
          v-for="msg in messages" 
          :key="msg.id" 
          :class="[
            'max-w-[85%] p-4 rounded-3xl shadow-sm text-[15px] leading-relaxed relative',
            msg.role === 'user' ? 'bg-white border border-slate-200 shadow-sm text-slate-700 self-start rounded-tl-sm' : 'bg-blue-600 text-white shadow-sm hover:bg-blue-700 self-end rounded-tr-sm shadow-lg shadow-purple-500/20'
          ]"
        >
          <p class="whitespace-pre-wrap">{{ msg.content }}</p>
          <div class="mt-1 flex justify-end">
            <span class="text-[10px] opacity-70 font-medium" :class="msg.role === 'user' ? 'text-slate-600' : 'text-slate-900/80'">{{ new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</span>
          </div>
          
          <!-- Tool Calls Indicator -->
          <div v-if="msg.tool_calls && msg.role !== 'user'" class="mt-3 pt-3 border-t border-white/20 flex items-center gap-2">
             <div class="w-4 h-4 rounded-full bg-white/20 flex items-center justify-center animate-pulse">
               <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
             </div>
             <span class="text-[10px] font-bold uppercase tracking-wider text-slate-900">Action Executed</span>
          </div>
        </div>
        <!-- Spacer for composer -->
        <div class="h-4 shrink-0"></div>
      </div>

      <!-- Composer Area -->
      <div class="p-3 bg-white border border-slate-200 shadow-sm border-t border-slate-200 rounded-t-[32px] z-20 pb-safe">
        <div class="flex items-end gap-2 bg-slate-50 rounded-3xl border border-slate-200 p-2 focus-within:ring-1 focus-within:ring-purple-500/50 transition-all">
          <textarea 
            v-model="composer"
            class="flex-grow bg-transparent p-2 text-sm text-slate-900 placeholder-slate-500 outline-none resize-none max-h-32 min-h-[40px] scrollbar-none [scrollbar-width:none]"
            placeholder="Message..."
            rows="1"
            @keyup.enter.ctrl="sendMessage"
          ></textarea>
          <button 
            @click="sendMessage"
            :disabled="isSending || !composer.trim()"
            class="h-10 w-10 shrink-0 rounded-full bg-blue-600 text-white shadow-sm hover:bg-blue-700 flex items-center justify-center text-slate-900 shadow-lg shadow-purple-500/20 disabled:opacity-50 disabled:grayscale transition-all active:scale-95"
          >
            <svg v-if="!isSending" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5 ml-1"><path d="M3.478 2.404a.75.75 0 00-.926.941l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.404z" /></svg>
            <div v-else class="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin"></div>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
