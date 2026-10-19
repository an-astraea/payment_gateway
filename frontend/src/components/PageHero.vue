<script setup>
/** Dark banner matching the lextria.in page heroes: gold pill badge, heavy title with a gold
 * highlighted phrase, short lead text. */
defineProps({
  badge: { type: String, default: '' },
  title: { type: String, required: true },
  highlight: { type: String, default: '' },
  text: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})
</script>

<template>
  <section class="hero" :class="{ 'hero--compact': compact }">
    <!-- Floating bubbles, as on lextria.in: soft, translucent, drifting out of sync -->
    <span class="bubble bubble--1" aria-hidden="true" />
    <span class="bubble bubble--2" aria-hidden="true" />
    <span class="bubble bubble--3" aria-hidden="true" />
    <span class="bubble bubble--4" aria-hidden="true" />
    <div class="hero__inner">
      <p v-if="badge" class="hero__badge">{{ badge }}</p>
      <h1 class="hero__title">
        {{ title }}<template v-if="highlight">&nbsp;<span class="hero__gold">{{ highlight }}</span></template>
      </h1>
      <p v-if="text" class="hero__text">{{ text }}</p>
      <slot />
    </div>
  </section>
</template>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  background: var(--hero);
  color: #fff;
  padding: 80px 20px 120px;
  clip-path: polygon(0 0, 100% 0, 100% calc(100% - 48px), 50% 100%, 0 calc(100% - 48px));
}
.hero--compact { padding: 52px 20px 96px; }
.hero__inner { position: relative; max-width: 960px; margin: 0 auto; text-align: center; display: grid; justify-items: center; gap: 22px; }

.hero__badge {
  display: inline-block;
  padding: 12px 30px;
  border-radius: 999px;
  background: var(--gold-gradient);
  color: #3f3a1e;
  font-weight: 700;
  font-size: 0.9rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  box-shadow: 0 10px 30px rgba(234, 179, 8, 0.35);
}
.hero__title {
  font-family: var(--display);
  font-weight: 400;
  color: #fff;
  font-size: clamp(2.3rem, 6vw, 4.6rem);
  line-height: 1.08;
  text-shadow: 0 6px 24px rgba(0, 0, 0, 0.25);
}
.hero--compact .hero__title { font-size: clamp(2rem, 4.6vw, 3.4rem); }
.hero__gold {
  display: inline-block;
  background: linear-gradient(135deg, #eab308 0%, #f6b40f 60%, #f59e0b 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: none;
  padding-bottom: 6px;
  border-bottom: 2px solid rgba(234, 179, 8, 0.55);
}
.hero__text { max-width: 720px; font-size: clamp(1.05rem, 2vw, 1.3rem); line-height: 1.55; color: rgba(255, 255, 255, 0.86); }

/* Bubbles ------------------------------------------------------------------ */
.bubble {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  /* flat, soft circle: blue top-left blending to gold bottom-right, like lextria.in */
  background: linear-gradient(135deg, rgba(125, 155, 215, 0.38) 0%, rgba(140, 150, 160, 0.3) 50%, rgba(200, 165, 55, 0.4) 100%);
  filter: blur(1.5px);
  will-change: transform;
  animation: float 5s ease-in-out infinite;
}
/* size, position, speed and start point differ so they never move in step */
.bubble--1 { width: 76px;  height: 76px;  left: 10%; top: 12%; animation-duration: 5.2s; animation-delay: -1.1s; }
.bubble--2 { width: 128px; height: 128px; right: 24%; top: 24%; animation-duration: 6.4s; animation-delay: -3s; }
.bubble--3 { width: 100px; height: 100px; right: 14%; top: 58%; animation-name: float-drift; animation-duration: 5.8s; animation-delay: -0.4s; }
.bubble--4 { width: 50px;  height: 50px;  left: 20%; top: 66%; animation-duration: 4.6s; animation-delay: -2.2s; }

@keyframes float {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
  50%      { transform: translate3d(0, -24px, 0) scale(1.03); }
}
@keyframes float-drift {
  0%, 100% { transform: translate3d(0, 0, 0); }
  33%      { transform: translate3d(28px, -16px, 0); }
  66%      { transform: translate3d(48px, 8px, 0); }
}
@media (prefers-reduced-motion: reduce) {
  .bubble { animation: none; }
}
@media (max-width: 640px) {
  .hero { padding: 56px 18px 96px; }
  .bubble--2 { width: 80px; height: 80px; right: 4%; top: 46%; }
  .bubble--3 { display: none; }
}
</style>