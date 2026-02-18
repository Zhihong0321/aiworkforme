<script setup>
import { ref, onMounted } from 'vue'

const leads = ref([])
const selectedLeadId = ref(null)

// Placeholder for fetching due leads
onMounted(() => {
  leads.value = [
    { id: 1, name: 'John Doe', stage: 'NEW', last_msg: 'Interested in solar', time: '2m ago' },
    { id: 2, name: 'Jane Smith', stage: 'CONTACTED', last_msg: 'When can we meet?', time: '15m ago' }
  ]
})
</script>

<template>
  <div class="flex h-[calc(100-4rem)] overflow-hidden">
    <!-- Lead List -->
    <div class="w-80 border-r border-[var(--border)] bg-white overflow-y-auto">
      <div class="p-4 border-b border-[var(--border)]">
        <h2 class="font-bold">Active Conversations</h2>
      </div>
      <div 
        v-for="lead in leads" 
        :key="lead.id"
        @click="selectedLeadId = lead.id"
        class="p-4 border-b border-[var(--border)] cursor-pointer hover:bg-gray-50"
        :class="{ 'bg-[var(--accent-soft)]': selectedLeadId === lead.id }"
      >
        <div class="flex justify-between items-start mb-1">
          <span class="font-semibold text-sm">{{ lead.name }}</span>
          <span class="text-[10px] text-[var(--muted)]">{{ lead.time }}</span>
        </div>
        <div class="text-xs text-[var(--muted)] truncate">{{ lead.last_msg }}</div>
        <div class="mt-2">
          <span class="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 font-bold border border-blue-100">
            {{ lead.stage }}
          </span>
        </div>
      </div>
    </div>

    <!-- Chat Area -->
    <div class="flex-grow flex flex-col bg-gray-50">
      <div v-if="selectedLeadId" class="flex flex-col h-full">
        <!-- Header -->
        <div class="p-4 border-b border-[var(--border)] bg-white flex justify-between items-center">
          <div>
            <span class="font-bold">Chat with Lead #{{ selectedLeadId }}</span>
          </div>
          <div class="flex gap-2">
            <button class="text-sm px-3 py-1 border border-red-200 text-red-600 rounded">Takeover</button>
            <button class="text-sm px-3 py-1 bg-black text-white rounded">Resolve</button>
          </div>
        </div>

        <!-- Messages -->
        <div class="flex-grow p-4 overflow-y-auto space-y-4">
          <div class="self-start max-w-[80%] bg-white p-3 rounded-lg border border-[var(--border)] shadow-sm">
            <p class="text-sm">Hello, I saw your ad for solar panels. Can you help?</p>
            <span class="text-[10px] text-[var(--muted)]">Lead • 10:30 AM</span>
          </div>
          <div class="self-end ml-auto max-w-[80%] bg-[var(--accent-soft)] p-3 rounded-lg border border-[#ff8200] shadow-sm">
            <p class="text-sm">Hi! Absolutely. I can walk you through our current options. Are you looking for residential or commercial?</p>
            <span class="text-[10px] text-[var(--muted)]">AI Agent • 10:31 AM</span>
          </div>
        </div>

        <!-- Composer -->
        <div class="p-4 bg-white border-t border-[var(--border)]">
          <textarea 
            class="w-full p-2 border border-[var(--border)] rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-black"
            placeholder="Type a message or use AI suggest..."
            rows="3"
          ></textarea>
          <div class="mt-2 flex justify-between items-center">
            <span class="text-xs text-[var(--muted)] italic">AI Auto-reply is ACTIVE</span>
            <button class="bg-black text-white px-4 py-2 rounded text-sm font-bold">Send Message</button>
          </div>
        </div>
      </div>
      <div v-else class="flex-grow flex items-center justify-center text-[var(--muted)]">
        Select a conversation to start
      </div>
    </div>
  </div>
</template>
