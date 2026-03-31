<script setup>
import { computed, onMounted, ref } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import PlatformAdminShell from '../components/platform/PlatformAdminShell.vue'
import { request } from '../services/api'

const tenants = ref([])
const users = ref([])
const memberships = ref([])
const tenantsLoading = ref(true)
const usersLoading = ref(true)
const membershipsLoading = ref(false)
const creatingTenant = ref(false)
const savingTenantId = ref(null)
const message = ref('')
const tenantSearch = ref('')
const newTenantName = ref('')
const selectedTenantId = ref(null)

const formatDate = (value) => {
  if (!value) return 'Unknown'
  return new Date(value).toLocaleString()
}

const statusVariant = (status) => {
  const normalized = String(status || '').trim().toUpperCase()
  if (normalized === 'ACTIVE') return 'success'
  if (normalized === 'SUSPENDED') return 'warning'
  return 'muted'
}

const roleTone = (role) => {
  const normalized = String(role || '').trim().toUpperCase()
  if (normalized === 'PLATFORM_ADMIN') return 'danger'
  if (normalized === 'TENANT_ADMIN') return 'info'
  return 'muted'
}

const usersById = computed(() => {
  const map = new Map()
  for (const user of users.value) {
    map.set(user.id, user)
  }
  return map
})

const filteredTenants = computed(() => {
  const term = tenantSearch.value.trim().toLowerCase()
  if (!term) return tenants.value
  return tenants.value.filter((tenant) =>
    [tenant.name, tenant.status, tenant.id]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(term))
  )
})

const selectedTenant = computed(() => (
  tenants.value.find((tenant) => tenant.id === selectedTenantId.value) || null
))

const summaryCards = computed(() => {
  const active = tenants.value.filter((tenant) => tenant.status === 'ACTIVE').length
  const suspended = tenants.value.filter((tenant) => tenant.status === 'SUSPENDED').length
  const totalMemberships = tenants.value.reduce((sum, tenant) => sum + Number(tenant.membership_count || 0), 0)
  const totalChannels = tenants.value.reduce((sum, tenant) => sum + Number(tenant.channel_count || 0), 0)
  return [
    { label: 'Tenants', value: tenants.value.length, hint: 'Registered companies or workspaces' },
    { label: 'Active', value: active, hint: 'Tenants currently allowed to operate' },
    { label: 'Suspended', value: suspended, hint: 'Tenants blocked at platform level' },
    { label: 'Members', value: totalMemberships, hint: `${totalChannels} channels across the platform` }
  ]
})

const membershipStats = computed(() => {
  const active = memberships.value.filter((membership) => membership.is_active).length
  const admins = memberships.value.filter((membership) => membership.role === 'TENANT_ADMIN').length
  return { active, admins }
})

const fetchUsers = async () => {
  usersLoading.value = true
  try {
    const data = await request('/platform/users')
    users.value = Array.isArray(data) ? data : []
  } catch (error) {
    message.value = `Failed to load users: ${error.message}`
    users.value = []
  } finally {
    usersLoading.value = false
  }
}

const fetchMemberships = async (tenantId) => {
  if (!tenantId) {
    memberships.value = []
    return
  }
  membershipsLoading.value = true
  try {
    const data = await request(`/platform/tenants/${tenantId}/memberships`)
    memberships.value = Array.isArray(data) ? data : []
  } catch (error) {
    message.value = `Failed to load memberships: ${error.message}`
    memberships.value = []
  } finally {
    membershipsLoading.value = false
  }
}

const fetchTenants = async ({ preserveSelection = true } = {}) => {
  tenantsLoading.value = true
  try {
    const data = await request('/platform/tenants')
    tenants.value = Array.isArray(data) ? data : []

    if (!preserveSelection || !tenants.value.some((tenant) => tenant.id === selectedTenantId.value)) {
      selectedTenantId.value = tenants.value[0]?.id ?? null
    }
  } catch (error) {
    message.value = `Failed to load tenants: ${error.message}`
    tenants.value = []
    selectedTenantId.value = null
  } finally {
    tenantsLoading.value = false
  }
}

const refreshAll = async () => {
  message.value = ''
  await Promise.all([fetchTenants(), fetchUsers()])
  await fetchMemberships(selectedTenantId.value)
}

const selectTenant = async (tenantId) => {
  selectedTenantId.value = tenantId
  await fetchMemberships(tenantId)
}

const createTenant = async () => {
  const name = newTenantName.value.trim()
  if (!name) {
    message.value = 'Tenant name is required.'
    return
  }

  creatingTenant.value = true
  message.value = 'Creating tenant...'
  try {
    const created = await request('/platform/tenants', {
      method: 'POST',
      body: JSON.stringify({ name })
    })
    newTenantName.value = ''
    message.value = `Tenant ${created.name} created.`
    await fetchTenants({ preserveSelection: false })
    selectedTenantId.value = created.id
    await fetchMemberships(created.id)
  } catch (error) {
    message.value = `Create failed: ${error.message}`
  } finally {
    creatingTenant.value = false
  }
}

const updateTenantStatus = async (tenant, nextStatus) => {
  savingTenantId.value = tenant.id
  message.value = `Updating ${tenant.name}...`
  try {
    const updated = await request(`/platform/tenants/${tenant.id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: nextStatus })
    })
    tenants.value = tenants.value.map((item) => (item.id === tenant.id ? updated : item))
    if (selectedTenantId.value === tenant.id) {
      selectedTenantId.value = updated.id
    }
    message.value = `${tenant.name} is now ${nextStatus.toLowerCase()}.`
  } catch (error) {
    message.value = `Update failed: ${error.message}`
  } finally {
    savingTenantId.value = null
  }
}

onMounted(async () => {
  await Promise.all([fetchTenants(), fetchUsers()])
  await fetchMemberships(selectedTenantId.value)
})
</script>

<template>
  <PlatformAdminShell>
    <template #sidebar>
      <div class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/92 p-5 shadow-panel">
        <p class="text-[10px] font-black uppercase tracking-[0.3em] text-ink-subtle">Platform Admin</p>
        <h2 class="mt-2 text-2xl font-bold text-ink">Tenant Management</h2>
        <p class="mt-2 text-sm text-ink-muted">
          Review every tenant, create new tenants, and control whether each tenant stays active on the platform.
        </p>

        <div class="mt-5 space-y-2">
          <router-link to="/settings" class="block rounded-2xl border border-line/70 bg-surface px-4 py-3 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-primary/5">Platform console</router-link>
          <router-link to="/settings/channels" class="block rounded-2xl border border-line/70 bg-surface px-4 py-3 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-primary/5">Channel management</router-link>
          <router-link to="/settings/history" class="block rounded-2xl border border-line/70 bg-surface px-4 py-3 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-primary/5">Message review</router-link>
        </div>
      </div>
    </template>

    <section class="rounded-[1.9rem] border border-line/80 bg-[linear-gradient(140deg,_rgb(var(--panel-elevated-rgb)_/_0.96),_rgb(var(--accent-soft-rgb)_/_0.2))] p-6 shadow-panel">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p class="text-[10px] font-black uppercase tracking-[0.32em] text-aurora">Platform Admin</p>
          <h1 class="mt-2 text-3xl font-black tracking-tight text-ink lg:text-4xl">Tenant management</h1>
          <p class="mt-2 max-w-3xl text-sm text-ink-muted">
            One desktop view for every registered tenant, with quick status control and membership visibility.
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <TuiBadge variant="info" size="sm">{{ users.length }} users loaded</TuiBadge>
          <TuiButton @click="refreshAll" :loading="tenantsLoading || usersLoading || membershipsLoading">Refresh</TuiButton>
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

    <div class="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
      <div class="space-y-4">
        <TuiCard title="Create Tenant" subtitle="Register a new tenant">
          <div class="grid gap-3 lg:grid-cols-[1fr_auto]">
            <TuiInput
              v-model="newTenantName"
              label="Tenant Name"
              placeholder="Example: Northwind Solar"
            />
            <div class="flex items-end">
              <TuiButton @click="createTenant" :loading="creatingTenant">Create Tenant</TuiButton>
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Tenant Directory" subtitle="Search and manage all registered tenants">
          <div class="grid gap-3 lg:grid-cols-[1fr_auto]">
            <TuiInput v-model="tenantSearch" label="Search" placeholder="Search name, id, or status" />
            <div class="flex items-end">
              <TuiButton variant="outline" @click="refreshAll" :loading="tenantsLoading" size="sm">Reload</TuiButton>
            </div>
          </div>

          <div v-if="tenantsLoading" class="py-6 text-sm text-ink-muted">Loading tenants...</div>
          <div v-else-if="filteredTenants.length === 0" class="py-6 text-sm text-ink-muted">No tenants match the current search.</div>
          <div v-else class="mt-4 space-y-3">
            <button
              v-for="tenant in filteredTenants"
              :key="tenant.id"
              @click="selectTenant(tenant.id)"
              class="w-full rounded-[1.5rem] border px-4 py-4 text-left transition-colors"
              :class="tenant.id === selectedTenantId ? 'border-primary/30 bg-primary/5' : 'border-line/70 bg-surface hover:border-line-strong hover:bg-surface-elevated/90'"
            >
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="text-base font-bold text-ink">{{ tenant.name }}</p>
                    <TuiBadge :variant="statusVariant(tenant.status)" size="sm">{{ tenant.status }}</TuiBadge>
                  </div>
                  <p class="mt-2 text-sm text-ink-muted">
                    Tenant #{{ tenant.id }} · {{ tenant.active_membership_count }}/{{ tenant.membership_count }} active memberships · {{ tenant.channel_count }} channels
                  </p>
                </div>
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-ink-subtle">
                  {{ formatDate(tenant.created_at) }}
                </p>
              </div>
            </button>
          </div>
        </TuiCard>
      </div>

      <div class="space-y-4">
        <TuiCard title="Tenant Detail" subtitle="Status control and membership view">
          <div v-if="!selectedTenant" class="py-6 text-sm text-ink-muted">Select a tenant to inspect its details.</div>
          <template v-else>
            <div class="rounded-[1.6rem] border border-line/70 bg-surface px-5 py-5">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div class="flex flex-wrap items-center gap-2">
                    <h3 class="text-2xl font-black tracking-tight text-ink">{{ selectedTenant.name }}</h3>
                    <TuiBadge :variant="statusVariant(selectedTenant.status)" size="sm">{{ selectedTenant.status }}</TuiBadge>
                  </div>
                  <p class="mt-2 text-sm text-ink-muted">
                    Tenant #{{ selectedTenant.id }} created {{ formatDate(selectedTenant.created_at) }}
                  </p>
                </div>
                <div class="flex flex-wrap gap-2">
                  <TuiButton
                    v-if="selectedTenant.status !== 'ACTIVE'"
                    @click="updateTenantStatus(selectedTenant, 'ACTIVE')"
                    :loading="savingTenantId === selectedTenant.id"
                    size="sm"
                  >
                    Activate
                  </TuiButton>
                  <TuiButton
                    v-if="selectedTenant.status !== 'SUSPENDED'"
                    @click="updateTenantStatus(selectedTenant, 'SUSPENDED')"
                    :loading="savingTenantId === selectedTenant.id"
                    variant="outline"
                    size="sm"
                  >
                    Suspend
                  </TuiButton>
                </div>
              </div>

              <div class="mt-5 grid gap-3 md:grid-cols-3">
                <div class="rounded-2xl border border-line/70 bg-surface-elevated/80 px-4 py-4">
                  <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Memberships</p>
                  <p class="mt-2 text-2xl font-black text-ink">{{ selectedTenant.membership_count }}</p>
                </div>
                <div class="rounded-2xl border border-line/70 bg-surface-elevated/80 px-4 py-4">
                  <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Active Members</p>
                  <p class="mt-2 text-2xl font-black text-ink">{{ selectedTenant.active_membership_count }}</p>
                </div>
                <div class="rounded-2xl border border-line/70 bg-surface-elevated/80 px-4 py-4">
                  <p class="text-[10px] font-black uppercase tracking-[0.24em] text-ink-subtle">Channels</p>
                  <p class="mt-2 text-2xl font-black text-ink">{{ selectedTenant.channel_count }}</p>
                </div>
              </div>
            </div>

            <div class="mt-4 rounded-[1.6rem] border border-line/70 bg-surface px-5 py-5">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p class="text-[10px] font-black uppercase tracking-[0.28em] text-ink-subtle">Memberships</p>
                  <h4 class="mt-2 text-xl font-bold text-ink">Users attached to this tenant</h4>
                  <p class="mt-2 text-sm text-ink-muted">
                    {{ membershipStats.active }} active memberships · {{ membershipStats.admins }} tenant admins
                  </p>
                </div>
                <TuiBadge :variant="membershipsLoading ? 'warning' : 'info'" size="sm">
                  {{ membershipsLoading ? 'Loading' : `${memberships.length} memberships` }}
                </TuiBadge>
              </div>

              <div v-if="membershipsLoading" class="mt-4 py-4 text-sm text-ink-muted">Loading memberships...</div>
              <div v-else-if="memberships.length === 0" class="mt-4 py-4 text-sm text-ink-muted">No memberships registered for this tenant yet.</div>
              <div v-else class="mt-4 space-y-3">
                <article
                  v-for="membership in memberships"
                  :key="membership.id"
                  class="rounded-2xl border border-line/70 bg-surface-elevated/80 px-4 py-4"
                >
                  <div class="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div class="flex flex-wrap items-center gap-2">
                        <p class="text-sm font-bold text-ink">
                          {{ usersById.get(membership.user_id)?.email || `User #${membership.user_id}` }}
                        </p>
                        <TuiBadge :variant="roleTone(membership.role)" size="sm">{{ membership.role }}</TuiBadge>
                        <TuiBadge :variant="membership.is_active ? 'success' : 'warning'" size="sm">
                          {{ membership.is_active ? 'Active' : 'Inactive' }}
                        </TuiBadge>
                      </div>
                      <p class="mt-2 text-sm text-ink-muted">
                        Membership #{{ membership.id }} · User #{{ membership.user_id }}
                      </p>
                    </div>
                    <p class="text-xs font-semibold uppercase tracking-[0.18em] text-ink-subtle">
                      {{ usersLoading ? 'Resolving users' : (usersById.get(membership.user_id)?.is_active ? 'User active' : 'User inactive') }}
                    </p>
                  </div>
                </article>
              </div>
            </div>
          </template>
        </TuiCard>
      </div>
    </div>
  </PlatformAdminShell>
</template>
