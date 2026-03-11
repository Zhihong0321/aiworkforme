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
    if (data.is_platform_admin) {
      throw new Error('This is tenant login. Use Platform Admin login.')
    }

    localStorage.setItem('token', data.access_token)
    if (data.tenant_id === null || data.tenant_id === undefined || data.tenant_id === '') {
      localStorage.removeItem('tenant_id')
    } else {
      localStorage.setItem('tenant_id', String(data.tenant_id))
    }
    localStorage.setItem('user_id', data.user_id)
    localStorage.setItem('is_platform_admin', 'false')
    
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
        <p class="text-[11px] font-bold uppercase tracking-[0.3em] text-ink-subtle">Tenant Console</p>
        <h2 class="mt-3 text-3xl font-black uppercase tracking-[-0.04em] text-ink">Aiworkfor.me</h2>
        <p class="mx-auto mt-3 max-w-[18rem] text-sm text-ink-muted">
          Sign in to review agents, conversations, and workspace activity from one calm mobile dashboard.
        </p>
      </div>

      <div class="surface-card rounded-[2rem] p-6 sm:p-8">
        <div class="mb-6 flex items-start justify-between gap-4">
          <div>
            <p class="text-[11px] font-bold uppercase tracking-[0.26em] text-primary">Welcome Back</p>
            <h1 class="mt-2 text-2xl font-bold text-ink">Tenant Sign In</h1>
          </div>
          <div class="flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/15 bg-primary/10 text-primary">
            <span class="material-symbols-outlined text-[26px]">shield_person</span>
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
          <router-link to="/platform/login" class="text-xs font-bold uppercase tracking-[0.22em] text-primary hover:underline">
            Platform Admin Login
          </router-link>
        </div>

        <div class="mt-8 border-t border-line/70 pt-6 text-center">
          <p class="text-[10px] font-bold uppercase tracking-[0.22em] leading-loose text-ink-subtle">
            Enterprise Grade AI Orchestration<br/>
            © 2026 Aiworkforme Inc.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
