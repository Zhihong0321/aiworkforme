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
  <div class="min-h-screen flex items-center justify-center bg-slate-50 px-4">
    <div class="max-w-md w-full">
      <div class="text-center mb-10">
        <h2 class="text-3xl font-black text-slate-900 uppercase tracking-tighter">Aiworkfor.me</h2>
        <p class="mt-2 text-sm text-slate-600 uppercase tracking-widest font-bold">Platform Admin Console</p>
      </div>

      <div class="bg-white p-10 rounded-[2.5rem] shadow-2xl shadow-slate-200 border border-slate-100">
        <h1 class="text-xl font-bold text-slate-900 mb-6">Platform Login</h1>

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

          <div v-if="error" class="p-4 bg-red-50 border border-red-100 rounded-2xl text-xs text-red-600 font-bold">
            {{ error }}
          </div>

          <TuiButton
            class="w-full !py-4 shadow-lg shadow-indigo-200"
            :loading="isLoading"
            type="button"
            @click="handleLogin"
          >
            Sign In
          </TuiButton>
        </div>

        <div class="mt-6 text-center">
          <router-link to="/login" class="text-xs font-bold text-slate-600 hover:underline uppercase tracking-widest">
            Back To Tenant Login
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>
