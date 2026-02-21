<script setup>
import { computed, onMounted, ref } from 'vue'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
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
  } catch (e) {
    errorMessage.value = `Failed to load model catalog: ${e.message}`
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
  } catch (e) {
    errorMessage.value = `Benchmark failed: ${e.message}`
  } finally {
    running.value = false
  }
}

onMounted(() => {
  hydrateModelCatalog()
})
</script>

<template>
  <div class="relative min-h-screen">
    <main class="relative z-10 mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-10 space-y-6">
      <header class="tui-surface rounded-3xl border border-slate-200 p-8 shadow-sm">
        <p class="text-[10px] uppercase font-black tracking-[0.32em] text-indigo-600">Platform Admin</p>
        <h1 class="mt-2 text-3xl font-black text-slate-900 tracking-tight">Model Benchmark</h1>
        <p class="mt-2 text-sm text-slate-600">Run internal model comparison by latency and token usage.</p>
      </header>

      <TuiCard title="Benchmark Config" subtitle="Prompt once, run across selected models">
        <div v-if="loadingModels" class="text-sm text-slate-600 py-4">Loading model catalog...</div>
        <div v-else class="space-y-4">
          <label class="text-xs font-bold uppercase tracking-wider text-slate-700 block">Models (one per line)</label>
          <textarea
            v-model="modelsText"
            rows="8"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-200 font-mono"
          />

          <label class="text-xs font-bold uppercase tracking-wider text-slate-700 block">Prompt</label>
          <textarea
            v-model="prompt"
            rows="4"
            class="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-200"
          />

          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <TuiInput v-model="runsPerModel" type="number" label="Runs / Model" />
            <TuiInput v-model="maxTokens" type="number" label="Max Tokens" />
            <TuiInput v-model="temperature" type="number" label="Temperature" />
          </div>

          <div class="flex justify-end">
            <TuiButton @click="runBenchmark" :loading="running">Run Benchmark</TuiButton>
          </div>
          <p v-if="errorMessage" class="text-xs font-semibold text-red-600">{{ errorMessage }}</p>
        </div>
      </TuiCard>

      <TuiCard v-if="benchmark" title="Summary" subtitle="Average speed and token usage per model">
        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="text-left text-slate-600 border-b border-slate-200">
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
              <tr v-for="row in benchmark.summary" :key="`${row.provider}:${row.schema}:${row.model}`" class="border-b border-slate-100">
                <td class="py-2 pr-3 font-semibold">{{ row.model }}</td>
                <td class="py-2 pr-3">{{ row.schema || 'n/a' }}</td>
                <td class="py-2 pr-3">{{ row.success_runs }}/{{ row.runs }}</td>
                <td class="py-2 pr-3">{{ row.avg_latency_ms !== null ? row.avg_latency_ms.toFixed(1) : 'n/a' }}</td>
                <td class="py-2 pr-3">{{ row.avg_prompt_tokens !== null ? row.avg_prompt_tokens.toFixed(1) : 'n/a' }}</td>
                <td class="py-2 pr-3">{{ row.avg_completion_tokens !== null ? row.avg_completion_tokens.toFixed(1) : 'n/a' }}</td>
                <td class="py-2 pr-3">{{ row.avg_total_tokens !== null ? row.avg_total_tokens.toFixed(1) : 'n/a' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </TuiCard>

      <TuiCard v-if="benchmark" title="Runs" subtitle="Per-run diagnostics">
        <div class="overflow-x-auto max-h-[26rem]">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="text-left text-slate-600 border-b border-slate-200">
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
              <tr v-for="row in benchmark.results" :key="`${row.model}:${row.run_index}:${row.latency_ms}`" class="border-b border-slate-100">
                <td class="py-2 pr-3 font-semibold">{{ row.model }}</td>
                <td class="py-2 pr-3">#{{ row.run_index }}</td>
                <td class="py-2 pr-3">
                  <span :class="row.ok ? 'text-emerald-700' : 'text-red-600'">{{ row.ok ? 'ok' : 'failed' }}</span>
                </td>
                <td class="py-2 pr-3">{{ row.latency_ms ?? 'n/a' }}</td>
                <td class="py-2 pr-3">{{ row.prompt_tokens }}</td>
                <td class="py-2 pr-3">{{ row.completion_tokens }}</td>
                <td class="py-2 pr-3">{{ row.total_tokens }}</td>
                <td class="py-2 pr-3 text-red-600">{{ row.error || '' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </TuiCard>
    </main>
  </div>
</template>
