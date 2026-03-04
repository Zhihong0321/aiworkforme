<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { store } from '../store'
import { request } from '../services/api'
import TuiLoader from '../components/ui/TuiLoader.vue'

const router = useRouter()
const isLoading = ref(true)
const dashboardStats = ref({
    activeAgents: 1,
    totalLeads: 0,
    recentActivity: [
        { id: 1, title: 'System health check', desc: 'All modules functioning normally', time: 'Just now', icon: 'settings', color: 'slate' }
    ]
})

onMounted(async () => {
    isLoading.value = true
    try {
        // Fetch some basic stats
        // We can fetch leads to get the count
        let agentId = store.activeAgentId
        if (agentId) {
             const leads = await request(`/agents/${agentId}/leads`)
             dashboardStats.value.totalLeads = leads ? leads.length : 0
        }
        // Simulated activity for now
        dashboardStats.value.recentActivity = [
            { id: 1, title: store.activeAgentId ? 'Agent Ready' : 'System Initialized', desc: store.activeAgentId ? `Agent #${store.activeAgentId} is active` : 'No agent selected yet', time: 'Just now', icon: 'verified', color: 'green' },
            { id: 2, title: 'CRM Integration', desc: 'Ready for connection', time: '1h ago', icon: 'hub', color: 'purple' },
            { id: 3, title: 'Knowledge Base', desc: 'Awaiting training data', time: '2h ago', icon: 'school', color: 'blue' }
        ]
    } catch (e) {
        console.error('Failed to load dashboard stats', e)
    } finally {
        isLoading.value = false
    }
})

const quickActions = [
    { name: 'Inbox', path: '/inbox', icon: 'inbox', colorClass: 'bg-blue-50 dark:bg-blue-900/30 text-primary' },
    { name: 'Add Lead', path: '/leads', icon: 'person_add', colorClass: 'bg-green-50 dark:bg-green-900/30 text-green-600' },
    { name: 'Train Brain', path: '/knowledge', icon: 'psychology', colorClass: 'bg-purple-50 dark:bg-purple-900/30 text-purple-600' },
    { name: 'Playground', path: '/playground', icon: 'play_circle', colorClass: 'bg-orange-50 dark:bg-orange-900/30 text-orange-600' }
]

const navigateTo = (path) => {
    router.push(path)
}
</script>

<template>
  <div class="flex flex-col min-h-[calc(100vh-64px)] w-full max-w-md mx-auto relative text-slate-900 dark:text-slate-100 bg-background-light dark:bg-background-dark overflow-hidden">
    
    <main class="flex-1 pb-24 overflow-y-auto scrollbar-none">
        
        <!-- Header area inside page to match typical iOS page structures if TopNav is transparent -->
        <div class="px-4 py-6 pb-2">
             <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Overview</h1>
        </div>

        <div v-if="isLoading" class="flex justify-center py-20">
            <span class="material-symbols-outlined animate-spin text-3xl text-primary">sync</span>
        </div>

        <template v-else>
            <!-- Status Cards -->
            <section class="p-4 grid grid-cols-1 gap-3">
                <div class="flex flex-col gap-4 rounded-3xl p-6 bg-primary/10 border border-primary/20 shadow-sm relative overflow-hidden">
                    <span class="absolute -right-4 -top-4 bg-primary/20 w-32 h-32 rounded-full blur-3xl"></span>
                    
                    <div class="flex items-center justify-between border-b border-primary/10 pb-4 relative z-10">
                        <div class="flex flex-col">
                            <p class="text-[10px] font-bold uppercase tracking-widest text-primary/80 mb-1">System Health</p>
                            <p class="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
                                Optimal
                            </p>
                        </div>
                        <div class="size-12 rounded-full bg-primary/20 flex items-center justify-center text-primary backdrop-blur-sm border border-primary/30">
                            <span class="material-symbols-outlined text-3xl">verified_user</span>
                        </div>
                    </div>
                    
                    <div class="grid grid-cols-2 gap-4 relative z-10">
                        <div class="flex flex-col">
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-1">Active Agents</p>
                            <p class="text-2xl font-bold text-slate-900 dark:text-white">{{ store.activeAgentId ? '1' : '0' }}</p>
                        </div>
                        <div class="flex flex-col border-l border-slate-200 dark:border-slate-700/50 pl-4">
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-1">Total Leads</p>
                            <p class="text-2xl font-bold text-slate-900 dark:text-white">{{ dashboardStats.totalLeads }}</p>
                        </div>
                    </div>
                </div>
            </section>

            <!-- 2x2 Grid of Buttons -->
            <section class="p-4 pt-2">
                <h2 class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3 px-1">Quick Actions</h2>
                <div class="grid grid-cols-2 gap-3">
                    <button 
                        v-for="action in quickActions" 
                        :key="action.name"
                        @click="navigateTo(action.path)"
                        class="flex flex-col items-center justify-center gap-3 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/80 p-6 shadow-sm hover:shadow-md active:scale-95 transition-all text-center"
                    >
                        <div class="flex h-14 w-14 items-center justify-center rounded-2xl shadow-inner border border-white/50 dark:border-slate-700/50" :class="action.colorClass">
                            <span class="material-symbols-outlined text-[28px]">{{ action.icon }}</span>
                        </div>
                        <span class="text-sm font-bold text-slate-800 dark:text-slate-200">{{ action.name }}</span>
                    </button>
                </div>
            </section>

            <!-- Recent Activity -->
            <section class="p-4">
                <div class="flex items-center justify-between mb-4 px-1">
                    <h2 class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Activity Log</h2>
                    <button class="text-primary text-[11px] font-bold tracking-wider hover:underline">View All</button>
                </div>
                
                <div class="space-y-2">
                    <div 
                        v-for="activity in dashboardStats.recentActivity" 
                        :key="activity.id"
                        class="flex items-center gap-4 p-4 rounded-2xl bg-white dark:bg-slate-800/80 border border-slate-100 dark:border-slate-800 hover:border-slate-200 dark:hover:border-slate-700 transition-colors shadow-sm"
                    >
                        <!-- Dynamic Color formatting -->
                        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl shadow-inner" 
                            :class="{
                                'bg-blue-50 dark:bg-blue-900/40 text-blue-600': activity.color === 'blue',
                                'bg-green-50 dark:bg-green-900/40 text-green-600': activity.color === 'green',
                                'bg-purple-50 dark:bg-purple-900/40 text-purple-600': activity.color === 'purple',
                                'bg-slate-50 dark:bg-slate-900/60 text-slate-600': activity.color === 'slate'
                            }"
                        >
                            <span class="material-symbols-outlined text-xl">{{ activity.icon }}</span>
                        </div>
                        
                        <div class="flex-1 min-w-0">
                            <p class="text-sm font-bold text-slate-900 dark:text-white truncate">{{ activity.title }}</p>
                            <p class="text-xs font-medium text-slate-500 dark:text-slate-400 truncate mt-0.5">{{ activity.desc }}</p>
                        </div>
                        <p class="text-[10px] font-bold uppercase tracking-wider text-slate-400 whitespace-nowrap">{{ activity.time }}</p>
                    </div>
                </div>
            </section>
        </template>
    </main>
  </div>
</template>

<style scoped>
.scrollbar-none::-webkit-scrollbar {
  display: none;
}
.scrollbar-none {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
