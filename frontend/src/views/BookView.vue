<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api.js'
import { COMPANY, inr, longDate } from '../format.js'
import { openCheckout } from '../razorpay.js'
import SlotPicker from '../components/SlotPicker.vue'
import PageHero from '../components/PageHero.vue'

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

// Coupon: only on the payment step. The admin emails the code to the client.
const couponOpen = ref(false)
const couponInput = ref('')
const coupon = ref(null) // { code, percent, base_fee_inr, discount_inr, total_inr }
const couponError = ref('')
const couponBusy = ref(false)
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

const amountToPay = computed(() => (coupon.value ? coupon.value.total_inr : service.value?.fee_inr || 0))

async function applyCoupon() {
  couponError.value = ''
  if (!couponInput.value.trim()) {
    couponError.value = 'Enter the coupon code from your email.'
    return
  }
  couponBusy.value = true
  try {
    coupon.value = await api.checkCoupon(couponInput.value.trim(), choice.serviceId, form.email.trim())
    couponInput.value = ''
  } catch (e) {
    couponError.value = e.message
  } finally {
    couponBusy.value = false
  }
}
function removeCoupon() {
  coupon.value = null
  couponError.value = ''
}
// a changed service or email must be checked again
watch(() => [choice.serviceId, form.email], () => { if (coupon.value) removeCoupon() })

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
      coupon_code: coupon.value?.code || null,
    })
  } catch (e) {
    paying.value = false
    if (e.code === 'coupon') {
      // coupon expired or was used meanwhile: stay here, show it by the coupon box
      coupon.value = null
      couponOpen.value = true
      couponError.value = e.message
      return
    }
    payError.value = e.message
    if (e.status === 409 || e.status === 400) {
      choice.slot = { date: choice.slot.date, time: null, label: null }
      step.value = 2
    }
    return
  }

  if (hold.booking) {
    // free booking (100% coupon): already confirmed, no payment needed
    paying.value = false
    result.value = hold.booking
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

// "Service 1" -> "S1": short code for the gold tile, like the site's IP / LC tiles
const serviceCode = (name) =>
  name
    .split(/\s+/)
    .map((w) => (/^\d+$/.test(w) ? w : w[0]))
    .join('')
    .slice(0, 3)
    .toUpperCase()

function startOver() {
  result.value = null
  step.value = 1
  choice.serviceId = null
  choice.slot = { date: null, time: null, label: null }
  Object.assign(form, { name: '', email: '', phone: '', consent: false })
  touched.value = false
  removeCoupon()
  couponOpen.value = false
}
</script>

<template>
  <PageHero
    badge="Online consultation booking"
    title="Book a"
    highlight="Consultation"
    text="Choose a service and a time that suits you. Your slot is confirmed the moment your payment goes through, and the Google Meet link arrives by email."
  />

  <div class="page page--over">
    <!-- Confirmation -->
    <section v-if="result" class="sheet stack" aria-live="polite">
      <template v-if="result.status === 'confirmed'">
        <div class="card-head">
          <span class="tile" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
          </span>
          <div class="card-head__text">
            <span><span class="tag tag--ok">Booking confirmed</span></span>
            <h2>You're booked, {{ result.client_name.split(' ')[0] }}</h2>
            <p class="muted">A confirmation email with these details is on its way to <span class="gold-text">{{ result.client_email }}</span>.</p>
          </div>
          <span class="gold-rule" />
        </div>
        <table class="summary"><tbody>
          <tr><th>Booking ID</th><td>{{ result.reference }}</td></tr>
          <tr><th>Service</th><td>{{ result.service_name }}</td></tr>
          <tr><th>Date</th><td>{{ longDate(result.date) }}</td></tr>
          <tr><th>Time</th><td>{{ result.slot_label }} IST</td></tr>
          <template v-if="result.discount_inr">
            <tr><th>Consultation fee</th><td>{{ inr(result.base_fee_inr) }}</td></tr>
            <tr><th>Coupon {{ result.coupon_code }}</th><td class="discount">− {{ inr(result.discount_inr) }}</td></tr>
          </template>
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
        <div class="card-head">
          <span class="tile" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 8v5M12 16.5v.5" /><circle cx="12" cy="12" r="9" /></svg>
          </span>
          <div class="card-head__text">
            <span><span class="tag tag--danger">Payment refunded</span></span>
            <h2>That slot has just been taken</h2>
          </div>
          <span class="gold-rule" />
        </div>
        <p>{{ result.message }}</p>
      </template>
      <div><button class="btn btn--primary" type="button" @click="startOver">Book another consultation</button></div>
    </section>

    <!-- Booking steps -->
    <template v-else>
      <ol class="steps" aria-label="Booking steps">
        <li v-for="(label, i) in STEPS" :key="label" :class="{ 'is-done': i + 1 < step, 'is-current': i + 1 === step }">
          <button type="button" :disabled="i + 1 >= step" :aria-current="i + 1 === step ? 'step' : undefined" @click="goTo(i + 1)">
            <span class="steps__n">
              <svg v-if="i + 1 < step" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
              <template v-else>{{ i + 1 }}</template>
            </span>
            <span class="steps__label">{{ label }}</span>
          </button>
        </li>
      </ol>

      <section class="sheet">
        <!-- 1. Service -->
        <div v-if="step === 1" class="stack">
          <div class="card-head">
            <span class="tile" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3 12h18" /></svg>
            </span>
            <div class="card-head__text">
              <h2>Choose a service</h2>
              <p class="muted"><span class="gold-text">Step 1 of 4</span> · Select the consultation you need</p>
            </div>
            <span class="gold-rule" />
          </div>
          <p v-if="loadError" class="notice notice--error">{{ loadError }}</p>
          <p v-else-if="!services.length" class="muted">Loading services…</p>
          <div class="services" role="radiogroup" aria-label="Services">
            <label v-for="s in services" :key="s.id" class="service" :class="{ 'is-on': choice.serviceId === s.id }">
              <input v-model="choice.serviceId" type="radio" name="service" :value="s.id" class="sr-only" />
              <span class="tile tile--sm service__tile" aria-hidden="true">{{ serviceCode(s.name) }}</span>
              <span class="service__main">
                <span class="service__name">{{ s.name }}</span>
                <span class="service__desc">{{ s.description }}</span>
              </span>
              <span class="service__meta">
                <span class="service__len">{{ s.duration_minutes }} min</span>
                <span class="service__len">Online</span>
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
          <div class="card-head">
            <span class="tile" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></svg>
            </span>
            <div class="card-head__text">
              <h2>Pick a date and time</h2>
              <p class="muted"><span class="gold-text">Step 2 of 4</span> · Three sessions a day, Monday to Saturday</p>
            </div>
            <span class="gold-rule" />
          </div>
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
          <div class="card-head">
            <span class="tile" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>
            </span>
            <div class="card-head__text">
              <h2>Your details</h2>
              <p class="muted"><span class="gold-text">Step 3 of 4</span> · Used only to confirm and run this consultation</p>
            </div>
            <span class="gold-rule" />
          </div>
          <div class="field" :data-invalid="touched && !!errors.name">
            <label for="name">Full name<span class="req">*</span></label>
            <div class="with-icon">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 12a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Zm0 2c-4.4 0-8 2.2-8 5v1h16v-1c0-2.8-3.6-5-8-5Z" /></svg>
              <input id="name" v-model="form.name" autocomplete="name" placeholder="Full name" required />
            </div>
            <span v-if="touched && errors.name" class="error">{{ errors.name }}</span>
          </div>
          <div class="grid2">
            <div class="field" :data-invalid="touched && !!errors.email">
              <label for="email">Email address<span class="req">*</span></label>
              <div class="with-icon">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Zm9 7.2L4 7.3V8l8 5 8-5v-.7l-8 4.9Z" /></svg>
                <input id="email" v-model="form.email" type="email" autocomplete="email" placeholder="you@example.com" required />
              </div>
              <span v-if="touched && errors.email" class="error">{{ errors.email }}</span>
            </div>
            <div class="field" :data-invalid="touched && !!errors.phone">
              <label for="phone">Phone number<span class="req">*</span></label>
              <div class="with-icon">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.58 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1L6.6 10.8Z" /></svg>
                <input id="phone" v-model="form.phone" type="tel" autocomplete="tel" placeholder="+91" required />
              </div>
              <span v-if="touched && errors.phone" class="error">{{ errors.phone }}</span>
            </div>
          </div>
          <label class="check">
            <input v-model="form.consent" type="checkbox" />
            <span>I agree that {{ COMPANY }} may use these details to manage this booking and contact me about it. Please don't share case details here.</span>
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
          <div class="card-head">
            <span class="tile" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M2 10h20M6 15h4" /></svg>
            </span>
            <div class="card-head__text">
              <h2>Review and pay</h2>
              <p class="muted"><span class="gold-text">Step 4 of 4</span> · Secure payment by Razorpay</p>
            </div>
            <span class="gold-rule" />
          </div>
          <div class="review">
            <table class="summary"><tbody>
              <tr><th>Service</th><td>{{ service?.name }}</td></tr>
              <tr><th>Date</th><td>{{ longDate(choice.slot.date) }}</td></tr>
              <tr><th>Time</th><td>{{ choice.slot.label }} IST</td></tr>
              <tr><th>Session</th><td>{{ service?.duration_minutes }} minutes on Google Meet</td></tr>
              <tr><th>Name</th><td>{{ form.name }}</td></tr>
              <tr><th>Email</th><td>{{ form.email }}</td></tr>
              <tr><th>Phone</th><td>{{ form.phone }}</td></tr>
              <tr><th>Consultation fee</th><td>{{ inr(service?.fee_inr || 0) }}</td></tr>
              <tr v-if="coupon">
                <th>Coupon {{ coupon.code }} ({{ coupon.percent }}% off)</th>
                <td class="discount">− {{ inr(coupon.discount_inr) }}</td>
              </tr>
              <tr class="total"><th>Amount to pay</th><td>{{ inr(amountToPay) }}</td></tr>
            </tbody></table>
          </div>

          <div class="coupon">
            <div v-if="coupon" class="coupon__applied">
              <span class="tag tag--ok">{{ coupon.code }} applied</span>
              <span class="small muted">You save {{ inr(coupon.discount_inr) }}</span>
              <span class="spacer" />
              <button class="btn btn--quiet btn--small" type="button" :disabled="paying" @click="removeCoupon">Remove</button>
            </div>
            <button v-else-if="!couponOpen" class="btn btn--quiet btn--small coupon__toggle" type="button" @click="couponOpen = true">
              + Use coupon
            </button>
            <form v-else class="coupon__form" novalidate @submit.prevent="applyCoupon">
              <div class="field">
                <label for="coupon">Coupon code</label>
                <input id="coupon" v-model="couponInput" placeholder="LEX-XXXXX" autocomplete="off" spellcheck="false" />
              </div>
              <button class="btn btn--small" type="submit" :disabled="couponBusy">{{ couponBusy ? 'Checking…' : 'Apply' }}</button>
            </form>
            <p v-if="couponError" class="small coupon__error" role="alert">{{ couponError }}</p>
          </div>
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
            <button class="btn btn--primary btn--pay" type="button" :disabled="paying" @click="pay">
              {{ paying ? (amountToPay === 0 ? 'Confirming…' : 'Opening payment…') : amountToPay === 0 ? 'Confirm free booking' : `Pay ${inr(amountToPay)}` }}
            </button>
          </div>
          <p v-if="amountToPay > 0" class="small muted pay-note">
            <span class="dot" aria-hidden="true" /> UPI, cards, net banking and wallets accepted
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
/* Steps bar */
.steps {
  list-style: none; margin: 0 0 20px; padding: 10px;
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
  background: var(--paper);
  border-radius: 999px;
  box-shadow: var(--shadow-card);
}
.steps button {
  width: 100%;
  display: flex; align-items: center; justify-content: center; gap: 10px;
  padding: 10px 12px;
  border: 0; border-radius: 999px;
  background: none;
  font: 700 0.8rem var(--font);
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--muted);
  cursor: pointer;
}
.steps button:disabled { cursor: default; }
.steps .is-done button { color: var(--slate); }
.steps .is-done button:hover { background: var(--gold-soft); }
.steps .is-current button { background: var(--gold-gradient); color: var(--ink); box-shadow: var(--shadow-gold); }
.steps__n {
  flex: none;
  width: 26px; height: 26px;
  display: grid; place-items: center;
  border-radius: 50%;
  font-size: 0.8rem;
  background: #f1f5f9; color: var(--slate);
}
.is-done .steps__n { background: var(--gold); color: #fff; }
.is-current .steps__n { background: rgba(255, 255, 255, 0.85); color: var(--ink); }
@media (max-width: 720px) {
  .steps { border-radius: 20px; }
  .steps__label { display: none; }
  .is-current .steps__label { display: inline; }
  .steps { grid-template-columns: auto auto auto auto; justify-content: space-between; }
}

/* Service options: selected one turns gold like the site's Corporate Law card */
.services { display: grid; gap: 14px; }
.service {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 18px; align-items: center;
  padding: 20px 22px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: linear-gradient(135deg, #fffdf6, #fbf7ea);
  cursor: pointer;
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
}
.service:hover { border-color: var(--gold); box-shadow: 0 10px 26px rgba(234, 179, 8, 0.15); }
.service:has(input:focus-visible) { box-shadow: var(--focus); }
.service__tile { background: #fff8db; color: var(--gold-text); box-shadow: none; border: 1px solid var(--gold-line); }
.service__main { display: grid; gap: 4px; }
.service__name { font-family: var(--display); font-size: 1.2rem; color: var(--navy); }
.service__desc { color: var(--muted); font-size: 0.95rem; }
.service__meta {
  display: grid; justify-items: center; gap: 2px;
  padding: 10px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--gold-line);
}
.service__len { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); }

.service.is-on { background: var(--gold-gradient); border-color: #d9a406; box-shadow: var(--shadow-gold); }
.service.is-on .service__name { color: #fff; }
.service.is-on .service__desc { color: rgba(255, 255, 255, 0.92); }
.service.is-on .service__tile { background: rgba(255, 255, 255, 0.25); border-color: rgba(255, 255, 255, 0.5); color: #fff; }
.service.is-on .service__meta { background: rgba(255, 255, 255, 0.22); border-color: rgba(255, 255, 255, 0.45); }
.service.is-on .service__len { color: #fff; }
@media (max-width: 600px) {
  .service { grid-template-columns: auto 1fr; }
  .service__meta { grid-column: 1 / -1; justify-items: start; grid-auto-flow: column; justify-content: space-between; align-items: center; }
}

.review { padding: 8px 24px; border-radius: 20px; background: #fcfdfe; border: 1px solid var(--line); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
@media (max-width: 600px) { .grid2 { grid-template-columns: 1fr; } .review { padding: 4px 16px; } }
.actions { display: flex; gap: 12px; align-items: center; padding-top: 10px; }
.btn--pay { min-width: 200px; font-size: 1rem; }
.discount { color: var(--ok) !important; }
.coupon { display: grid; gap: 8px; }
.coupon__toggle { justify-self: start; padding-left: 0; }
.coupon__form { display: grid; grid-template-columns: minmax(0, 320px) auto; gap: 12px; align-items: end; }
.coupon__form input { text-transform: uppercase; letter-spacing: 0.08em; }
.coupon__applied { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; padding: 12px 16px; border-radius: 14px; background: #f0fdf4; border: 1px solid #bbf7d0; }
.coupon__error { color: var(--danger); }
@media (max-width: 600px) { .coupon__form { grid-template-columns: 1fr; } }
.pay-note { display: flex; align-items: center; gap: 8px; justify-content: flex-end; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--ok); }
</style>