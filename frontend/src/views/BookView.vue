<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api.js'
import { COMPANY, inr, longDate } from '../format.js'
import { openCheckout } from '../razorpay.js'
import SlotPicker from '../components/SlotPicker.vue'

const STEPS = ['Service', 'Date and time', 'Your details', 'Review and pay']
const step = ref(1)
const services = ref([])
const loadError = ref('')
const choice = reactive({ serviceId: null, slot: { date: null, time: null, label: null } })
const form = reactive({ name: '', email: '', phone: '', consent: false })
const touched = ref(false)
const paying = ref(false)
const payError = ref('')
const mockHold = ref(null) // test mode: no real Razorpay keys configured
const result = ref(null)
const picker = ref(null)

onMounted(async () => {
  try {
    services.value = await api.services()
  } catch (e) {
    loadError.value = e.message
  }
})

const service = computed(() => services.value.find((s) => s.id === choice.serviceId))
const errors = computed(() => ({
  name: form.name.trim().length < 2 ? 'Enter your full name.' : '',
  email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()) ? '' : 'Enter a valid email address.',
  phone: /^[0-9+\-\s]{7,20}$/.test(form.phone.trim()) ? '' : 'Enter a valid phone number.',
  consent: form.consent ? '' : 'Tick the box to continue.',
}))
const formValid = computed(() => Object.values(errors.value).every((e) => !e))

function next() {
  if (step.value === 3) {
    touched.value = true
    if (!formValid.value) return
  }
  step.value += 1
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
function back() {
  payError.value = ''
  step.value -= 1
}
function goTo(n) {
  if (n < step.value) step.value = n
}

async function pay() {
  payError.value = ''
  paying.value = true
  let hold
  try {
    hold = await api.hold({
      service_id: choice.serviceId,
      date: choice.slot.date,
      time: choice.slot.time,
      name: form.name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
    })
  } catch (e) {
    paying.value = false
    payError.value = e.message
    if (e.status === 409 || e.status === 400) {
      choice.slot = { date: choice.slot.date, time: null, label: null }
      step.value = 2
    }
    return
  }

  if (hold.order.mock) {
    mockHold.value = hold
    return
  }
  try {
    const outcome = await openCheckout({ order: hold.order, hold, company: COMPANY })
    if (outcome.status === 'paid') {
      await confirm(outcome.response)
    } else {
      await api.release(hold.order.id).catch(() => {})
      payError.value = outcome.failed
        ? 'The payment did not go through and the slot has been released. You can try again.'
        : 'Payment cancelled. The slot has been released.'
    }
  } catch (e) {
    await api.release(hold.order.id).catch(() => {})
    payError.value = e.message
  } finally {
    paying.value = false
  }
}

async function confirm(response) {
  try {
    result.value = await api.verify(response)
  } catch (e) {
    payError.value = e.message
  }
}

async function finishMock(success) {
  const hold = mockHold.value
  mockHold.value = null
  if (success) {
    await confirm({
      razorpay_order_id: hold.order.id,
      razorpay_payment_id: `pay_mock_${Date.now()}`,
      razorpay_signature: 'mock_signature',
    })
  } else {
    await api.release(hold.order.id).catch(() => {})
    payError.value = 'The payment did not go through and the slot has been released. You can try again.'
  }
  paying.value = false
}

function startOver() {
  result.value = null
  step.value = 1
  choice.serviceId = null
  choice.slot = { date: null, time: null, label: null }
  Object.assign(form, { name: '', email: '', phone: '', consent: false })
  touched.value = false
}
</script>

<template>
  <div class="page">
    <!-- Confirmation -->
    <section v-if="result" class="sheet stack" aria-live="polite">
      <template v-if="result.status === 'confirmed'">
        <p class="tag">Booking confirmed</p>
        <h1>You're booked, {{ result.client_name.split(' ')[0] }}</h1>
        <p class="muted">A confirmation email with these details is on its way to {{ result.client_email }}.</p>
        <table class="summary"><tbody>
          <tr><th>Booking ID</th><td>{{ result.reference }}</td></tr>
          <tr><th>Service</th><td>{{ result.service_name }}</td></tr>
          <tr><th>Date</th><td>{{ longDate(result.date) }}</td></tr>
          <tr><th>Time</th><td>{{ result.slot_label }} IST</td></tr>
          <tr><th>Amount paid</th><td>{{ inr(result.fee_inr) }}</td></tr>
          <tr>
            <th>Google Meet</th>
            <td>
              <a v-if="result.meet_link" :href="result.meet_link" target="_blank" rel="noopener">{{ result.meet_link }}</a>
              <span v-else class="muted">The link will arrive in your email.</span>
            </td>
          </tr>
        </tbody></table>
        <p class="small muted">Need to change it? Use the link in your email to reschedule or cancel up to 24 hours before the session.</p>
      </template>
      <template v-else>
        <p class="tag tag--danger">Payment refunded</p>
        <h1>That slot has just been taken</h1>
        <p>{{ result.message }}</p>
      </template>
      <div><button class="btn" type="button" @click="startOver">Book another consultation</button></div>
    </section>

    <!-- Booking steps -->
    <template v-else>
      <header class="intro">
        <h1>Book a consultation</h1>
        <p class="muted">Pick a service and a time. Your slot is confirmed as soon as the payment goes through.</p>
      </header>

      <ol class="steps" aria-label="Booking steps">
        <li v-for="(label, i) in STEPS" :key="label" :class="{ 'is-done': i + 1 < step, 'is-current': i + 1 === step }">
          <button type="button" :disabled="i + 1 >= step" :aria-current="i + 1 === step ? 'step' : undefined" @click="goTo(i + 1)">
            <span class="steps__n">{{ i + 1 }}</span><span class="steps__label">{{ label }}</span>
          </button>
        </li>
      </ol>

      <section class="sheet">
        <!-- 1. Service -->
        <div v-if="step === 1" class="stack">
          <h2>Which consultation do you need?</h2>
          <p v-if="loadError" class="notice notice--error">{{ loadError }}</p>
          <p v-else-if="!services.length" class="muted">Loading services…</p>
          <div class="services" role="radiogroup" aria-label="Services">
            <label v-for="s in services" :key="s.id" class="service" :class="{ 'is-on': choice.serviceId === s.id }">
              <input v-model="choice.serviceId" type="radio" name="service" :value="s.id" class="sr-only" />
              <span class="service__main">
                <span class="service__name">{{ s.name }}</span>
                <span class="small muted">{{ s.description }}</span>
              </span>
              <span class="service__meta">
                <span class="service__fee">{{ inr(s.fee_inr) }}</span>
                <span class="small muted">{{ s.duration_minutes }} min, online</span>
              </span>
            </label>
          </div>
          <div class="actions">
            <span class="spacer" />
            <button class="btn btn--primary" type="button" :disabled="!choice.serviceId" @click="next">Choose a time</button>
          </div>
        </div>

        <!-- 2. Date and time -->
        <div v-else-if="step === 2" class="stack">
          <h2>When would you like to meet?</h2>
          <p v-if="payError" class="notice notice--error">{{ payError }}</p>
          <SlotPicker ref="picker" v-model="choice.slot" />
          <div class="actions">
            <button class="btn" type="button" @click="back">Back</button>
            <span class="spacer" />
            <button class="btn btn--primary" type="button" :disabled="!choice.slot.time" @click="next">Enter your details</button>
          </div>
        </div>

        <!-- 3. Details -->
        <form v-else-if="step === 3" class="stack" novalidate @submit.prevent="next">
          <h2>Your details</h2>
          <p class="muted">We use these only to confirm and run this consultation. Please don't share case details here.</p>
          <div class="field" :data-invalid="touched && !!errors.name">
            <label for="name">Full name</label>
            <input id="name" v-model="form.name" autocomplete="name" required />
            <span v-if="touched && errors.name" class="error">{{ errors.name }}</span>
          </div>
          <div class="grid2">
            <div class="field" :data-invalid="touched && !!errors.email">
              <label for="email">Email</label>
              <input id="email" v-model="form.email" type="email" autocomplete="email" required />
              <span v-if="touched && errors.email" class="error">{{ errors.email }}</span>
            </div>
            <div class="field" :data-invalid="touched && !!errors.phone">
              <label for="phone">Phone number</label>
              <input id="phone" v-model="form.phone" type="tel" autocomplete="tel" placeholder="+91" required />
              <span v-if="touched && errors.phone" class="error">{{ errors.phone }}</span>
            </div>
          </div>
          <label class="check">
            <input v-model="form.consent" type="checkbox" />
            <span>I agree that {{ COMPANY }} may use these details to manage this booking and contact me about it.</span>
          </label>
          <span v-if="touched && errors.consent" class="small" style="color: var(--danger)">{{ errors.consent }}</span>
          <div class="actions">
            <button class="btn" type="button" @click="back">Back</button>
            <span class="spacer" />
            <button class="btn btn--primary" type="submit">Review booking</button>
          </div>
        </form>

        <!-- 4. Review and pay -->
        <div v-else class="stack">
          <h2>Check and pay</h2>
          <table class="summary"><tbody>
            <tr><th>Service</th><td>{{ service?.name }}</td></tr>
            <tr><th>Date</th><td>{{ longDate(choice.slot.date) }}</td></tr>
            <tr><th>Time</th><td>{{ choice.slot.label }} IST</td></tr>
            <tr><th>Session</th><td>{{ service?.duration_minutes }} minutes on Google Meet</td></tr>
            <tr><th>Name</th><td>{{ form.name }}</td></tr>
            <tr><th>Email</th><td>{{ form.email }}</td></tr>
            <tr><th>Phone</th><td>{{ form.phone }}</td></tr>
            <tr class="total"><th>Amount to pay</th><td>{{ inr(service?.fee_inr || 0) }}</td></tr>
          </tbody></table>
          <p class="small muted">
            Your slot is held while you pay. Cancel 24 hours or more before the session for a full refund. You can reschedule once.
          </p>
          <p v-if="payError" class="notice notice--error" role="alert">{{ payError }}</p>

          <div v-if="mockHold" class="notice notice--warn stack" role="dialog" aria-label="Test payment">
            <p><strong>Test mode.</strong> Razorpay keys are not set, so no real payment is taken.</p>
            <div class="row">
              <button class="btn btn--primary btn--small" type="button" @click="finishMock(true)">Simulate successful payment</button>
              <button class="btn btn--small" type="button" @click="finishMock(false)">Simulate failed payment</button>
            </div>
          </div>

          <div class="actions">
            <button class="btn" type="button" :disabled="paying" @click="back">Back</button>
            <span class="spacer" />
            <button class="btn btn--primary" type="button" :disabled="paying" @click="pay">
              {{ paying ? 'Opening payment…' : `Pay ${inr(service?.fee_inr || 0)}` }}
            </button>
          </div>
          <p class="small muted">Payments are processed securely by Razorpay: UPI, cards, net banking and wallets.</p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.intro { margin-bottom: 24px; display: grid; gap: 8px; }

.steps { list-style: none; padding: 0; margin: 0 0 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.steps button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0 8px;
  border: 0;
  border-top: 3px solid var(--line);
  background: none;
  font: inherit;
  color: var(--muted);
  text-align: left;
  cursor: pointer;
}
.steps button:disabled { cursor: default; }
.steps .is-done button { border-top-color: var(--seal); color: var(--ink); }
.steps .is-current button { border-top-color: var(--seal); color: var(--ink); font-weight: 600; }
.steps__n {
  flex: none;
  width: 22px; height: 22px;
  display: grid; place-items: center;
  border-radius: 50%;
  font-size: 12px;
  border: 1px solid currentColor;
}
.is-current .steps__n, .is-done .steps__n { background: var(--seal); border-color: var(--seal); color: #fff; }
.steps__label { font-size: var(--step--1); }
@media (max-width: 560px) { .steps__label { display: none; } .is-current .steps__label { display: inline; } }

.services { display: grid; gap: 10px; }
.service {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border: 1px solid var(--line);
  border-radius: var(--radius-m);
  cursor: pointer;
}
.service:hover { border-color: var(--seal); }
.service.is-on { border-color: var(--seal); background: var(--seal-soft); box-shadow: inset 0 0 0 1px var(--seal); }
.service:has(input:focus-visible) { box-shadow: var(--focus); }
.service__main, .service__meta { display: grid; gap: 2px; }
.service__meta { text-align: right; }
.service__name { font-weight: 600; font-size: var(--step-1); }
.service__fee { font-weight: 600; }

.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 560px) { .grid2 { grid-template-columns: 1fr; } }
.actions { display: flex; gap: 12px; align-items: center; padding-top: 8px; }
</style>