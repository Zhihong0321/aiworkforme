<template>
  <div class="p-8">
    <header class="mb-8">
      <h1 class="text-2xl font-bold mb-2">Analytics</h1>
      <p class="text-[var(--muted)]">Track performance against your Pilot KPIs.</p>
    </header>

    <!-- North Star KPI -->
    <div class="grid grid-cols-4 gap-6 mb-8">
      <div v-for="stat in stats" :key="stat.label" class="bg-white p-6 border border-[var(--border)] rounded-lg shadow-sm">
        <div class="text-xs font-bold uppercase text-[var(--muted)] mb-2">{{ stat.label }}</div>
        <div class="text-3xl font-bold mb-1">{{ stat.value }}</div>
        <div class="text-[10px]" :class="stat.trend > 0 ? 'text-green-600' : 'text-red-600'">
          {{ stat.trend > 0 ? '↑' : '↓' }} {{ Math.abs(stat.trend) }}% vs baseline
        </div>
      </div>
    </div>

    <!-- Charts Placeholder -->
    <div class="grid grid-cols-2 gap-6">
      <div class="bg-white p-6 border border-[var(--border)] rounded-lg h-80 flex flex-col justify-between">
        <h4 class="font-bold text-sm">Conversion Funnel</h4>
        <div class="flex-grow flex items-center justify-center text-[var(--muted)] italic">
          Funnel visualization placeholder
        </div>
      </div>
      <div class="bg-white p-6 border border-[var(--border)] rounded-lg h-80 flex flex-col justify-between">
        <h4 class="font-bold text-sm">Policy Health (Blocks)</h4>
        <div class="flex-grow flex items-center justify-center text-[var(--muted)] italic">
          Pie chart: Quiet Hours vs Outbound Cap
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const stats = [
  { label: 'Outcomes / 100 Leads', value: '18.2', trend: 15.4 },
  { label: 'Avg Responsiveness', value: '8.4s', trend: -20.0 },
  { label: 'AI Cost Share', value: '14.5%', trend: -5.2 },
  { label: 'Negative Signals', value: '1.2%', trend: -0.8 }
]
</script>
