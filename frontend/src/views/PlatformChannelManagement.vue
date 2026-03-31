<script setup>
import { computed, onMounted, ref } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import PlatformAdminShell from '../components/platform/PlatformAdminShell.vue'
import { request } from '../services/api'

const channels = ref([])
const channelsLoading = ref(true)
const message = ref('')
const search = ref('')
const tenantFilter = ref('all')
const statusFilter = ref('all')
const typeFilter = ref('all')
const selectedChannelId = ref(null)

const normalize = (value) => String(value || '').trim().toLowerCase()

const formatDate = (value) => {
  if (!value) return 'Unknown'
  return new Date(value).toLocaleString()
}

const statusVariant = (status) => {
  const normalized = normalize(status)
  if (normalized === 'active') return 'success'
  if (normalized === 'suspended') return 'warning'
  if (normalized === 'disconnected') return 'danger'
  return 'muted'
}

const channelTitle = (channel) => (
  channel?.connected_number
  || channel?.display_name
  || channel?.session_identifier
  || 'Unnamed channel'
)

const channelDescription = (channel) => (
  channel?.description
  || channel?.session_metadata?.description
  || 'No description saved for this channel.'
)

const tenantOptions = computed(() => {
  const map = new Map()
  for (const channel of channels.value) {
    map.set(String(channel.tenant_id), channel.tenant_name || `Tenant #${channel.tenant_id}`)
  }
  return Array.from(map.entries())
    .map(([value, label]) => ({ value, label }))
    .sort((left, right) => left.label.localeCompare(right.label))
})

const summaryCards = computed(() => {
  const active = channels.value.filter((channel) => normalize(channel.status) === 'active').length
  const disconnected = channels.value.filter((channel) => normalize(channel.status) === 'disconnected').length
  const suspended = channels.value.filter((channel) => normalize(channel.status) === 'suspended').length
  const tenants = new Set(channels.value.map((channel) => channel.tenant_id)).size
  return [
    { label: 'Channels', value: channels.value.length, hint: 'All registered platform channels' },
    { label: 'Tenants', value: tenants, hint: 'Tenants currently using channels' },
    { label: 'Active', value: active, hint: 'Ready or live channels' },
    { label: 'Disconnected', value: disconnected + suspended, hint: `${suspended} suspended across the platform` }
  ]
})

const filteredChannels = computed(() => {
  const term = search.value.trim().toLowerCase()
  return channels.value.filter((channel) => {
    const matchesTenant = tenantFilter.value === 'all' || String(channel.tenant_id) === tenantFilter.value
    const matchesStatus = statusFilter.value === 'all' || normalize(channel.status) === statusFilter.value
    const matchesType = typeFilter.value === 'all' || normalize(channel.channel_type) === typeFilter.value
    const matchesSearch = !term || [
      channel.id,
      channel.tenant_id,
      channel.tenant_name,
      channel.channel_type,
      channel.status,
      channel.session_identifier,
      channel.display_name,
      channel.description,
      channel.connected_number,
      channel.provider_session_id
    ].filter(Boolean).some((value) => String(value).toLowerCase().includes(term))

    return matchesTenant && matchesStatus && matchesType && matchesSearch
  })
})

const selectedChannel = computed(() => (
  channels.value.find((channel) => channel.id === selectedChannelId.value)
  || filteredChannels.value[0]
  || null
))

const fetchChannels = async () => {
  channelsLoading.value = true
  message.value = ''
  try {
    const data = await request('/platform/channels')
    channels.value = Array.isArray(data) ? data : []
    if (!channels.value.some((channel) => channel.id === selectedChannelId.value)) {
      selectedChannelId.value = channels.value[0]?.id ?? null
    }
  } catch (error) {
    message.value = `Failed to load channels: ${error.message}`
    channels.value = []
    selectedChannelId.value = null
  } finally {
    channelsLoading.value = false
  }
}

const selectChannel = (channelId) => {
  selectedChannelId.value = channelId
}

onMounted(fetchChannels)
</script>

<template>
  <PlatformAdminShell>
    <template #sidebar>
      <div class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/92 p-5 shadow-panel">
        <p class="text-[10px] font-black uppercase tracking-[0.3em] text-ink-subtle">Platform Admin</p>
        <h2 class="mt-2 text-2xl font-bold text-ink">Channel Management</h2>
        <p class="mt-2 text-sm text-ink-muted">
          Review every channel created on the platform with tenant ownership, live identity, and session metadata.
        </p>

        <div class="mt-5 space-y-2">
          <router-link to="/settings" class="block rounded-2xl border border-line/70 bg-surface px-4 py-3 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-primary/5">Platform console</router-link>
          <router-link to="/settings/tenants" class="block rounded-2xl border border-line/70 bg-surface px-4 py-3 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-primary/5">Tenant management</router-link>
          <router-link to="/settings/history" class="block rounded-2xl border border-line/70 bg-surface px-4 py-3 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-primary/5">Message review</router-link>
        </div>
      </div>
    </template>

    <section class="rounded-[1.9rem] border border-line/80 bg-[linear-gradient(140deg,_rgb(var(--panel-elevated-rgb)_/_0.96),_rgb(var(--accent-soft-rgb)_/_0.2))] p-6 shadow-panel">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p class="text-[10px] font-black uppercase tracking-[0.32em] text-aurora">Platform Admin</p>
          <h1 class="mt-2 text-3xl font-black tracking-tight text-ink lg:text-4xl">Channel management</h1>
          <p class="mt-2 max-w-3xl text-sm text-ink-muted">
            A single readout for all platform channels, with tenant ownership, live identifiers, provider session hints, and raw metadata.
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <TuiBadge variant="info" size="sm">{{ summaryCards[0].value }} total channels</TuiBadge>
          <TuiButton @click="fetchChannels" :loading="channelsLoading">Refresh</TuiButton>
        </div>
      </div>
      <p v-if="message" class="mt-4 rounded-2xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm font-semibold text-primary">
        {{ message }}
      </p>
    </section>

    <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <article
        v-for="card in summaryCards"
        :key="card.label"
        class="rounded-[1.6rem] border border-line/70 bg-surface-elevated/90 p-5 shadow-[0_20px_40px_-28px_rgb(var(--text-rgb)_/_0.2)]"
      >
        <p class="text-[10px] font-black uppercase tracking-[0.28em] text-ink-subtle">{{ card.label }}</p>
        <p class="mt-3 text-3xl font-black tracking-tight text-ink">{{ card.value }}</p>
        <p class="mt-2 text-sm text-ink-muted">{{ card.hint }}</p>
      </article>
    </section>

    <div class="grid gap-4 xl:grid-cols-[1fr_0.95fr]">
      <div class="space-y-4">
        <TuiCard title="Channel Filters" subtitle="Narrow the platform-wide list">
          <div class="grid gap-3 xl:grid-cols-2">
            <TuiInput v-model="search" label="Search" placeholder="Search tenant, identifier, phone, description" />

            <label class="flex flex-col gap-2 text-sm text-ink">
              <span class="text-xs uppercase tracking-wider text-ink-subtle">Tenant</span>
              <select v-model="tenantFilter" class="w-full rounded-2xl border border-line-strong bg-surface-elevated/90 px-4 py-3 text-sm text-ink">
                <option value="all">All tenants</option>
                <option v-for="tenant in tenantOptions" :key="tenant.value" :value="tenant.value">
                  {{ tenant.label }}
                </option>
              </select>
            </label>

            <label class="flex flex-col gap-2 text-sm text-ink">
              <span class="text-xs uppercase tracking-wider text-ink-subtle">Status</span>
              <select v-model="statusFilter" class="w-full rounded-2xl border border-line-strong bg-surface-elevated/90 px-4 py-3 text-sm text-ink">
                <option value="all">All statuses</option>
                <option value="active">Active</option>
                <option value="disconnected">Disconnected</option>
                <option value="suspended">Suspended</option>
              </select>
            </label>

            <label class="flex flex-col gap-2 text-sm text-ink">
              <span class="text-xs uppercase tracking-wider text-ink-subtle">Channel Type</span>
              <select v-model="typeFilter" class="w-full rounded-2xl border border-line-strong bg-surface-elevated/90 px-4 py-3 text-sm text-ink">
                <option value="all">All types</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="email">Email</option>
                <option value="discord">Discord</option>
                <option value="telegram">Telegram</option>
              </select>
            </label>
          </div>
        </TuiCard>

        <TuiCard title="Platform Channels" subtitle="All channels created in the platform">
          <div v-if="channelsLoading" class="py-6 text-sm text-ink-muted">Loading channels...</div>
          <div v-else-if="filteredChannels.length === 0" class="py-6 text-sm text-ink-muted">No channels match the current filters.</div>
          <div v-else class="space-y-3">
            <button
              v-for="channel in filteredChannels"
              :key="channel.id"
              @click="selectChannel(channel.id)"
              class="w-full rounded-[1.5rem] border px-4 py-4 text-left transition-colors"
              :class="channel.id === selectedChannel?.id ? 'border-primary/30 bg-primary/5' : 'border-line/70 bg-surface hover:border-line-strong hover:bg-surface-elevated/90'"
            >
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="truncate text-base font-bold text-ink">{{ channelTitle(channel) }}</p>
                    <TuiBadge :variant="statusVariant(channel.status)" size="sm">{{ channel.status }}</TuiBadge>
                    <TuiBadge variant="info" size="sm">{{ channel.channel_type }}</TuiBadge>
                  </div>
                  <p class="mt-2 text-sm text-ink-muted">
                    {{ channel.tenant_name || `Tenant #${channel.tenant_id}` }} · Provider {{ channel.provider_session_id || 'n/a' }}
                  </p>
                  <p class="mt-2 text-sm text-ink-muted">
                    {{ channelDescription(channel) }}
                  </p>
                </div>
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-ink-subtle">
                  {{ formatDate(channel.updated_at) }}
                </p>
              </div>
            </button>
          </div>
        </TuiCard>
      </div>

      <div class="space-y-4">
        <TuiCard title="Channel Detail" subtitle="Selected platform channel">
          <div v-if="!selectedChannel" class="py-6 text-sm text-ink-muted">Select a channel to inspect its metadata.</div>
          <template v-else>
            <div class="rounded-[1.6rem] border border-line/70 bg-surface px-5 py-5">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2">
                    <h3 class="truncate text-2xl font-black tracking-tight text-ink">{{ channelTitle(selectedChannel) }}</h3>
                    <TuiBadge :variant="statusVariant(selectedChannel.status)" size="sm">{{ selectedChannel.status }}</TuiBadge>
                    <TuiBadge variant="info" size="sm">{{ selectedChannel.channel_type }}</TuiBadge>
                  </div>
                  <p class="mt-2 text-sm text-ink-muted">
                    {{ selectedChannel.tenant_name || `Tenant #${selectedChannel.tenant_id}` }} · Channel #{{ selectedChannel.id }}
                  </p>
                </div>
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-ink-subtle">
                  Updated {{ formatDate(selectedChannel.updated_at) }}
                </p>
              </div>

              <div class="mt-5 grid gap-3 md:grid-cols-2">
                <div class="rounded-2xl border border-line/70 bg-surface-elevated/80 px-4 py-4">
                  <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Session Identifier</p>
                  <p class="mt-2 break-all text-sm font-semibold text-ink">{{ selectedChannel.session_identifier }}</p>
                </div>
                <div class="rounded-2xl border border-line/70 bg-surface-elevated/80 px-4 py-4">
                  <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Provider Session</p>
                  <p class="mt-2 break-all text-sm font-semibold text-ink">{{ selectedChannel.provider_session_id || 'Not captured' }}</p>
                </div>
                <div class="rounded-2xl border border-line/70 bg-surface-elevated/80 px-4 py-4">
                  <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Connected Number</p>
                  <p class="mt-2 break-all text-sm font-semibold text-ink">{{ selectedChannel.connected_number || 'Not captured yet' }}</p>
                </div>
                <div class="rounded-2xl border border-line/70 bg-surface-elevated/80 px-4 py-4">
                  <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Created</p>
                  <p class="mt-2 text-sm font-semibold text-ink">{{ formatDate(selectedChannel.created_at) }}</p>
                </div>
              </div>

              <div class="mt-5 rounded-2xl border border-line/70 bg-surface-elevated/80 px-4 py-4">
                <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Description</p>
                <p class="mt-2 text-sm text-ink">{{ channelDescription(selectedChannel) }}</p>
              </div>
            </div>

            <div class="rounded-[1.6rem] border border-line/70 bg-surface px-5 py-5">
              <div class="flex items-center justify-between gap-3">
                <div>
                  <p class="text-[10px] font-black uppercase tracking-[0.28em] text-ink-subtle">Raw Metadata</p>
                  <h4 class="mt-2 text-xl font-bold text-ink">Provider payload snapshot</h4>
                </div>
                <TuiBadge variant="info" size="sm">{{ Object.keys(selectedChannel.session_metadata || {}).length }} keys</TuiBadge>
              </div>
              <pre class="mt-4 overflow-x-auto rounded-2xl bg-slate-950 p-4 text-[11px] leading-5 text-slate-100">{{ JSON.stringify(selectedChannel.session_metadata || {}, null, 2) }}</pre>
            </div>
          </template>
        </TuiCard>
      </div>
    </div>
  </PlatformAdminShell>
</template>
