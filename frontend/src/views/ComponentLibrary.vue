<script setup>
import { onBeforeUnmount, ref } from 'vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import TuiLoader from '../components/ui/TuiLoader.vue'
import TuiScrambleTitle from '../components/ui/TuiScrambleTitle.vue'
import TuiSelect from '../components/ui/TuiSelect.vue'

const tokens = [
  { label: 'Surface', value: 'var(--panel)' },
  { label: 'Border', value: 'var(--border)' },
  { label: 'Accent', value: 'var(--accent)' },
  { label: 'Muted', value: 'var(--muted)' }
]

const pills = ['ready', 'online', 'syncing', 'cooldown']

const surfaceMetrics = [
  { label: 'Components', value: '07', note: 'stable' },
  { label: 'Variants', value: '18', note: 'light tui' },
  { label: 'Latency', value: '12ms', note: 'ui response' }
]

const componentMap = [
  { name: 'Buttons', detail: 'primary, outline, ghost', state: 'ready' },
  { name: 'Badges', detail: 'success, info, warning, muted', state: 'ready' },
  { name: 'Inputs', detail: 'label + hint + two-column grid', state: 'ready' },
  { name: 'Select', detail: 'model preset dropdown', state: 'live' },
  { name: 'Loader', detail: 'deterministic length + done text', state: 'watch' },
  { name: 'Terminal', detail: 'panel log with headers', state: 'ready' }
]

const replayKey = ref(0)
const uploadState = ref('done')
const selectedModel = ref('')
const scanState = ref('idle')
const scanLog = ref([
  'ready: surface clean + contrast checked',
  'inputs primed: label + hint + numeric pairs',
  'loader: deterministic length 18'
])

const modelOptions = [
  { label: 'glm-4.7', value: 'glm-4.7' },
  { label: 'glm-4.7-flash', value: 'glm-4.7-flash' },
  { label: 'glm-4.6', value: 'glm-4.6' },
  { label: 'glm-4.5', value: 'glm-4.5' },
  { label: 'glm-4.5-air', value: 'glm-4.5-air' }
]

let timers = []

const clearTimers = () => {
  timers.forEach((id) => clearTimeout(id))
  timers = []
}

const pushLog = (line) => {
  scanLog.value = [line, ...scanLog.value].slice(0, 6)
}

const replay = () => {
  replayKey.value += 1
  uploadState.value = 'loading'
  clearTimers()
  timers.push(
    setTimeout(() => {
      uploadState.value = 'done'
    }, 3000)
  )
}

const startScan = () => {
  clearTimers()
  scanState.value = 'scanning'
  uploadState.value = 'loading'
  replayKey.value += 1
  pushLog('scan: booting loaders + typography')
  timers.push(setTimeout(() => pushLog('ok: buttons -> primary / outline / ghost'), 400))
  timers.push(setTimeout(() => pushLog('ok: inputs -> label + hint + numeric'), 1100))
  timers.push(setTimeout(() => pushLog('ok: badges -> success / info / warn / muted'), 1600))
  timers.push(
    setTimeout(() => {
      scanState.value = 'done'
      uploadState.value = 'done'
      pushLog('complete: components stable, ready for ship')
    }, 2300)
  )
}

const stateVariant = (state) => {
  if (state === 'live') return 'info'
  if (state === 'watch') return 'warning'
  return 'success'
}

onBeforeUnmount(() => {
  clearTimers()
})
</script>

<template>
  <div class="relative min-h-screen">
    <main class="relative z-10 mx-auto w-full max-w-none px-5 lg:px-10 py-10 space-y-8">
      <header class="tui-surface rounded-xl border border-slate-200 p-6">
        <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div class="space-y-3">
            <p class="text-xs uppercase tracking-[0.32em] text-slate-500">z.ai design</p>
            <TuiScrambleTitle text="COMPONENT RESCAN" variant="mono" />
            <p class="text-sm text-slate-600">
              Light TUI primitives for dashboards, agents, and MCP workflows — scanned and ready.
            </p>
            <div class="flex flex-wrap gap-2">
              <TuiBadge variant="info">light tui</TuiBadge>
              <TuiBadge variant="muted">panel grid</TuiBadge>
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <TuiBadge variant="info">state: {{ scanState }}</TuiBadge>
            <TuiBadge variant="muted">v0.2</TuiBadge>
            <TuiButton size="sm" @click="startScan" :loading="scanState === 'scanning'">rescan</TuiButton>
            <TuiButton size="sm" variant="outline" @click="replay">sync loaders</TuiButton>
          </div>
        </div>
      </header>

      <section class="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <TuiCard title="Rescan Console" subtitle="runtime">
          <div class="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
            <div class="space-y-4">
              <div class="flex flex-wrap items-center gap-3">
                <TuiButton size="sm" @click="startScan" :loading="scanState === 'scanning'">start scan</TuiButton>
                <TuiButton size="sm" variant="outline" @click="replay">replay loader</TuiButton>
                <TuiBadge variant="muted">deterministic</TuiBadge>
                <TuiBadge variant="info">focus-visible</TuiBadge>
              </div>
              <div class="rounded-lg border border-slate-200 bg-white">
                <div class="flex items-center justify-between border-b border-slate-200 px-4 py-2 text-[11px] uppercase tracking-[0.2em] text-slate-500">
                  <span>scan log</span>
                  <span>{{ scanState }}</span>
                </div>
                <div class="space-y-2 px-4 py-3 text-sm text-slate-800">
                  <p v-for="(line, idx) in scanLog" :key="idx" class="font-mono">
                    > {{ line }}
                  </p>
                </div>
              </div>
            </div>
            <div class="space-y-4">
              <TuiLoader
                label="component scan"
                :state="uploadState"
                :length="18"
                :intervalMs="16"
                done-text="SCAN COMPLETE"
                :key-seed="replayKey"
              />
              <div class="grid grid-cols-3 gap-3">
                <div v-for="metric in surfaceMetrics" :key="metric.label" class="rounded-lg border border-slate-200 bg-white p-3">
                  <p class="text-[11px] uppercase tracking-[0.2em] text-slate-500">{{ metric.label }}</p>
                  <p class="text-lg font-semibold text-slate-900">{{ metric.value }}</p>
                  <p class="text-xs text-slate-600">{{ metric.note }}</p>
                </div>
              </div>
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Tokens & Pills" subtitle="theme">
          <div class="grid grid-cols-2 gap-3">
            <div v-for="token in tokens" :key="token.label" class="rounded-lg border border-slate-200 p-3">
              <p class="text-[11px] uppercase tracking-[0.2em] text-slate-500">{{ token.label }}</p>
              <p class="text-sm text-slate-800">{{ token.value }}</p>
            </div>
          </div>
          <div class="mt-4 flex flex-wrap gap-2">
            <span
              v-for="pill in pills"
              :key="pill"
              class="rounded-full border border-slate-300 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-700"
            >
              {{ pill }}
            </span>
          </div>
        </TuiCard>
      </section>

      <section class="grid gap-6 lg:grid-cols-3">
        <TuiCard title="Buttons" subtitle="controls">
          <div class="flex flex-wrap items-center gap-3">
            <TuiButton>Primary</TuiButton>
            <TuiButton variant="outline">Outline</TuiButton>
            <TuiButton variant="ghost">Ghost</TuiButton>
            <TuiButton size="lg">Large</TuiButton>
            <TuiButton size="sm" variant="outline">Small</TuiButton>
            <TuiButton :block="true">Block</TuiButton>
          </div>
        </TuiCard>

        <TuiCard title="Badges" subtitle="status">
          <div class="flex flex-wrap gap-2">
            <TuiBadge variant="success">online</TuiBadge>
            <TuiBadge variant="info">streaming</TuiBadge>
            <TuiBadge variant="warning">pending</TuiBadge>
            <TuiBadge variant="muted">idle</TuiBadge>
          </div>
        </TuiCard>

        <TuiCard title="Terminal Window" subtitle="layout">
          <div class="rounded-lg border border-slate-300 bg-white">
            <div class="flex items-center justify-between border-b border-slate-200 px-4 py-2 text-[11px] uppercase tracking-[0.2em] text-slate-600">
              <span>reasoning</span>
              <span>live</span>
            </div>
            <div class="space-y-2 px-4 py-3 text-sm text-slate-800">
              <p>> mcp registry scan...</p>
              <p>> found 3 toolchains</p>
              <p class="font-semibold text-slate-900">> streaming: awaiting confirmation _</p>
            </div>
          </div>
        </TuiCard>
      </section>

      <section class="grid gap-6 lg:grid-cols-2">
        <TuiCard title="Forms" subtitle="inputs" class="h-full">
          <div class="space-y-4">
            <TuiInput label="Agent Name" placeholder="e.g. Atlas" hint="Required" />
            <TuiInput label="Model" placeholder="glm-4.6" hint="Select" />
            <div class="grid grid-cols-2 gap-3">
              <TuiInput label="Temperature" placeholder="0.7" />
              <TuiInput label="Max Tokens" placeholder="2048" />
            </div>
            <TuiSelect
              label="Model Preset"
              hint="Dropdown"
              placeholder="Select model"
              :options="modelOptions"
              v-model="selectedModel"
            />
            <div class="flex gap-3">
              <TuiButton>Save Agent</TuiButton>
              <TuiButton variant="outline">Reset</TuiButton>
            </div>
          </div>
        </TuiCard>

        <TuiCard title="Loader" subtitle="animated">
          <div class="grid gap-4">
            <div class="flex flex-wrap items-center gap-2">
              <TuiButton size="sm" variant="outline" @click="replay">Replay (3s)</TuiButton>
              <TuiBadge variant="muted">interval 16ms</TuiBadge>
            </div>
            <TuiLoader label="agent boot" :length="16" :intervalMs="16" :key-seed="replayKey" />
            <TuiLoader label="mcp sync" :length="10" :intervalMs="16" :key-seed="replayKey" />
            <TuiLoader
              label="upload"
              :state="uploadState"
              done-text="FILE UPLOADED"
              :intervalMs="16"
              :key-seed="replayKey"
            />
          </div>
        </TuiCard>
      </section>

      <section>
        <TuiCard title="Component Matrix" subtitle="status grid">
          <div class="rounded-lg border border-slate-200 bg-white">
            <div class="grid grid-cols-[1.4fr_1fr_auto] gap-3 border-b border-slate-200 px-4 py-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
              <span>component</span>
              <span>coverage</span>
              <span>state</span>
            </div>
            <div class="divide-y divide-slate-200">
              <div
                v-for="item in componentMap"
                :key="item.name"
                class="grid grid-cols-[1.4fr_1fr_auto] gap-3 px-4 py-3 text-sm text-slate-800"
              >
                <div>
                  <p class="font-semibold text-slate-900">{{ item.name }}</p>
                  <p class="text-xs text-slate-600">{{ item.detail }}</p>
                </div>
                <span class="self-center text-xs text-slate-700">coverage: 100%</span>
                <TuiBadge :variant="stateVariant(item.state)" class="w-24 justify-center">{{ item.state }}</TuiBadge>
              </div>
            </div>
          </div>
        </TuiCard>
      </section>
    </main>
  </div>
</template>
