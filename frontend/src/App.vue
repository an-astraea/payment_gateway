<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { COMPANY } from './format.js'

const route = useRoute()
watch(() => route.meta.title, (t) => { document.title = t ? `${t} | ${COMPANY}` : COMPANY }, { immediate: true })

// Put the seal logo at frontend/public/logo.png. Until then a simple seal is shown.
const logoOk = ref(true)
const logoSrc = '/logo.png' // bound dynamically so a missing file shows the fallback instead of a build error
const SITE = 'https://lextria.in'
const menuOpen = ref(false)
</script>

<template>
  <header class="topbar">
    <div class="topbar__inner">
      <a :href="SITE" class="brand">
        <img v-if="logoOk" :src="logoSrc" alt="" class="brand__logo" @error="logoOk = false" />
        <span v-else class="brand__seal" aria-hidden="true">LR</span>
        <span class="brand__name">{{ COMPANY }}</span>
      </a>

      <button class="menu-btn" type="button" :aria-expanded="menuOpen" aria-controls="main-nav" @click="menuOpen = !menuOpen">
        <span class="sr-only">Menu</span>
        <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
      </button>

      <nav id="main-nav" class="nav" :class="{ 'is-open': menuOpen }" aria-label="Main" @click="menuOpen = false">
        <a :href="SITE">Home</a>
        <a :href="`${SITE}/practice`">Practice areas</a>
        <a :href="`${SITE}/contact`">Contact us</a>
        <RouterLink to="/book" :class="{ 'is-active': route.path === '/book' || route.path.startsWith('/manage') }">Book a consultation</RouterLink>
      </nav>
    </div>
  </header>
  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.topbar { background: var(--paper); box-shadow: 0 2px 18px rgba(15, 23, 42, 0.06); position: sticky; top: 0; z-index: 20; }
.topbar__inner { max-width: 1400px; margin: 0 auto; padding: 16px 32px; display: flex; align-items: center; gap: 24px; }

.brand { display: flex; align-items: center; gap: 18px; text-decoration: none; color: var(--ink); }
.brand__logo { width: 58px; height: 58px; object-fit: contain; border-radius: 50%; }
.brand__seal {
  width: 58px; height: 58px; border-radius: 50%;
  display: grid; place-items: center;
  background: radial-gradient(circle at 50% 45%, #2b3f73 0%, #1b2a52 70%);
  border: 3px solid #c9a227;
  color: #f5d76e; font-family: var(--display); font-size: 1rem;
}
.brand__name { font-weight: 700; font-size: clamp(1.35rem, 2.4vw, 2.1rem); letter-spacing: -0.01em; }

.nav { margin-left: auto; display: flex; gap: clamp(20px, 3vw, 56px); }
.nav a {
  position: relative;
  color: var(--slate);
  text-decoration: none;
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 10px 0 12px;
}
.nav a::after {
  content: '';
  position: absolute; left: 0; right: 0; bottom: 0;
  height: 3px; border-radius: 3px;
  background: var(--gold);
  transform: scaleX(0); transform-origin: left;
  transition: transform 0.2s ease;
}
.nav a:hover { color: var(--gold-text); }
.nav a.is-active { color: var(--gold-text); }
.nav a.is-active::after, .nav a:hover::after { transform: scaleX(1); }

.menu-btn { display: none; margin-left: auto; border: 0; background: none; color: var(--ink); padding: 8px; cursor: pointer; border-radius: 10px; }

@media (max-width: 900px) {
  .topbar__inner { padding: 12px 18px; flex-wrap: wrap; }
  .brand__logo, .brand__seal { width: 46px; height: 46px; }
  .menu-btn { display: block; }
  .nav { display: none; width: 100%; flex-direction: column; gap: 0; margin: 0; }
  .nav.is-open { display: flex; }
  .nav a { padding: 14px 4px; border-top: 1px solid var(--line); }
  .nav a::after { display: none; }
}
</style>