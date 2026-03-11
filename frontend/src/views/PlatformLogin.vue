<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiInput from '../components/ui/TuiInput.vue'

const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref('')
const isLoading = ref(false)

const handleLogin = async () => {
  if (!email.value || !password.value) {
    error.value = 'Please enter both email and password.'
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    const formData = new FormData()
    formData.append('username', email.value)
    formData.append('password', password.value)

    const response = await fetch(`${window.location.origin}/api/v1/auth/login`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Login failed')
    }

    const data = await response.json()
    if (!data.is_platform_admin) {
      throw new Error('This account is not a platform admin.')
    }

    localStorage.setItem('token', data.access_token)
    localStorage.removeItem('tenant_id')
    localStorage.setItem('user_id', data.user_id)
    localStorage.setItem('is_platform_admin', 'true')
    router.push('/home')
  } catch (e) {
    error.value = e.message
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="mobile-shell flex min-h-screen items-center justify-center px-4 py-8">
    <div class="w-full max-w-md">
      <div class="mb-8 text-center">
        <p class="text-[11px] font-bold uppercase tracking-[0.3em] text-ink-subtle">Platform Admin Console</p>
        <h2 class="mt-3 text-3xl font-black uppercase tracking-[-0.04em] text-ink">Aiworkfor.me</h2>
        <p class="mx-auto mt-3 max-w-[18rem] text-sm text-ink-muted">
          Access provider settings, audit trails, and platform-wide controls from the same streamlined theme.
        </p>
      </div>

      <div class="surface-card rounded-[2rem] p-6 sm:p-8">
        <div class="mb-6 flex items-start justify-between gap-4">
          <div>
            <p class="text-[11px] font-bold uppercase tracking-[0.26em] text-primary">Platform Access</p>
            <h1 class="mt-2 text-2xl font-bold text-ink">Admin Sign In</h1>
          </div>
          <div class="flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/15 bg-primary/10 text-primary">
            <span class="material-symbols-outlined text-[26px]">admin_panel_settings</span>
          </div>
        </div>

        <div class="space-y-6">
          <TuiInput
            label="Email Address"
            v-model="email"
            placeholder="admin@aiworkfor.me"
            type="email"
            @keyup.enter="handleLogin"
            required
          />

          <TuiInput
            label="Password"
            v-model="password"
            placeholder="••••••••"
            type="password"
            @keyup.enter="handleLogin"
            required
          />

          <div v-if="error" class="rounded-2xl border border-danger/20 bg-danger/10 p-4 text-xs font-bold text-danger">
            {{ error }}
          </div>

          <TuiButton
            class="w-full !py-4"
            :loading="isLoading"
            type="button"
            @click="handleLogin"
          >
            Sign In
          </TuiButton>
        </div>

        <div class="mt-6 text-center">
          <router-link to="/login" class="text-xs font-bold uppercase tracking-[0.22em] text-ink-muted hover:underline">
            Back To Tenant Login
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>
