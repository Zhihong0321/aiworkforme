<script setup>
import { computed, onMounted, ref } from 'vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import PlatformAdminShell from '../components/platform/PlatformAdminShell.vue'
import { request } from '../services/api'

const availableModels = ref([])
const modelsText = ref('')
const prompt = ref('Summarize solar lead qualification in one sentence.')
const runsPerModel = ref(2)
const maxTokens = ref(256)
const temperature = ref(0.2)
const loadingModels = ref(true)
const running = ref(false)
const errorMessage = ref('')
const benchmark = ref(null)

const selectedModels = computed(() =>
  modelsText.value
    .split('\n')
    .map((v) => v.trim())
    .filter(Boolean)
)

const hydrateModelCatalog = async () => {
  loadingModels.value = true
  errorMessage.value = ''
  try {
    const data = await request('/platform/llm/models')
    const rows = Array.isArray(data) ? data : []
    availableModels.value = rows.filter((row) => row.provider === 'uniapi')
    const defaults = availableModels.value.map((row) => row.model)
    modelsText.value = defaults.join('\n')
  } catch (error) {
    errorMessage.value = `Failed to load model catalog: ${error.message}`
  } finally {
    loadingModels.value = false
  }
}

const runBenchmark = async () => {
  if (selectedModels.value.length === 0) {
    errorMessage.value = 'Provide at least one model name.'
    return
  }
  running.value = true
  errorMessage.value = ''
  benchmark.value = null
  try {
    benchmark.value = await request('/platform/llm/benchmark', {
      method: 'POST',
      body: JSON.stringify({
        provider: 'uniapi',
        models: selectedModels.value,
        prompt: prompt.value,
        runs_per_model: Number(runsPerModel.value || 1),
        max_tokens: Number(maxTokens.value || 256),
        temperature: Number(temperature.value || 0.2)
      })
    })
  } catch (error) {
    errorMessage.value = `Benchmark failed: ${error.message}`
  } finally {
    running.value = false
  }
}

onMounted(() => {
  hydrateModelCatalog()
})
</script>

<template>
  <PlatformAdminShell>
    <template #sidebar>
      <div class="rounded-[1.75rem] border border-line/80 bg-surface-elevated/92 p-5 shadow-panel">
        <p class="text-[10px] font-black uppercase tracking-[0.3em] text-ink-subtle">Platform Admin</p>
        <h2 class="mt-2 text-2xl font-bold text-ink">Benchmark</h2>
        <p class="mt-2 text-sm text-ink-muted">Desktop comparison lane for provider latency, token usage, and failures.</p>
        <div class="mt-5 space-y-2">
          <a href="/settings" class="block rounded-2xl border border-line/70 bg-surface px-4 py-3 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-primary/5">Back to console</a>
          <a href="/settings/history" class="block rounded-2xl border border-line/70 bg-surface px-4 py-3 text-sm font-semibold text-ink transition-colors hover:border-line-strong hover:bg-primary/5">Message review</a>
        </div>
      </div>
    </template>

    <section class="rounded-[1.9rem] border border-line/80 bg-[linear-gradient(140deg,_rgb(var(--panel-elevated-rgb)_/_0.96),_rgb(var(--accent-soft-rgb)_/_0.18))] p-6 shadow-panel">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p class="text-[10px] font-black uppercase tracking-[0.32em] text-aurora">Platform Admin</p>
          <h1 class="mt-2 text-3xl font-black tracking-tight text-ink lg:text-4xl">Model benchmark</h1>
          <p class="mt-2 max-w-3xl text-sm text-ink-muted">Run internal model comparison by latency and token usage without leaving the admin console.</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <TuiButton @click="runBenchmark" :loading="running">Run Benchmark</TuiButton>
        </div>
      </div>
      <p v-if="errorMessage" class="mt-4 rounded-2xl border border-danger/20 bg-danger/10 px-4 py-3 text-sm font-semibold text-danger">{{ errorMessage }}</p>
    </section>

    <div class="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
      <TuiCard title="Benchmark Config" subtitle="Prompt once, run across selected models">
        <div v-if="loadingModels" class="py-4 text-sm text-ink-muted">Loading model catalog...</div>
        <div v-else class="space-y-4">
          <label class="block text-xs font-bold uppercase tracking-wider text-ink-subtle">Models (one per line)</label>
          <textarea
            v-model="modelsText"
            rows="8"
            class="w-full rounded-2xl border border-line-strong bg-surface-elevated/90 px-4 py-3 font-mono text-sm text-ink outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
          />

          <label class="block text-xs font-bold uppercase tracking-wider text-ink-subtle">Prompt</label>
          <textarea
            v-model="prompt"
            rows="4"
            class="w-full rounded-2xl border border-line-strong bg-surface-elevated/90 px-4 py-3 text-sm text-ink outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
          />

          <div class="grid gap-3 md:grid-cols-3">
            <TuiInput v-model="runsPerModel" type="number" label="Runs / Model" />
            <TuiInput v-model="maxTokens" type="number" label="Max Tokens" />
            <TuiInput v-model="temperature" type="number" label="Temperature" />
          </div>

          <div class="flex justify-end">
            <TuiButton @click="runBenchmark" :loading="running">Run Benchmark</TuiButton>
          </div>
        </div>
      </TuiCard>

      <TuiCard v-if="benchmark" title="Summary" subtitle="Average speed and token usage per model">
        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="border-b border-line/70 text-left text-ink-subtle">
                <th class="py-2 pr-3">Model</th>
                <th class="py-2 pr-3">Schema</th>
                <th class="py-2 pr-3">Success</th>
                <th class="py-2 pr-3">Avg Latency (ms)</th>
                <th class="py-2 pr-3">Avg Prompt Tokens</th>
                <th class="py-2 pr-3">Avg Completion Tokens</th>
                <th class="py-2 pr-3">Avg Total Tokens</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in benchmark.summary" :key="`${row.provider}:${row.schema}:${row.model}`" class="border-b border-line/40">
                <td class="py-2 pr-3 font-semibold text-ink">{{ row.model }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.schema || 'n/a' }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.success_runs }}/{{ row.runs }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.avg_latency_ms !== null ? row.avg_latency_ms.toFixed(1) : 'n/a' }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.avg_prompt_tokens !== null ? row.avg_prompt_tokens.toFixed(1) : 'n/a' }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.avg_completion_tokens !== null ? row.avg_completion_tokens.toFixed(1) : 'n/a' }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.avg_total_tokens !== null ? row.avg_total_tokens.toFixed(1) : 'n/a' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </TuiCard>

      <TuiCard v-if="benchmark" title="Runs" subtitle="Per-run diagnostics">
        <div class="overflow-x-auto max-h-[26rem]">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="border-b border-line/70 text-left text-ink-subtle">
                <th class="py-2 pr-3">Model</th>
                <th class="py-2 pr-3">Run</th>
                <th class="py-2 pr-3">Status</th>
                <th class="py-2 pr-3">Latency (ms)</th>
                <th class="py-2 pr-3">Prompt</th>
                <th class="py-2 pr-3">Completion</th>
                <th class="py-2 pr-3">Total</th>
                <th class="py-2 pr-3">Error</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in benchmark.results" :key="`${row.model}:${row.run_index}:${row.latency_ms}`" class="border-b border-line/40">
                <td class="py-2 pr-3 font-semibold text-ink">{{ row.model }}</td>
                <td class="py-2 pr-3 text-ink-muted">#{{ row.run_index }}</td>
                <td class="py-2 pr-3">
                  <span :class="row.ok ? 'text-emerald-700' : 'text-red-600'">{{ row.ok ? 'ok' : 'failed' }}</span>
                </td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.latency_ms ?? 'n/a' }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.prompt_tokens }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.completion_tokens }}</td>
                <td class="py-2 pr-3 text-ink-muted">{{ row.total_tokens }}</td>
                <td class="py-2 pr-3 text-red-600">{{ row.error || '' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </TuiCard>
    </div>
  </PlatformAdminShell>
</template>
