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
  <div class="px-6 py-8 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
      <div>
        <h1 class="text-3xl font-black tracking-tighter uppercase mb-1">User Calendar</h1>
        <p class="text-sm font-medium opacity-50 uppercase tracking-widest">Manage your availability and AI-scheduled appointments</p>
      </div>

      <div class="flex items-center p-1 rounded-xl bg-black/5 dark:bg-white/5 backdrop-blur-md border border-black/10 dark:border-white/10">
        <button 
          @click="activeTab = 'calendar'"
          :class="[
            'px-6 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all duration-300',
            activeTab === 'calendar' 
              ? 'bg-black text-white dark:bg-white dark:text-black shadow-lg' 
              : 'text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white'
          ]"
        >
          Calendar
        </button>
        <button 
          @click="activeTab = 'config'"
          :class="[
            'px-6 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all duration-300',
            activeTab === 'config' 
              ? 'bg-black text-white dark:bg-white dark:text-black shadow-lg' 
              : 'text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white'
          ]"
        >
          Settings
        </button>
      </div>
    </div>

    <!-- Calendar Tab -->
    <div v-if="activeTab === 'calendar'" class="animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-8">
        
        <!-- Sidebar: Stats & Next Meetings -->
        <div class="space-y-6">
          <div class="p-6 rounded-3xl bg-blue-600 text-white shadow-xl shadow-blue-500/20">
            <h3 class="text-[10px] font-black uppercase tracking-widest opacity-80 mb-4">Total Appointments</h3>
            <div class="text-4xl font-black mb-1">{{ events.length }}</div>
            <p class="text-[10px] font-bold uppercase tracking-widest opacity-60">This Month</p>
          </div>

          <div class="p-6 rounded-3xl border border-black/10 dark:border-white/10 bg-white/50 dark:bg-black/20 backdrop-blur-xl">
            <h3 class="text-[10px] font-black uppercase tracking-widest opacity-50 mb-4">Upcoming</h3>
            <div v-if="events.length === 0" class="text-xs opacity-40 py-4">No meetings scheduled</div>
            <div v-else class="space-y-4">
              <div v-for="event in events.slice(0, 5)" :key="event.id" class="flex items-start gap-3">
                <div class="w-1 h-10 rounded-full bg-blue-500"></div>
                <div>
                  <div class="text-xs font-black uppercase">{{ event.title }}</div>
                  <div class="text-[10px] opacity-50 uppercase font-bold">{{ new Date(event.start_time).toLocaleString() }}</div>
                </div>
              </div>
            </div>
          </div>

          <button 
            @click="openAddModal()"
            class="w-full flex items-center justify-center gap-2 py-4 rounded-3xl border-2 border-dashed border-black/10 dark:border-white/10 hover:border-black dark:hover:border-white transition-all group"
          >
            <Plus class="w-4 h-4 group-hover:scale-125 transition-transform" />
            <span class="text-[10px] font-black uppercase tracking-widest">Add Manual Block</span>
          </button>
        </div>

        <!-- Main Calendar -->
        <div class="lg:col-span-3">
          <div class="p-6 rounded-3xl border border-black/10 dark:border-white/10 bg-white/50 dark:bg-black/20 backdrop-blur-xl shadow-2xl">
            <!-- Calendar Header -->
            <div class="flex items-center justify-between mb-8">
              <h2 class="text-xl font-black uppercase tracking-tight">
                {{ currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' }) }}
              </h2>
              <div class="flex items-center gap-2">
                <button @click="prevMonth" class="p-2 rounded-xl hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                  <ChevronLeft class="w-5 h-5" />
                </button>
                <button @click="nextMonth" class="p-2 rounded-xl hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                  <ChevronRight class="w-5 h-5" />
                </button>
              </div>
            </div>

            <!-- Days Grid -->
            <div class="grid grid-cols-7 border border-black/5 dark:border-white/5 rounded-2xl overflow-hidden">
              <div v-for="day in ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']" :key="day" 
                   class="py-3 text-[10px] font-black uppercase tracking-widest text-center border-b border-black/5 dark:border-white/5 opacity-50">
                {{ day }}
              </div>
              <div 
                v-for="(day, idx) in calendarDays" 
                :key="idx"
                class="min-h-[120px] p-2 border-r border-b border-black/5 dark:border-white/5 last:border-r-0 hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors relative group"
                :class="[!day.currentMonth ? 'opacity-20' : '']"
              >
                <div class="flex justify-between items-start mb-2">
                  <span class="text-[10px] font-black">{{ day.date.getDate() }}</span>
                  <button 
                    v-if="day.currentMonth"
                    @click="openAddModal(day.date)"
                    class="p-1 rounded bg-black/5 dark:bg-white/5 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <Plus class="w-3 h-3" />
                  </button>
                </div>
                
                <!-- Events in Day -->
                <div class="space-y-1 overflow-y-auto max-h-[80px] scrollbar-hide">
                  <div 
                    v-for="event in getEventsForDay(day.date)" 
                    :key="event.id"
                    :class="[
                      'px-2 py-1 rounded text-[8px] font-black uppercase truncate cursor-pointer transition-transform hover:scale-105',
                      event.event_type === 'appointment' ? 'bg-blue-500 text-white' : 'bg-red-500 text-white'
                    ]"
                  >
                    {{ event.title }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Config Tab -->
    <div v-if="activeTab === 'config'" class="animate-in fade-in slide-in-from-bottom-4 duration-700 max-w-2xl mx-auto">
      <div class="p-8 rounded-3xl border border-black/10 dark:border-white/10 bg-white/50 dark:bg-black/20 backdrop-blur-xl space-y-8 shadow-2xl">
        
        <!-- Meeting Types -->
        <div>
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-black uppercase tracking-widest flex items-center gap-2">
              <Clock class="w-4 h-4" /> Meeting Types
            </h3>
            <button @click="addMeetingType" class="text-[10px] font-black uppercase tracking-widest opacity-50 hover:opacity-100 flex items-center gap-1">
              <Plus class="w-3 h-3" /> Add Type
            </button>
          </div>
          <div class="space-y-3">
            <div v-for="(type, index) in config.meeting_types" :key="index" class="flex gap-3 items-center group">
              <input 
                v-model="type.name" 
                placeholder="Label" 
                class="flex-1 bg-black/5 dark:bg-white/5 border-none rounded-xl px-4 py-3 text-xs font-bold focus:ring-2 ring-blue-500"
              />
              <input 
                v-model.number="type.duration_minutes" 
                type="number" 
                placeholder="Min" 
                class="w-24 bg-black/5 dark:bg-white/5 border-none rounded-xl px-4 py-3 text-xs font-bold focus:ring-2 ring-blue-500"
              />
              <button @click="removeMeetingType(index)" class="p-3 rounded-xl hover:bg-red-500/10 text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <!-- Regions -->
        <div>
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-black uppercase tracking-widest flex items-center gap-2">
              <MapPin class="w-4 h-4" /> Available Regions
            </h3>
            <button @click="addRegion" class="text-[10px] font-black uppercase tracking-widest opacity-50 hover:opacity-100 flex items-center gap-1">
              <Plus class="w-3 h-3" /> Add Region
            </button>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div v-for="(region, index) in config.available_regions" :key="index" class="flex gap-2 items-center group">
              <input 
                v-model="config.available_regions[index]" 
                placeholder="Region Name" 
                class="flex-1 bg-black/5 dark:bg-white/5 border-none rounded-xl px-4 py-3 text-xs font-bold focus:ring-2 ring-blue-500"
              />
              <button @click="removeRegion(index)" class="p-2 rounded-xl hover:bg-red-500/10 text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">
                <Trash2 class="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>

        <!-- Timezone -->
        <div>
           <h3 class="text-sm font-black uppercase tracking-widest flex items-center gap-2 mb-4">
              <Settings class="w-4 h-4" /> System Timezone
            </h3>
            <select v-model="config.timezone" class="w-full bg-black/5 dark:bg-white/5 border-none rounded-xl px-4 py-3 text-xs font-bold focus:ring-2 ring-blue-500">
              <option value="UTC">UTC (Universal Time)</option>
              <option value="Asia/Singapore">Asia/Singapore (SGT)</option>
              <option value="Asia/Kuala_Lumpur">Asia/Kuala_Lumpur (MYT)</option>
              <option value="America/New_York">America/New_York (EST)</option>
              <option value="Europe/London">Europe/London (GMT)</option>
            </select>
        </div>

        <button 
          @click="saveConfig"
          :disabled="isLoading"
          class="w-full py-4 bg-black dark:bg-white text-white dark:text-black rounded-3xl text-[10px] font-black uppercase tracking-widest shadow-xl transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-50"
        >
          <span v-if="!isLoading">Save Configuration</span>
          <span v-else class="animate-pulse">Saving...</span>
        </button>
      </div>
    </div>

    <!-- Modal: New Event -->
    <div v-if="showEventModal" class="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
      <div class="w-full max-w-md bg-white dark:bg-slate-900 rounded-3xl shadow-2xl p-8 border border-white/10 space-y-6">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-black uppercase tracking-tight">Schedule Block</h3>
          <button @click="showEventModal = false" class="p-2 hover:bg-black/5 dark:hover:bg-white/5 rounded-xl">
             <XCircle class="w-6 h-6 opacity-40" />
          </button>
        </div>

        <div class="space-y-4">
          <div>
            <label class="text-[10px] font-black uppercase opacity-50 block mb-2">Block Title</label>
            <input v-model="newEvent.title" placeholder="e.g. Do Not Disturb" class="w-full bg-black/5 dark:bg-white/5 border-none rounded-xl px-4 py-3 text-xs font-bold" />
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-[10px] font-black uppercase opacity-50 block mb-2">Start Time</label>
              <input v-model="newEvent.start_time" type="datetime-local" class="w-full bg-black/5 dark:bg-white/5 border-none rounded-xl px-4 py-3 text-xs font-bold" />
            </div>
            <div>
              <label class="text-[10px] font-black uppercase opacity-50 block mb-2">End Time</label>
              <input v-model="newEvent.end_time" type="datetime-local" class="w-full bg-black/5 dark:bg-white/5 border-none rounded-xl px-4 py-3 text-xs font-bold" />
            </div>
          </div>

          <div class="flex items-center gap-4">
             <button 
              @click="newEvent.event_type = 'appointment'"
              :class="[
                'flex-1 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest border transition-all',
                newEvent.event_type === 'appointment' ? 'bg-blue-500 border-blue-500 text-white' : 'border-black/10 dark:border-white/10 opacity-50'
              ]"
            >
              Appointment
            </button>
             <button 
              @click="newEvent.event_type = 'unavailable'"
              :class="[
                'flex-1 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest border transition-all',
                newEvent.event_type === 'unavailable' ? 'bg-red-500 border-red-500 text-white' : 'border-black/10 dark:border-white/10 opacity-50'
              ]"
            >
              Unavailable
            </button>
          </div>

          <button 
            @click="handleCreateEvent"
            :disabled="isLoading"
            class="w-full py-4 bg-black dark:bg-white text-white dark:text-black rounded-3xl text-[10px] font-black uppercase tracking-widest shadow-xl disabled:opacity-50"
          >
            Confirm Block
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
