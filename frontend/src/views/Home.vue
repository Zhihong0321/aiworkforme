<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { store } from '../store'
import { request } from '../services/api'

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
    { name: 'Inbox', path: '/inbox', icon: 'inbox', tone: 'accent' },
    { name: 'Add Lead', path: '/leads', icon: 'person_add', tone: 'sage' },
    { name: 'Train Brain', path: '/knowledge', icon: 'psychology', tone: 'sand' },
    { name: 'Playground', path: '/playground', icon: 'play_circle', tone: 'clay' }
]

const actionToneClass = (tone) => {
    const tones = {
        accent: 'border-primary/10 bg-primary/10 text-primary',
        sage: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300',
        sand: 'border-warning/20 bg-warning/10 text-warning',
        clay: 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-500/20 dark:bg-orange-500/10 dark:text-orange-300'
    }
    return tones[tone] || tones.accent
}

const activityToneClass = (tone) => {
    const tones = {
        green: 'bg-success/10 text-success',
        purple: 'bg-primary/10 text-primary',
        blue: 'bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300',
        slate: 'bg-surface-muted text-ink-muted'
    }
    return tones[tone] || tones.slate
}

const navigateTo = (path) => {
    router.push(path)
}
</script>

<template>
  <div class="mobile-shell relative mx-auto flex min-h-[calc(100vh-76px)] w-full max-w-md flex-col overflow-hidden rounded-[2rem] border border-line/60 bg-background-light/70 text-ink shadow-panel">
    
    <main class="flex-1 pb-24 overflow-y-auto scrollbar-none">
        
        <div class="px-5 py-6 pb-3">
             <p class="text-[11px] font-bold uppercase tracking-[0.26em] text-ink-subtle">Overview</p>
             <h1 class="mt-2 text-3xl font-bold tracking-tight text-ink">Control Center</h1>
             <p class="mt-2 text-sm text-ink-muted">Your mobile snapshot of agent health, leads, and next actions.</p>
        </div>

        <div v-if="isLoading" class="flex justify-center py-20">
            <span class="material-symbols-outlined animate-spin text-3xl text-primary">sync</span>
        </div>

        <template v-else>
            <section class="p-4 grid grid-cols-1 gap-3">
                <div class="relative overflow-hidden rounded-[1.75rem] border border-primary/15 bg-[linear-gradient(145deg,_rgb(var(--panel-elevated-rgb)_/_0.94),_rgb(var(--accent-soft-rgb)_/_0.88))] p-6 shadow-panel">
                    <span class="absolute -right-4 -top-4 h-32 w-32 rounded-full bg-primary/15 blur-3xl"></span>
                    
                    <div class="relative z-10 flex items-center justify-between border-b border-primary/10 pb-4">
                        <div class="flex flex-col">
                            <p class="mb-1 text-[10px] font-bold uppercase tracking-[0.22em] text-primary/80">System Health</p>
                            <p class="flex items-center gap-2 text-xl font-bold text-ink">
                                <span class="h-2.5 w-2.5 rounded-full bg-success shadow-[0_0_12px_rgb(var(--success-rgb)_/_0.4)]"></span>
                                Optimal
                            </p>
                        </div>
                        <div class="flex size-12 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary backdrop-blur-sm">
                            <span class="material-symbols-outlined text-3xl">verified_user</span>
                        </div>
                    </div>
                    
                    <div class="relative z-10 grid grid-cols-2 gap-4">
                        <div class="flex flex-col">
                            <p class="mb-1 text-xs font-bold uppercase tracking-[0.2em] text-ink-muted">Active Agents</p>
                            <p class="text-2xl font-bold text-ink">{{ store.activeAgentId ? '1' : '0' }}</p>
                        </div>
                        <div class="flex flex-col border-l border-line/80 pl-4">
                            <p class="mb-1 text-xs font-bold uppercase tracking-[0.2em] text-ink-muted">Total Leads</p>
                            <p class="text-2xl font-bold text-ink">{{ dashboardStats.totalLeads }}</p>
                        </div>
                    </div>
                </div>
            </section>

            <section class="p-4 pt-2">
                <h2 class="mb-3 px-1 text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Quick Actions</h2>
                <div class="grid grid-cols-2 gap-3">
                    <button 
                        v-for="action in quickActions" 
                        :key="action.name"
                        @click="navigateTo(action.path)"
                        class="surface-card flex flex-col items-center justify-center gap-3 rounded-[1.5rem] p-6 text-center transition-all active:scale-95 hover:-translate-y-0.5"
                    >
                        <div class="flex h-14 w-14 items-center justify-center rounded-2xl border shadow-inner" :class="actionToneClass(action.tone)">
                            <span class="material-symbols-outlined text-[28px]">{{ action.icon }}</span>
                        </div>
                        <span class="text-sm font-bold text-ink">{{ action.name }}</span>
                    </button>
                </div>
            </section>

            <section class="p-4">
                <div class="mb-4 flex items-center justify-between px-1">
                    <h2 class="text-[11px] font-bold uppercase tracking-[0.24em] text-ink-subtle">Activity Log</h2>
                    <button class="text-[11px] font-bold tracking-[0.2em] text-primary hover:underline">View All</button>
                </div>
                
                <div class="space-y-2">
                    <div 
                        v-for="activity in dashboardStats.recentActivity" 
                        :key="activity.id"
                        class="surface-card flex items-center gap-4 rounded-[1.4rem] p-4 transition-colors"
                    >
                        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl shadow-inner" :class="activityToneClass(activity.color)">
                            <span class="material-symbols-outlined text-xl">{{ activity.icon }}</span>
                        </div>
                        
                        <div class="flex-1 min-w-0">
                            <p class="truncate text-sm font-bold text-ink">{{ activity.title }}</p>
                            <p class="mt-0.5 truncate text-xs font-medium text-ink-muted">{{ activity.desc }}</p>
                        </div>
                        <p class="whitespace-nowrap text-[10px] font-bold uppercase tracking-[0.2em] text-ink-subtle">{{ activity.time }}</p>
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
