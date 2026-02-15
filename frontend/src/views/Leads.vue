<template>
  <div class="p-8">
    <header class="mb-8 flex justify-between items-center">
      <div>
        <h1 class="text-2xl font-bold mb-2">Leads</h1>
        <p class="text-[var(--muted)]">Manage and monitor your lead pipeline.</p>
      </div>
      <button class="bg-black text-white px-4 py-2 rounded font-bold">+ Import Leads</button>
    </header>

    <div class="bg-white border border-[var(--border)] rounded-lg overflow-hidden">
      <table class="w-full text-left text-sm">
        <thead class="bg-gray-50 border-b border-[var(--border)] uppercase text-[10px] tracking-wider font-bold">
          <tr>
            <th class="px-6 py-3">Lead</th>
            <th class="px-6 py-3">Stage</th>
            <th class="px-6 py-3">Behavior</th>
            <th class="px-6 py-3">Last Touch</th>
            <th class="px-6 py-3">Next Due</th>
            <th class="px-6 py-3">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          <tr v-for="i in 5" :key="i" class="hover:bg-gray-50">
            <td class="px-6 py-4">
              <div class="font-medium text-black">Lead #{{ i }}</div>
              <div class="text-[10px] text-[var(--muted)]">+1 555-010{{ i }}</div>
            </td>
            <td class="px-6 py-4">
              <span class="px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 text-[10px] font-bold border border-blue-100">ENGAGED</span>
            </td>
            <td class="px-6 py-4">
               <span class="px-2 py-0.5 rounded-full bg-green-50 text-green-600 text-[10px] font-bold border border-green-100">POSITIVE</span>
            </td>
            <td class="px-6 py-4 text-[var(--muted)]">24m ago</td>
            <td class="px-6 py-4 text-orange-600 font-medium">In 2h</td>
            <td class="px-6 py-4">
              <button class="text-blue-600 hover:underline">View</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
