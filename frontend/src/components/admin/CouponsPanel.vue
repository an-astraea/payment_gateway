<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../../api.js'
import { inr } from '../../format.js'

const PERCENTS = [25, 50, 75, 100]
const config = ref({ percents: PERCENTS, valid_hours: 24, lock_to_email: true })
const fee = ref(10000) // consultation fee used for the preview

const percent = ref(25)
const busy = ref(false)
const error = ref('')
const created = ref(null) // last generated coupon
const sendEmail = ref('')
const sending = ref(false)
const sendError = ref('')
const sentTo = ref('')

const coupons = ref([])
const filter = ref('all')
const listError = ref('')
const copied = ref('')
const now = ref(Date.now())
let timer

onMounted(async () => {
  timer = setInterval(() => (now.value = Date.now()), 30000)
  try {
    const [cfg, services] = await Promise.all([api.admin.couponConfig(), api.services()])
    config.value = cfg
    if (services.length) fee.value = services[0].fee_inr
  } catch {
    /* defaults are fine */
  }
  load()
})
onBeforeUnmount(() => clearInterval(timer))

async function load() {
  listError.value = ''
  try {
    coupons.value = await api.admin.coupons()
  } catch (e) {
    listError.value = e.message
  }
}

// discount preview (same rounding as the server: whole rupees)
const discount = computed(() => Math.floor((fee.value * percent.value) / 100))
const payable = computed(() => fee.value - discount.value)
const fillPct = computed(() => ((percent.value - 25) / 75) * 100)

const isEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((v || '').trim())

// Step 1: generate the code
async function generate() {
  error.value = ''
  sendError.value = ''
  sentTo.value = ''
  sendEmail.value = ''
  busy.value = true
  try {
    created.value = await api.admin.createCoupon(percent.value)
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

// Step 2 (optional): email it to the client
async function sendCreated() {
  sendError.value = ''
  if (!isEmail(sendEmail.value)) {
    sendError.value = "Enter the client's email address."
    return
  }
  sending.value = true
  try {
    const r = await api.admin.sendCoupon(created.value.id, sendEmail.value.trim())
    created.value = r
    if (r.emailed) sentTo.value = r.client_email
    else sendError.value = 'The email could not be sent. Check the email settings, or copy the code and send it yourself.'
    await load()
  } catch (e) {
    sendError.value = e.message
  } finally {
    sending.value = false
  }
}

async function copy(code) {
  try {
    await navigator.clipboard.writeText(code)
  } catch {
    const t = document.createElement('textarea')
    t.value = code
    document.body.appendChild(t)
    t.select()
    document.execCommand('copy')
    t.remove()
  }
  copied.value = code
  setTimeout(() => { if (copied.value === code) copied.value = '' }, 1800)
}

// Send from the list: asks for the email if the coupon has not been sent yet
async function sendFromList(c) {
  let to = c.client_email
  if (!to) {
    to = window.prompt(`Send ${c.code} to which email address?`, '')
    if (to === null) return
    if (!isEmail(to)) {
      listError.value = 'That email address does not look right.'
      return
    }
  }
  try {
    const r = await api.admin.sendCoupon(c.id, to)
    window.alert(r.emailed ? `Coupon ${c.code} emailed to ${r.client_email}.` : 'The email could not be sent. Check the email settings, or copy the code and send it yourself.')
    await load()
  } catch (e) {
    listError.value = e.message
  }
}

async function deactivate(c) {
  if (!window.confirm(`Deactivate ${c.code}? The client will no longer be able to use it.`)) return
  try {
    await api.admin.deactivateCoupon(c.id)
    await load()
  } catch (e) {
    listError.value = e.message
  }
}

const FILTERS = [
  ['all', 'All'],
  ['unused', 'Unused'],
  ['used', 'Used'],
  ['expired', 'Expired'],
  ['deactivated', 'Deactivated'],
]
const counts = computed(() => {
  const c = { all: coupons.value.length, unused: 0, used: 0, expired: 0, deactivated: 0 }
  for (const x of coupons.value) c[liveStatus(x)]++
  return c
})
const shown = computed(() => (filter.value === 'all' ? coupons.value : coupons.value.filter((c) => liveStatus(c) === filter.value)))

// an unused coupon turns "expired" on screen as soon as its time passes
function liveStatus(c) {
  if (c.status === 'unused' && new Date(c.expires_at).getTime() <= now.value) return 'expired'
  return c.status
}
const STATUS = {
  unused: ['Unused', 'tag--ok'],
  used: ['Used', ''],
  expired: ['Expired', 'tag--closed'],
  deactivated: ['Deactivated', 'tag--danger'],
}

function timeLeft(iso) {
  const ms = new Date(iso).getTime() - now.value
  if (ms <= 0) return 'expired'
  const h = Math.floor(ms / 3600000)
  const m = Math.floor((ms % 3600000) / 60000)
  return h ? `${h} h ${m} min left` : `${m} min left`
}
const when = (iso) =>
  new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Kolkata' })
</script>

<template>
  <div class="coupons stack">
    <!-- Generator -->
    <section class="sheet stack">
      <div class="card-head">
        <span class="tile" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9V6a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v3a3 3 0 0 0 0 6v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-3a3 3 0 0 0 0-6Z" /><path d="M9 9h.01M15 15h.01M15.5 8.5l-7 7" /></svg>
        </span>
        <div class="card-head__text">
          <h2>Generate a coupon</h2>
          <p class="muted">
            <span class="gold-text">Single use</span> · expires {{ config.valid_hours }} hours after it is generated · generate it, then copy or email it
          </p>
        </div>
        <span class="gold-rule" />
      </div>

      <div class="gen">
        <div class="gen__controls stack">
          <div class="field">
            <span class="label" id="disc-label">Discount</span>
            <div class="bar">
              <input
                v-model.number="percent"
                type="range"
                min="25"
                max="100"
                step="25"
                aria-labelledby="disc-label"
                :aria-valuetext="percent === 100 ? 'Free consultation' : `${percent}% off`"
                :style="{ '--fill': fillPct + '%' }"
              />
              <div class="bar__ticks">
                <button v-for="p in PERCENTS" :key="p" type="button" :class="{ 'is-on': percent === p }" @click="percent = p">{{ p }}%</button>
              </div>
            </div>
            <span v-if="percent === 100" class="small muted">100% = free consultation. The client confirms without paying.</span>
          </div>
          <p v-if="error" class="notice notice--error" role="alert">{{ error }}</p>
          <div>
            <button class="btn btn--primary" type="button" :disabled="busy" @click="generate">
              {{ busy ? 'Generating…' : percent === 100 ? 'Generate free coupon' : `Generate ${percent}% coupon` }}
            </button>
          </div>
        </div>

        <!-- Preview -->
        <div class="preview" aria-live="polite">
          <span class="preview__off">{{ percent === 100 ? 'FREE' : `${percent}% OFF` }}</span>
          <span class="preview__code">LEX-XXXXX</span>
          <span class="preview__line"><s>{{ inr(fee) }}</s> <strong>{{ inr(payable) }}</strong></span>
          <span class="small">The client saves {{ inr(discount) }}</span>
        </div>
      </div>

      <!-- After generating: copy it, or email it to the client -->
      <div v-if="created" class="result" role="status">
        <div class="result__top">
          <div class="result__code">
            <span class="label">New coupon · {{ created.percent === 100 ? 'free consultation' : `${created.percent}% off` }}</span>
            <strong>{{ created.code }}</strong>
            <span class="small muted">Valid until {{ when(created.expires_at) }} IST · single use</span>
          </div>
          <button class="btn btn--small" type="button" @click="copy(created.code)">{{ copied === created.code ? 'Copied' : 'Copy code' }}</button>
        </div>

        <p v-if="sentTo" class="notice" role="status">Emailed to <span class="gold-text">{{ sentTo }}</span>. It now works only with that email address.</p>
        <form v-else class="send" novalidate @submit.prevent="sendCreated">
          <div class="field">
            <label for="c-email">Email it to the client (optional)</label>
            <div class="with-icon">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Zm9 7.2L4 7.3V8l8 5 8-5v-.7l-8 4.9Z" /></svg>
              <input id="c-email" v-model="sendEmail" type="email" placeholder="client@example.com" autocomplete="off" />
            </div>
          </div>
          <button class="btn btn--primary" type="submit" :disabled="sending">{{ sending ? 'Sending…' : 'Send to client' }}</button>
        </form>
        <p v-if="sendError" class="small warn" role="alert">{{ sendError }}</p>
        <p v-if="!sentTo && config.lock_to_email" class="small muted">Once emailed, the coupon works only with that email address.</p>
      </div>
    </section>

    <!-- List -->
    <section class="sheet stack">
      <div class="row">
        <h2>Coupons</h2>
        <span class="spacer" />
        <button class="btn btn--small" type="button" @click="load">Refresh</button>
      </div>

      <div class="filters" role="tablist" aria-label="Filter coupons">
        <button
          v-for="[key, label] in FILTERS"
          :key="key"
          type="button"
          role="tab"
          :aria-selected="filter === key"
          @click="filter = key"
        >
          {{ label }} <span class="count">{{ counts[key] }}</span>
        </button>
      </div>

      <p v-if="listError" class="notice notice--error">{{ listError }}</p>
      <p v-else-if="!shown.length" class="muted">No coupons here yet.</p>

      <div v-else class="table-wrap">
        <table class="list">
          <thead>
            <tr><th>Code</th><th>Discount</th><th>Client</th><th>Validity</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr>
          </thead>
          <tbody>
            <tr v-for="c in shown" :key="c.id">
              <td><strong class="code">{{ c.code }}</strong></td>
              <td>{{ c.percent === 100 ? 'Free' : `${c.percent}%` }}</td>
              <td>
                <template v-if="c.client_email">{{ c.client_email }}</template>
                <span v-else class="muted">Not sent</span>
                <span v-if="c.client_email && !c.emailed && liveStatus(c) === 'unused'" class="small warn">Email failed</span>
              </td>
              <td class="small">
                <template v-if="liveStatus(c) === 'unused'">{{ timeLeft(c.expires_at) }}</template>
                <template v-else-if="c.status === 'used'">
                  Used {{ when(c.used_at) }}<br />
                  <span class="muted">{{ c.booking_reference }} · {{ c.booking_client_name }} · paid {{ inr(c.amount_paid_inr) }}</span>
                </template>
                <template v-else>Created {{ when(c.created_at) }}</template>
              </td>
              <td><span class="tag" :class="STATUS[liveStatus(c)][1]">{{ STATUS[liveStatus(c)][0] }}</span></td>
              <td class="actions">
                <template v-if="liveStatus(c) === 'unused'">
                  <button class="btn btn--quiet btn--small" type="button" @click="copy(c.code)">{{ copied === c.code ? 'Copied' : 'Copy' }}</button>
                  <button class="btn btn--quiet btn--small" type="button" @click="sendFromList(c)">{{ c.client_email ? 'Resend' : 'Send' }}</button>
                  <button class="btn btn--quiet btn--small danger" type="button" @click="deactivate(c)">Deactivate</button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.gen { display: grid; grid-template-columns: 1fr 280px; gap: 32px; align-items: start; }
@media (max-width: 820px) { .gen { grid-template-columns: 1fr; } }

/* Discount bar: snaps to 25 / 50 / 75 */
.bar { display: grid; gap: 10px; padding-top: 6px; }
.bar input[type='range'] {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 12px;
  min-height: 0;
  padding: 0;
  border: 0;
  box-shadow: none;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--gold) 0%, var(--amber) var(--fill), #e2e8f0 var(--fill), #e2e8f0 100%);
  outline: none;
  cursor: pointer;
}
.bar input[type='range']::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 30px; height: 30px; border-radius: 50%;
  background: #fff; border: 4px solid var(--gold);
  box-shadow: var(--shadow-gold);
}
.bar input[type='range']::-moz-range-thumb {
  width: 24px; height: 24px; border-radius: 50%;
  background: #fff; border: 4px solid var(--gold);
  box-shadow: var(--shadow-gold);
}
.bar input[type='range']:focus-visible { box-shadow: var(--focus); }
.bar__ticks { display: flex; justify-content: space-between; margin: 0 -4px; }
.bar__ticks button {
  border: 0; background: none; cursor: pointer;
  font: 700 0.95rem var(--font); color: var(--muted);
  padding: 4px 6px; border-radius: 8px;
}
.bar__ticks button.is-on { color: var(--gold-text); }

/* Coupon preview, styled like a ticket */
.preview {
  display: grid; justify-items: center; gap: 6px; text-align: center;
  padding: 26px 20px;
  border-radius: 20px;
  background: var(--hero);
  color: #fff;
  border: 2px dashed rgba(234, 179, 8, 0.6);
}
.preview__off { font-family: var(--display); font-size: 2.2rem; line-height: 1; background: var(--gold-gradient); -webkit-background-clip: text; background-clip: text; color: transparent; }
.preview__code { font-weight: 700; letter-spacing: 0.2em; color: rgba(255, 255, 255, 0.8); }
.preview__line { font-size: 1.1rem; }
.preview__line s { color: rgba(255, 255, 255, 0.55); margin-right: 6px; }
.preview .small { color: rgba(255, 255, 255, 0.75); }

.result {
  display: grid; gap: 14px;
  padding: 20px 22px; border-radius: 18px;
  background: var(--gold-soft); border: 1px solid var(--gold-line);
}
.result__top { display: flex; gap: 16px; align-items: center; justify-content: space-between; flex-wrap: wrap; }
.result__code { display: grid; gap: 2px; }
.send { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; align-items: end; }
@media (max-width: 640px) { .send { grid-template-columns: 1fr; } }
.result__code strong { font-family: var(--display); font-weight: 400; font-size: 1.6rem; letter-spacing: 0.06em; color: var(--navy); }
.warn { color: var(--held); font-weight: 600; }

.filters { display: flex; gap: 6px; flex-wrap: wrap; }
.filters button {
  border: 1px solid var(--line); background: var(--paper); cursor: pointer;
  font: 700 0.8rem var(--font); letter-spacing: 0.08em; text-transform: uppercase; color: var(--slate);
  padding: 9px 16px; border-radius: 999px;
}
.filters button[aria-selected='true'] { background: var(--gold-gradient); border-color: transparent; color: var(--ink); }
.count { display: inline-block; min-width: 22px; margin-left: 6px; padding: 1px 7px; border-radius: 999px; background: rgba(15, 23, 42, 0.08); }

.table-wrap { overflow-x: auto; }
.list { width: 100%; border-collapse: collapse; min-width: 760px; }
.list th { text-align: left; font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); padding: 10px 12px; border-bottom: 1px solid var(--line); }
.list td { padding: 14px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }
.list tr:last-child td { border-bottom: 0; }
.code { letter-spacing: 0.06em; color: var(--navy); }
.list .warn { display: block; }
.actions { white-space: nowrap; text-align: right; }
.danger { color: var(--danger); }
</style>