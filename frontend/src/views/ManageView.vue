<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api.js'
import { inr, longDate } from '../format.js'
import SlotPicker from '../components/SlotPicker.vue'
import PageHero from '../components/PageHero.vue'

const token = useRoute().params.token
const booking = ref(null)
const loadError = ref('')
const mode = ref('view') // view | reschedule | cancel
const newSlot = ref({ date: null, time: null, label: null })
const busy = ref(false)
const error = ref('')
const done = ref('')

onMounted(async () => {
  try {
    booking.value = await api.manage(token)
  } catch (e) {
    loadError.value = e.message
  }
})

function open(m) {
  error.value = ''
  done.value = ''
  mode.value = m
}

async function reschedule() {
  busy.value = true
  error.value = ''
  try {
    booking.value = await api.reschedule(token, newSlot.value.date, newSlot.value.time)
    done.value = 'Your booking has been moved. We have emailed you the new time. The Google Meet link stays the same.'
    mode.value = 'view'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function cancel() {
  busy.value = true
  error.value = ''
  try {
    booking.value = await api.cancel(token)
    done.value = booking.value.refund_inr
      ? `Your booking is cancelled. A refund of ${inr(booking.value.refund_inr)} has been started and usually arrives in 5-7 working days.`
      : 'Your booking is cancelled.'
    mode.value = 'view'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

const statusText = {
  confirmed: 'Confirmed',
  cancelled: 'Cancelled',
  refunded_conflict: 'Refunded',
  pending_payment: 'Awaiting payment',
  expired: 'Not completed',
  payment_failed: 'Not completed',
}
</script>

<template>
  <PageHero badge="Your consultation" title="Manage your" highlight="Booking" text="Reschedule once or cancel for a full refund, up to 24 hours before your session." compact />

  <div class="page page--over">
    <p v-if="loadError" class="sheet notice--error">{{ loadError }}</p>
    <p v-else-if="!booking" class="sheet muted">Loading your booking…</p>

    <section v-else class="sheet stack">
      <div class="card-head">
        <span class="tile" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></svg>
        </span>
        <div class="card-head__text">
          <span><span class="tag" :class="booking.status === 'confirmed' ? 'tag--ok' : 'tag--danger'">{{ statusText[booking.status] || booking.status }}</span></span>
          <h2>Booking {{ booking.reference }}</h2>
        </div>
        <span class="gold-rule" />
      </div>
      <p v-if="done" class="notice" role="status">{{ done }}</p>

      <table class="summary"><tbody>
        <tr><th>Booking ID</th><td>{{ booking.reference }}</td></tr>
        <tr><th>Service</th><td>{{ booking.service_name }}</td></tr>
        <tr><th>Date</th><td>{{ longDate(booking.date) }}</td></tr>
        <tr><th>Time</th><td>{{ booking.slot_label }} IST</td></tr>
        <tr><th>Amount paid</th><td>{{ inr(booking.fee_inr) }}</td></tr>
        <tr v-if="booking.refund_inr"><th>Refunded</th><td>{{ inr(booking.refund_inr) }}</td></tr>
        <tr v-if="booking.meet_link && booking.status === 'confirmed'">
          <th>Google Meet</th>
          <td><a :href="booking.meet_link" target="_blank" rel="noopener">{{ booking.meet_link }}</a></td>
        </tr>
      </tbody></table>

      <template v-if="booking.status === 'confirmed'">
        <template v-if="booking.can_change">
          <div v-if="mode === 'view'" class="row">
            <button v-if="booking.reschedules_left > 0" class="btn btn--primary" type="button" @click="open('reschedule')">Reschedule</button>
            <button class="btn btn--danger" type="button" @click="open('cancel')">Cancel booking</button>
          </div>
          <p v-if="mode === 'view' && booking.reschedules_left === 0" class="small muted">
            This booking has already been rescheduled once. To change it again, contact us.
          </p>

          <div v-if="mode === 'reschedule'" class="stack">
            <h2>Choose a new time</h2>
            <p class="muted">You can reschedule once, free of charge.</p>
            <SlotPicker v-model="newSlot" :current="{ date: booking.date, time: booking.time }" />
            <p v-if="error" class="notice notice--error" role="alert">{{ error }}</p>
            <div class="row">
              <button class="btn" type="button" :disabled="busy" @click="open('view')">Keep my current time</button>
              <span class="spacer" />
              <button class="btn btn--primary" type="button" :disabled="busy || !newSlot.time" @click="reschedule">
                {{ busy ? 'Moving…' : newSlot.time ? `Move to ${longDate(newSlot.date)}, ${newSlot.label}` : 'Move booking' }}
              </button>
            </div>
          </div>

          <div v-if="mode === 'cancel'" class="notice notice--warn stack" role="alertdialog" aria-label="Cancel booking">
            <p><strong>Cancel this booking?</strong> You will get a full refund of {{ inr(booking.fee_inr) }}. It usually reaches your account in 5-7 working days.</p>
            <p v-if="error" class="notice notice--error" role="alert">{{ error }}</p>
            <div class="row">
              <button class="btn btn--danger" type="button" :disabled="busy" @click="cancel">{{ busy ? 'Cancelling…' : 'Cancel and refund' }}</button>
              <button class="btn" type="button" :disabled="busy" @click="open('view')">Keep my booking</button>
            </div>
          </div>
        </template>
        <p v-else class="notice notice--warn">
          Changes close 24 hours before the session, so this booking can no longer be moved or cancelled online. Contact us if you need help.
        </p>
      </template>
    </section>
  </div>
</template>