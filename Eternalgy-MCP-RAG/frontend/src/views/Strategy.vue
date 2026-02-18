<template>
  <div class="p-8 max-w-4xl mx-auto">
    <header class="mb-8">
      <h1 class="text-2xl font-bold mb-2">Outreach Strategy</h1>
      <p class="text-[var(--muted)]">Design how your AI agent approaches and converts leads.</p>
    </header>

    <div class="space-y-6">
      <!-- Tone Section -->
      <section class="bg-white p-6 border border-[var(--border)] rounded-lg shadow-sm">
        <h3 class="font-bold mb-4">Messaging Persona</h3>
        <div class="space-y-4">
          <div>
            <label class="block text-xs font-bold uppercase mb-1 text-[var(--muted)]">Tone & Style</label>
            <textarea class="w-full border border-[var(--border)] rounded p-2 text-sm" rows="3" placeholder="e.g. Professional yet friendly, focused on value..."></textarea>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-bold uppercase mb-1 text-[var(--muted)]">Aggressiveness</label>
              <select class="w-full border border-[var(--border)] rounded p-2 text-sm">
                <option>Gentle</option>
                <option selected>Balanced</option>
                <option>Aggressive</option>
              </select>
            </div>
            <div>
               <label class="block text-xs font-bold uppercase mb-1 text-[var(--muted)]">Language</label>
               <select class="w-full border border-[var(--border)] rounded p-2 text-sm">
                 <option>English</option>
                 <option>Spanish</option>
               </select>
            </div>
          </div>
        </div>
      </section>

      <!-- Simulation Bench -->
      <section class="bg-[var(--accent-soft)] p-6 border border-[#ff820033] rounded-lg">
        <div class="flex justify-between items-center mb-4">
          <h3 class="font-bold">Simulation Bench</h3>
          <span class="text-[10px] bg-[#ff8200] text-white px-2 py-0.5 rounded font-bold uppercase">Ready</span>
        </div>
        <p class="text-sm mb-4">Run 50 simulated conversations to test this strategy before activating.</p>
        <button class="w-full bg-black text-white py-2 rounded font-bold text-sm">Run Simulation</button>
      </section>

      <!-- Controls -->
      <div class="flex justify-end gap-3">
        <button class="px-6 py-2 border border-[var(--border)] rounded font-bold text-sm">Save Draft</button>
        <button class="px-6 py-2 bg-black text-white rounded font-bold text-sm">Activate Strategy</button>
      </div>
    </div>
  </div>
</template>
