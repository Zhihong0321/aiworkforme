<template>
  <div class="p-8">
    <header class="mb-8 flex justify-between items-center">
      <div>
        <h1 class="text-2xl font-bold mb-2">Knowledge Base</h1>
        <p class="text-[var(--muted)]">Upload documentation for the AI agent to reference during outreach.</p>
      </div>
      <button class="bg-black text-white px-4 py-2 rounded font-bold">+ Upload Source</button>
    </header>

    <div class="grid grid-cols-3 gap-6">
      <!-- Source List -->
      <div class="col-span-2 bg-white border border-[var(--border)] rounded-lg">
        <div class="p-4 border-b border-[var(--border)] flex justify-between items-center bg-gray-50">
           <span class="text-xs font-bold uppercase text-[var(--muted)]">Document Library</span>
           <span class="text-[10px] text-[var(--muted)]">3 Sources • 1.2MB total</span>
        </div>
        <div class="divide-y divide-[var(--border)]">
          <div v-for="i in 3" :key="i" class="p-4 flex justify-between items-center hover:bg-gray-50">
             <div class="flex items-center gap-3">
               <div class="w-10 h-10 bg-blue-50 text-blue-600 flex items-center justify-center rounded">PDF</div>
               <div>
                  <div class="text-sm font-bold">Product_Catalog_v{{ i }}.pdf</div>
                  <div class="text-[10px] text-[var(--muted)]">Uploaded Feb 15, 2026 • 50 chunks extracted</div>
               </div>
             </div>
             <button class="text-[var(--muted)] hover:text-black">•••</button>
          </div>
        </div>
      </div>

      <!-- Health/Stats -->
      <div class="space-y-6">
        <div class="bg-white p-4 border border-[var(--border)] rounded-lg">
           <h4 class="text-xs font-bold uppercase mb-4 text-[var(--muted)]">Retrieval Health</h4>
           <div class="space-y-2">
             <div class="flex justify-between text-sm">
               <span>Relevance Score</span>
               <span class="font-bold text-green-600">92%</span>
             </div>
             <div class="w-full bg-gray-100 h-1.5 rounded-full overflow-hidden">
               <div class="bg-green-500 h-full" style="width: 92%"></div>
             </div>
           </div>
        </div>
        
        <div class="bg-white p-4 border border-[var(--border)] rounded-lg">
           <h4 class="text-xs font-bold uppercase mb-4 text-[var(--muted)]">Token Usage</h4>
           <p class="text-[10px] text-[var(--muted)] mb-2">Knowledge retrieval accounts for 15% of total token usage.</p>
           <button class="text-xs text-blue-600 hover:underline">Optimize Chunks</button>
        </div>
      </div>
    </div>
  </div>
</template>
