<script setup>
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { COMPANY } from './format.js'

const route = useRoute()
watch(() => route.meta.title, (t) => { document.title = t ? `${t} | ${COMPANY}` : COMPANY }, { immediate: true })
</script>

<template>
  <header class="topbar">
    <div class="topbar__inner">
      <RouterLink to="/book" class="brand">{{ COMPANY }}</RouterLink>
      <nav class="topbar__nav" aria-label="Main">
        <RouterLink to="/book">Book a consultation</RouterLink>
        <RouterLink to="/admin">Dashboard</RouterLink>
      </nav>
    </div>
  </header>
  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.topbar { background: var(--paper); border-bottom: 1px solid var(--line); }
.topbar__inner { max-width: 1120px; margin: 0 auto; padding: 14px 20px; display: flex; align-items: center; gap: 24px; }
.brand { font-weight: 600; color: var(--ink); text-decoration: none; font-size: var(--step-1); }
.topbar__nav { margin-left: auto; display: flex; gap: 20px; }
.topbar__nav a { color: var(--muted); text-decoration: none; font-weight: 500; }
.topbar__nav a.router-link-active { color: var(--seal); }
</style>
