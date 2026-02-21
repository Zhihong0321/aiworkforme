<script setup>
const props = defineProps({
  label: String,
  hint: String,
  placeholder: {
    type: String,
    default: ''
  },
  modelValue: {
    type: [String, Number],
    default: ''
  },
  type: {
    type: String,
    default: 'text'
  }
})

const emit = defineEmits(['update:modelValue'])

const onInput = (event) => {
  emit('update:modelValue', event.target.value)
}
</script>

<template>
  <label class="flex flex-col gap-2 text-sm text-[var(--text)]">
    <div class="flex items-center justify-between">
      <span class="text-xs uppercase tracking-wider text-[var(--muted)]">{{ label }}</span>
      <span v-if="hint" class="text-xs text-[var(--muted)]">{{ hint }}</span>
    </div>
    <input
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      class="w-full rounded-md border border-[var(--border-strong)] bg-white px-3 py-2 text-[var(--text)] transition focus:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[rgba(29,78,216,0.15)]"
      @input="onInput"
    />
  </label>
</template>
