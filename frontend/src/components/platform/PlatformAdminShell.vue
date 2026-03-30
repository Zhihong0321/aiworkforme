<template>
  <div class="relative min-h-[calc(100vh-1rem)]">
    <div class="mx-auto w-full max-w-[1800px] px-4 pb-8 pt-6 lg:px-6 xl:px-8">
      <div class="rounded-[2rem] border border-line/70 bg-[linear-gradient(140deg,_rgb(var(--panel-elevated-rgb)_/_0.92),_rgb(var(--panel-rgb)_/_0.84),_rgb(var(--accent-soft-rgb)_/_0.3))] p-4 shadow-[0_30px_60px_-34px_rgb(var(--text-rgb)_/_0.35)] backdrop-blur-xl lg:p-6">
        <div class="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[320px_minmax(0,1fr)]">
          <aside class="hidden lg:block">
            <div class="sticky top-28 space-y-4">
              <slot name="sidebar" />
            </div>
          </aside>

          <main class="min-w-0 space-y-6">
            <slot />
          </main>
        </div>
      </div>
    </div>

    <div class="px-4 pb-8 lg:hidden">
      <div class="mx-auto max-w-2xl rounded-[1.75rem] border border-warning/25 bg-warning/10 px-5 py-6 text-ink shadow-panel">
        <p class="text-[10px] font-black uppercase tracking-[0.28em] text-warning">Desktop only</p>
        <h2 class="mt-2 text-xl font-semibold text-ink">Platform admin is optimized for laptops and desktops</h2>
        <p class="mt-2 text-sm text-ink-muted">
          This console manages platform-wide settings, message review, and benchmarking. Please use a wider screen for the best experience.
        </p>
      </div>
    </div>
  </div>
</template>
