<script setup>
/**
 * Date strip + the day's fixed slots. Each day shows three seat marks: a filled mark is a
 * booked slot, an open mark is free. Used for new bookings and for rescheduling.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api.js'
import { dayNumber, longDate, monthShort, weekday } from '../format.js'

const props = defineProps({
  /** { date: 'YYYY-MM-DD', time: 'HH:MM', label: '10:00 AM - 11:00 AM' } */
  modelValue: { type: Object, default: () => ({ date: null, time: null, label: null }) },
  /** slot to show as the client's current one (rescheduling) */
  current: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])

const days = ref([])
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    days.value = await api.availability()
    const chosen = days.value.find((d) => d.date === props.modelValue.date)
    if (chosen && props.modelValue.time && !chosen.slots.find((s) => s.time === props.modelValue.time)?.available) {
      emit('update:modelValue', { date: chosen.date, time: null, label: null })
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)
defineExpose({ reload: load })

const selectedDay = computed(() => days.value.find((d) => d.date === props.modelValue.date) || null)
const freeCount = (day) => day.slots.filter((s) => s.available).length

function pickDay(day) {
  if (!day.open || freeCount(day) === 0) return
  emit('update:modelValue', { date: day.date, time: null, label: null })
}
function pickTime(slot) {
  if (!slot.available) return
  emit('update:modelValue', { date: props.modelValue.date, time: slot.time, label: slot.label })
}

const closedText = { too_soon: 'Closed', non_working_day: 'Closed', holiday: 'Holiday', beyond_horizon: 'Closed' }
const isCurrent = (date, time) => props.current && props.current.date === date && props.current.time === time

// keep the selected day in view on small screens
const strip = ref(null)
watch(() => props.modelValue.date, () => {
  requestAnimationFrame(() => strip.value?.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' }))
})
</script>

<template>
  <div class="picker">
    <p v-if="loading" class="muted">Loading open slots…</p>
    <div v-else-if="error" class="notice notice--error row">
      <span>{{ error }}</span><span class="spacer" />
      <button class="btn btn--small" type="button" @click="load">Try again</button>
    </div>

    <template v-else>
      <div class="legend small muted" aria-hidden="true">
        <span><i class="seat seat--free" /> open slot</span>
        <span><i class="seat seat--taken" /> booked</span>
      </div>

      <div ref="strip" class="strip" role="group" aria-label="Choose a date">
        <button
          v-for="day in days"
          :key="day.date"
          type="button"
          class="day"
          :class="{ 'day--closed': !day.open, 'day--full': day.open && freeCount(day) === 0 }"
          :aria-pressed="modelValue.date === day.date"
          :disabled="!day.open || freeCount(day) === 0"
          :aria-label="`${longDate(day.date)}: ${day.open ? `${freeCount(day)} of ${day.slots.length} slots open` : 'closed'}`"
          @click="pickDay(day)"
        >
          <span class="day__wd">{{ weekday(day.date) }}</span>
          <span class="day__num">{{ dayNumber(day.date) }}</span>
          <span class="day__mon">{{ monthShort(day.date) }}</span>
          <span v-if="day.open" class="seats">
            <i v-for="s in day.slots" :key="s.time" class="seat" :class="s.available ? 'seat--free' : 'seat--taken'" />
          </span>
          <span v-else class="day__closed">{{ closedText[day.closed_reason] || 'Closed' }}</span>
        </button>
      </div>

      <div v-if="selectedDay" class="times">
        <h3>{{ longDate(selectedDay.date) }}</h3>
        <p class="muted small">{{ freeCount(selectedDay) }} of {{ selectedDay.slots.length }} slots open. Times are in IST.</p>
        <div class="times__list" role="radiogroup" :aria-label="`Times on ${longDate(selectedDay.date)}`">
          <button
            v-for="slot in selectedDay.slots"
            :key="slot.time"
            type="button"
            role="radio"
            class="time"
            :aria-checked="modelValue.time === slot.time"
            :disabled="!slot.available"
            @click="pickTime(slot)"
          >
            <span class="time__label">{{ slot.label }}</span>
            <span v-if="isCurrent(selectedDay.date, slot.time)" class="small">Your current slot</span>
            <span v-else-if="!slot.available" class="small">Booked</span>
          </button>
        </div>
      </div>
      <p v-else class="muted">Choose a date to see its times.</p>
    </template>
  </div>
</template>

<style scoped>
.picker { display: grid; gap: 20px; }
.legend { display: flex; gap: 20px; font-weight: 600; }
.legend span { display: inline-flex; align-items: center; gap: 8px; }

.strip { display: flex; gap: 10px; overflow-x: auto; padding: 4px 4px 14px; scroll-snap-type: x proximity; }
.day {
  flex: 0 0 84px;
  scroll-snap-align: start;
  display: grid; justify-items: center; gap: 2px;
  padding: 12px 6px 14px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--paper);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
  color: var(--ink);
  font: inherit;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.day:hover:not(:disabled) { border-color: var(--gold); box-shadow: 0 8px 20px rgba(234, 179, 8, 0.18); }
.day[aria-pressed='true'] { background: var(--gold-gradient); border-color: #d9a406; box-shadow: var(--shadow-gold); }
.day[aria-pressed='true'] .day__wd, .day[aria-pressed='true'] .day__mon { color: rgba(30, 41, 59, 0.8); }
.day:disabled { cursor: not-allowed; }
.day--closed { background: #f1f5f9; box-shadow: none; border-style: dashed; color: var(--muted); }
.day--full { color: var(--muted); background: #f8fafc; }
.day__wd, .day__mon { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); }
.day__num { font-family: var(--display); font-size: 1.6rem; line-height: 1.15; }
.day__closed { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; margin-top: 6px; }

.seats { display: flex; gap: 4px; margin-top: 8px; }
.seat { display: inline-block; width: 15px; height: 6px; border-radius: 3px; }
.seat--free { border: 1.5px solid var(--gold); background: #fff; }
.seat--taken { background: var(--slate); }
.day[aria-pressed='true'] .seat--free { border-color: #fff; background: rgba(255, 255, 255, 0.6); }
.day[aria-pressed='true'] .seat--taken { background: var(--ink); }

.times { display: grid; gap: 6px; padding: 22px; border-radius: 20px; background: #fcfdfe; border: 1px solid var(--line); }
.times h3 { font-size: 1.15rem; }
.times__list { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-top: 10px; }
.time {
  display: grid; gap: 4px;
  text-align: left;
  padding: 16px 20px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--paper);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  font: inherit;
  color: var(--ink);
  cursor: pointer;
  min-height: 64px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.time:hover:not(:disabled) { border-color: var(--gold); }
.time[aria-checked='true'] { background: var(--gold-gradient); border-color: #d9a406; box-shadow: var(--shadow-gold); }
.time:disabled { color: var(--muted); background: #f1f5f9; box-shadow: none; cursor: not-allowed; }
.time:disabled .time__label { text-decoration: line-through; text-decoration-color: rgba(100, 116, 139, 0.6); }
.time__label { font-weight: 700; font-size: 1.02rem; }
.time .small { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
</style>