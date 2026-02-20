<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { 
  Calendar as CalendarIcon, 
  Settings, 
  Plus, 
  ChevronLeft, 
  ChevronRight, 
  Trash2, 
  Clock, 
  MapPin,
  CheckCircle,
  XCircle,
  AlertCircle
} from 'lucide-vue-next'
import { calendarService } from '../services/calendar'
import { useTheme } from '../composables/theme'
import { store } from '../store'

const { theme } = useTheme()
const isDark = computed(() => theme.value === 'dark')

const activeTab = ref('calendar') // 'calendar' or 'config'
const currentMonth = ref(new Date())
const events = ref([])
const config = ref({
  meeting_types: [],
  available_regions: [],
  timezone: 'UTC'
})

const isLoading = ref(false)
const showEventModal = ref(false)
const selectedEvent = ref(null)
const newEvent = ref({
  title: '',
  start_time: '',
  end_time: '',
  event_type: 'appointment',
  meeting_type_name: '',
  region: '',
  description: ''
})

// Fetch data
const fetchData = async () => {
  isLoading.value = true
  try {
    const [conf, evs] = await Promise.all([
      calendarService.getConfig(),
      calendarService.getEvents()
    ])
    config.value = conf
    events.value = evs
    
    // Set default values for new event based on config
    if (config.value.meeting_types.length > 0) {
      newEvent.value.meeting_type_name = config.value.meeting_types[0].name
    }
    if (config.value.available_regions.length > 0) {
      newEvent.value.region = config.value.available_regions[0]
    }
  } catch (err) {
    console.error('Failed to fetch calendar data:', err)
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchData)

// Calendar Navigation
const nextMonth = () => {
  currentMonth.value = new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() + 1, 1)
}
const prevMonth = () => {
  currentMonth.value = new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() - 1, 1)
}

const calendarDays = computed(() => {
  const year = currentMonth.value.getFullYear()
  const month = currentMonth.value.getMonth()
  
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  
  const startOffset = firstDay.getDay()
  const totalDays = lastDay.getDate()
  
  const days = []
  
  // Padding for previous month
  const prevMonthLastDay = new Date(year, month, 0).getDate()
  for (let i = startOffset - 1; i >= 0; i--) {
    days.push({
      date: new Date(year, month - 1, prevMonthLastDay - i),
      currentMonth: false
    })
  }
  
  // Current month days
  for (let i = 1; i <= totalDays; i++) {
    days.push({
      date: new Date(year, month, i),
      currentMonth: true
    })
  }
  
  // Padding for next month
  const remaining = 42 - days.length
  for (let i = 1; i <= remaining; i++) {
    days.push({
      date: new Date(year, month + 1, i),
      currentMonth: false
    })
  }
  
  return days
})

const getEventsForDay = (date) => {
  return events.value.filter(e => {
    const d = new Date(e.start_time)
    return d.toDateString() === date.toDateString()
  })
}

// Config Management
const addMeetingType = () => {
  config.value.meeting_types.push({ name: '', duration_minutes: 30 })
}
const removeMeetingType = (index) => {
  config.value.meeting_types.splice(index, 1)
}
const addRegion = () => {
  config.value.available_regions.push('')
}
const removeRegion = (index) => {
  config.value.available_regions.splice(index, 1)
}

const saveConfig = async () => {
  try {
    isLoading.value = true
    await calendarService.updateConfig(config.value)
    alert('Settings saved successfully')
  } catch (err) {
    alert('Failed to save settings: ' + err.message)
  } finally {
    isLoading.value = false
  }
}

// Event Management
const openAddModal = (date = null) => {
  const now = date ? new Date(date) : new Date()
  now.setHours(9, 0, 0, 0)
  
  const end = new Date(now)
  end.setMinutes(end.getMinutes() + 30)
  
  newEvent.value = {
    title: '',
    start_time: now.toISOString().slice(0, 16),
    end_time: end.toISOString().slice(0, 16),
    event_type: 'appointment',
    meeting_type_name: config.value.meeting_types[0]?.name || '',
    region: config.value.available_regions[0] || '',
    description: ''
  }
  selectedEvent.value = null
  showEventModal.value = true
}

const handleCreateEvent = async () => {
  try {
    isLoading.value = true
    await calendarService.createEvent(newEvent.value)
    showEventModal.value = false
    fetchData()
  } catch (err) {
    alert('Failed to create event: ' + err.message)
  } finally {
    isLoading.value = false
  }
}

const handleDeleteEvent = async (id) => {
  if (!confirm('Are you sure you want to delete this event?')) return
  try {
    isLoading.value = true
    await calendarService.deleteEvent(id)
    fetchData()
  } catch (err) {
    alert('Failed to delete event')
  } finally {
    isLoading.value = false
  }
}

</script>

<template>
  <div class="min-h-[calc(100vh-64px)] w-full bg-onyx font-inter text-slate-200 pb-20 flex flex-col relative overflow-hidden">
    <!-- Aurora Background Effect -->
    <div class="absolute inset-0 bg-mobile-aurora z-0 pointer-events-none opacity-40"></div>

    <!-- Header Section -->
    <div class="p-5 border-b border-slate-800/50 glass-panel-light rounded-b-[2rem] sticky top-0 z-30 mb-2 relative">
       <div class="flex flex-col gap-1 mb-4">
         <h1 class="text-3xl font-semibold text-white tracking-tight">Calendar</h1>
         <p class="text-[10px] text-aurora font-bold uppercase tracking-widest mt-1">Availability & AI Scheduling</p>
       </div>
       
       <!-- Tab Navigation (Mobile friendly Segmented Control) -->
       <div class="flex p-1 bg-slate-900/60 rounded-xl border border-slate-700/50 backdrop-blur-md relative z-10 w-full max-w-sm mx-auto">
         <button 
            @click="activeTab = 'calendar'"
            class="flex-1 py-2 text-xs font-bold rounded-lg transition-all duration-300 relative"
            :class="activeTab === 'calendar' ? 'text-white bg-slate-800 shadow-md border border-slate-700/50' : 'text-slate-500 hover:text-slate-300'"
         >
            Calendar View
         </button>
         <button 
            @click="activeTab = 'config'"
            class="flex-1 py-2 text-xs font-bold rounded-lg transition-all duration-300 relative"
            :class="activeTab === 'config' ? 'text-white bg-slate-800 shadow-md border border-slate-700/50' : 'text-slate-500 hover:text-slate-300'"
         >
            Preferences
         </button>
       </div>
    </div>

    <!-- Main Content Area -->
    <div class="flex-grow px-4 pb-10 relative z-10 w-full max-w-5xl mx-auto">
       
      <!-- Loading State -->
      <div v-if="isLoading" class="flex justify-center items-center py-20">
         <div class="w-8 h-8 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin"></div>
      </div>

      <!-- ==================== CALENDAR TAB ==================== -->
      <div v-else-if="activeTab === 'calendar'" class="space-y-5 animate-fade-in mt-2">
         
         <!-- Top Stats & Action (Mobile Stacked) -->
         <div class="grid grid-cols-2 gap-4">
            <div class="glass-panel p-4 rounded-3xl border border-slate-700/50 relative overflow-hidden">
               <div class="absolute -right-4 -top-4 w-16 h-16 bg-blue-500/20 blur-xl rounded-full"></div>
               <h3 class="text-[9px] font-black uppercase tracking-widest text-slate-400 mb-2 relative z-10">Total Appointments</h3>
               <div class="text-3xl font-black text-white tracking-tight relative z-10">{{ events.length }}</div>
               <p class="text-[9px] font-bold text-blue-400 uppercase tracking-widest relative z-10 mt-1">This Month</p>
            </div>
            <button 
               @click="openAddModal()"
               class="glass-panel p-4 rounded-3xl border border-dashed border-slate-500/50 hover:border-purple-500/50 active:scale-95 transition-all outline-none flex flex-col items-center justify-center text-center group bg-slate-800/20"
            >
               <div class="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center mb-2 group-hover:bg-purple-500/20 transition-colors">
                  <Plus class="w-4 h-4 text-slate-300 group-hover:text-purple-400 transition-colors" />
               </div>
               <span class="text-[10px] font-black uppercase tracking-widest text-slate-400 group-hover:text-white transition-colors">Add Block</span>
            </button>
         </div>

         <!-- Upcoming Mobile List (If any exist) -->
         <div v-if="events.length > 0" class="glass-panel p-4 rounded-3xl border border-slate-700/50 mb-2">
            <h3 class="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-3 px-1">Upcoming Events (Top 3)</h3>
            <div class="space-y-2">
               <div v-for="event in events.slice(0, 3)" :key="event.id" class="bg-slate-800/40 border border-slate-700/30 rounded-2xl p-3 flex gap-3 relative overflow-hidden group">
                  <div class="w-1 rounded-full absolute left-0 top-3 bottom-3" :class="event.event_type === 'appointment' ? 'bg-blue-500' : 'bg-red-500'"></div>
                  <div class="pl-2 flex-grow min-w-0">
                     <div class="text-[13px] font-bold text-white uppercase tracking-tight truncate">{{ event.title }}</div>
                     <div class="text-[10px] text-slate-400 font-semibold uppercase mt-0.5">{{ new Date(event.start_time).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}) }}</div>
                  </div>
                  <button @click="handleDeleteEvent(event.id)" class="shrink-0 w-8 h-8 rounded-full bg-red-500/10 text-red-400 flex items-center justify-center active:bg-red-500/20 transition-colors">
                     <Trash2 class="w-3.5 h-3.5" />
                  </button>
               </div>
            </div>
         </div>

         <!-- Main Calendar Grid -->
         <div class="glass-panel p-4 rounded-[2rem] border border-slate-700/50 bg-slate-900/40">
            <!-- Header Controls -->
            <div class="flex items-center justify-between mb-4 px-2">
               <h2 class="text-base font-bold text-white tracking-tight">
                 {{ currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' }) }}
               </h2>
               <div class="flex items-center gap-1">
                 <button @click="prevMonth" class="p-1.5 rounded-full bg-slate-800 text-slate-400 hover:text-white border border-slate-700/50 active:scale-90 transition-all">
                   <ChevronLeft class="w-5 h-5" />
                 </button>
                 <button @click="nextMonth" class="p-1.5 rounded-full bg-slate-800 text-slate-400 hover:text-white border border-slate-700/50 active:scale-90 transition-all">
                   <ChevronRight class="w-5 h-5" />
                 </button>
               </div>
            </div>

            <!-- CSS Grid Calendar (Optimized for Mobile) -->
            <div class="grid grid-cols-7 gap-1">
               <div v-for="day in ['S', 'M', 'T', 'W', 'T', 'F', 'S']" :key="day" class="text-center text-[10px] font-black uppercase text-slate-500 pb-2">
                 {{ day }}
               </div>
               
               <div 
                 v-for="(day, idx) in calendarDays" 
                 :key="idx"
                 class="aspect-square flex flex-col p-1 rounded-xl border border-transparent relative group"
                 :class="[
                    !day.currentMonth ? 'opacity-20 pointer-events-none' : 'hover:bg-slate-800/50 hover:border-slate-700/50 cursor-pointer active:scale-95 transition-all',
                    idx % 2 === 0 ? 'bg-slate-800/10' : ''
                 ]"
                 @click="day.currentMonth ? openAddModal(day.date) : null"
               >
                 <span class="text-[10px] font-bold text-slate-300 ml-1">{{ day.date.getDate() }}</span>
                 
                 <!-- Event Indicators (Dots on mobile to save space) -->
                 <div class="flex-grow flex flex-wrap gap-[2px] items-end justify-start pl-1 pb-1 overflow-hidden">
                    <span 
                       v-for="(event, eIdx) in getEventsForDay(day.date).slice(0, 3)" 
                       :key="eIdx" 
                       class="w-1.5 h-1.5 rounded-full"
                       :class="event.event_type === 'appointment' ? 'bg-blue-500' : 'bg-red-500'"
                    ></span>
                    <span v-if="getEventsForDay(day.date).length > 3" class="text-[8px] text-slate-500 font-bold leading-none">+</span>
                 </div>
               </div>
            </div>
         </div>
      </div>

      <!-- ==================== SETTINGS TAB ==================== -->
      <div v-else-if="activeTab === 'config'" class="space-y-6 animate-fade-in mt-2">
         
         <!-- Meeting Types Card -->
         <div class="glass-panel p-5 rounded-[2rem] border border-slate-700/50">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
                <Clock class="w-3.5 h-3.5" /> Meeting Types
              </h3>
              <button @click="addMeetingType" class="w-7 h-7 rounded-full bg-slate-800 border border-slate-600 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-700 transition-colors">
                <Plus class="w-4 h-4" />
              </button>
            </div>
            
            <div class="space-y-3">
              <div v-if="config.meeting_types.length === 0" class="text-xs text-slate-500 italic py-2">No meeting types defined.</div>
              <div v-for="(type, index) in config.meeting_types" :key="index" class="flex gap-2 items-center bg-slate-900/50 p-1.5 rounded-2xl border border-slate-700/50">
                <input 
                   v-model="type.name" 
                   placeholder="e.g. Discovery Call" 
                   class="flex-1 bg-slate-800/80 border border-slate-700/50 rounded-xl px-3 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 transition-colors min-w-0"
                />
                <div class="relative w-20 shrink-0">
                   <span class="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-bold text-slate-500">min</span>
                   <input 
                      v-model.number="type.duration_minutes" 
                      type="number" 
                      class="w-full bg-slate-800/80 border border-slate-700/50 rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:border-purple-500 transition-colors"
                   />
                </div>
                <button @click="removeMeetingType(index)" class="shrink-0 p-2.5 rounded-xl text-red-400 hover:bg-red-500/10 transition-colors">
                  <Trash2 class="w-4 h-4" />
                </button>
              </div>
            </div>
         </div>

         <!-- Available Regions Card -->
         <div class="glass-panel p-5 rounded-[2rem] border border-slate-700/50">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
                <MapPin class="w-3.5 h-3.5" /> Available Regions
              </h3>
              <button @click="addRegion" class="w-7 h-7 rounded-full bg-slate-800 border border-slate-600 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-700 transition-colors">
                <Plus class="w-4 h-4" />
              </button>
            </div>
            
            <div class="space-y-3">
              <div v-if="config.available_regions.length === 0" class="text-xs text-slate-500 italic py-2">No regions defined.</div>
              <div v-for="(region, index) in config.available_regions" :key="index" class="flex gap-2 items-center bg-slate-900/50 p-1.5 rounded-2xl border border-slate-700/50">
                <input 
                   v-model="config.available_regions[index]" 
                   placeholder="e.g. US-East" 
                   class="flex-1 bg-slate-800/80 border border-slate-700/50 rounded-xl px-3 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 transition-colors"
                />
                <button @click="removeRegion(index)" class="shrink-0 p-2.5 rounded-xl text-red-400 hover:bg-red-500/10 transition-colors">
                  <Trash2 class="w-4 h-4" />
                </button>
              </div>
            </div>
         </div>

         <!-- System Timezone Card -->
         <div class="glass-panel p-5 rounded-[2rem] border border-slate-700/50">
             <h3 class="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2 mb-3">
                <Settings class="w-3.5 h-3.5" /> System Timezone
             </h3>
             <div class="relative">
                <select v-model="config.timezone" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3.5 text-sm font-semibold text-white focus:outline-none focus:border-purple-500 transition-colors appearance-none">
                  <option value="UTC">UTC (Universal Time)</option>
                  <option value="Asia/Singapore">Asia/Singapore (SGT)</option>
                  <option value="Asia/Kuala_Lumpur">Asia/Kuala_Lumpur (MYT)</option>
                  <option value="America/New_York">America/New_York (EST)</option>
                  <option value="Europe/London">Europe/London (GMT)</option>
                </select>
                <div class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                   <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                </div>
             </div>
         </div>

         <!-- Save Button (Sticky bottom on mobile) -->
         <div class="pt-4 pb-safe bg-onyx/80 backdrop-blur-md sticky bottom-16 z-20 mx--4 px-4 sm:mx-0 sm:px-0 sm:static sm:bg-transparent -mx-4">
            <button 
               @click="saveConfig"
               :disabled="isLoading"
               class="w-full py-4 bg-aurora-gradient text-white rounded-2xl font-bold uppercase tracking-widest text-sm shadow-lg shadow-purple-500/20 active:scale-[0.98] disabled:opacity-50 transition-all flex items-center justify-center gap-2"
            >
               <span v-if="!isLoading">Save Configuration</span>
               <div v-else class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            </button>
         </div>
      </div>
    </div>

    <!-- Modals Overlay (Mobile Bottom Sheet Style) -->
    <transition name="fade">
      <div v-if="showEventModal" class="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-sm">
        
        <div class="w-full max-w-md bg-onyx sm:rounded-3xl rounded-t-[2rem] border border-slate-800 shadow-2xl overflow-hidden flex flex-col slide-up max-h-[90vh]">
           
           <div class="p-5 border-b border-slate-800 flex justify-between items-center sticky top-0 bg-onyx/90 backdrop-blur-md z-10">
              <h2 class="text-lg font-bold text-white tracking-tight">Manual Block</h2>
              <button @click="showEventModal = false" class="w-8 h-8 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center hover:bg-slate-700 hover:text-white">
                 <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
           </div>

           <div class="p-5 overflow-y-auto scrollbar-none space-y-5">
              
              <!-- Block Title -->
              <div class="space-y-1.5">
                <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Block Title</label>
                <input v-model="newEvent.title" type="text" placeholder="e.g. Out of Office" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3.5 text-sm font-semibold text-white focus:outline-none focus:border-purple-500 transition-colors" />
              </div>

              <!-- Date / Time Grid -->
              <div class="grid grid-cols-2 gap-3">
                 <div class="space-y-1.5">
                   <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Start Time</label>
                   <!-- Mobile browsers display native date/time pickers nicely here -->
                   <input v-model="newEvent.start_time" type="datetime-local" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-3 py-3 text-[13px] font-semibold text-white focus:outline-none focus:border-purple-500 transition-colors appearance-none" />
                 </div>
                 <div class="space-y-1.5">
                   <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">End Time</label>
                   <input v-model="newEvent.end_time" type="datetime-local" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-3 py-3 text-[13px] font-semibold text-white focus:outline-none focus:border-purple-500 transition-colors appearance-none" />
                 </div>
              </div>

              <!-- Segmented Control for Type -->
              <div class="space-y-1.5">
                 <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Availability Type</label>
                 <div class="flex p-1 bg-slate-900 border border-slate-700/80 rounded-2xl">
                    <button 
                       @click="newEvent.event_type = 'appointment'"
                       class="flex-1 py-2.5 text-[11px] font-bold uppercase tracking-widest rounded-xl transition-all"
                       :class="newEvent.event_type === 'appointment' ? 'bg-blue-500 text-white shadow-md' : 'text-slate-500 hover:text-slate-300'"
                    >
                       Meeting
                    </button>
                    <button 
                       @click="newEvent.event_type = 'unavailable'"
                       class="flex-1 py-2.5 text-[11px] font-bold uppercase tracking-widest rounded-xl transition-all"
                       :class="newEvent.event_type === 'unavailable' ? 'bg-red-500 text-white shadow-md' : 'text-slate-500 hover:text-slate-300'"
                    >
                       Blocked
                    </button>
                 </div>
              </div>
           </div>

           <!-- Submit btn -->
           <div class="p-5 border-t border-slate-800 bg-slate-900/50 pb-safe">
              <button 
                 @click="handleCreateEvent"
                 :disabled="isLoading"
                 class="w-full py-4 bg-white text-slate-900 rounded-2xl font-black uppercase tracking-widest text-xs shadow-lg active:scale-[0.98] disabled:opacity-50 transition-all flex justify-center items-center gap-2"
              >
                 <span v-if="!isLoading">Confirm Block</span>
                 <div v-else class="w-4 h-4 border-2 border-slate-900/30 border-t-slate-900 rounded-full animate-spin"></div>
              </button>
           </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
/* Hide scrollbar but keep scroll functionality */
.scrollbar-none::-webkit-scrollbar {
  display: none;
}
.scrollbar-none {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* Animations */
.animate-fade-in {
  animation: fadeIn 0.4s ease-out forwards;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.slide-up {
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
