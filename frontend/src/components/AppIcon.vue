<script setup lang="ts">
defineProps<{ name: string }>()
</script>

<template>
  <svg v-if="name === 'landmark'" viewBox="0 0 24 24"><path d="M3 10h18M5 10V8l7-4 7 4v2M6 10v8m4-8v8m4-8v8m4-8v8M3 20h18" /></svg>
  <svg v-else-if="name === 'document'" viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h6M9 16h6" /></svg>
  <svg v-else-if="name === 'check'" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m8 12 2.7 2.8L16.5 9"/></svg>
  <svg v-else-if="name === 'clock'" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
  <svg v-else-if="name === 'rate'" viewBox="0 0 24 24"><path d="M4 19V9m5 10V5m5 14v-7m5 7V3"/></svg>
  <svg v-else-if="name === 'spark'" viewBox="0 0 24 24"><path d="m12 3 1.4 4.1L17.5 8l-4.1 1.4L12 13.5l-1.4-4.1L6.5 8l4.1-.9zM18 14l.8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8z"/></svg>
  <svg v-else-if="name === 'refresh'" viewBox="0 0 24 24"><path d="M20 7v5h-5M4 17v-5h5M18.5 9A7 7 0 0 0 6 7l-2 5m2 3a7 7 0 0 0 12.5 2l1.5-5"/></svg>
  <svg v-else-if="name === 'arrow-up'" viewBox="0 0 24 24"><path d="m7 14 5-5 5 5"/></svg>
  <svg v-else-if="name === 'send'" viewBox="0 0 24 24"><path d="m3 4 18 8-18 8 3-8zm3 8h15"/></svg>
  <svg v-else-if="name === 'close'" viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18"/></svg>
  <svg v-else-if="name === 'database'" viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg>
  <svg v-else-if="name === 'menu'" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
  <svg v-else viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/></svg>
</template>

<style scoped>
svg { width: 1em; height: 1em; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
</style>
