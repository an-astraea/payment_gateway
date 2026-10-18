<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'
import { addDays, inr, longDate, todayIso } from '../format.js'
import EmployeesPanel from '../components/admin/EmployeesPanel.vue'
import HolidaysPanel from '../components/admin/HolidaysPanel.vue'

const tab = ref('bookings')
const start = ref(todayIso())
const days = ref([])
const employees = ref([])
const loading = ref(false)
const error = ref('')
const flash = ref('')
const busyId = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [d, e] = await Promise.all([api.admin.days(start.value, 7), api.admin.employees()])
    days.value = d
    employees.value = e
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)

function shift(n) {
  start.value = n === 0 ? todayIso() : addDays(start.value, n)
  load()
}

const activeEmployees = computed(() => employees.value.filter((e) => e.is_active))
const weekStats = computed(() => {
  const confirmed = days.value.flatMap((d) => d.slots.map((s) => s.booking)).filter((b) => b?.status === 'confirmed')
  return { booked: confirmed.length, unassigned: confirmed.filter((b) => !b.employee_id).length }
})
const rangeLabel = computed(() => (days.value.length ? `${longDate(days.value[0].date)} to ${longDate(days.value[days.value.length - 1].date)}` : ''))

async function assign(booking, employeeId) {
  if (!employeeId) return
  busyId.value = booking.id
  flash.value = ''
  try {
    const updated = await api.admin.assign(booking.id, Number(employeeId))
    Object.assign(booking, updated)
    const emp = employees.value.find((e) => e.id === updated.employee_id)
    flash.value = `${updated.reference} assigned to ${emp?.name}. They have been emailed and added to the calendar invite.`
  } catch (e) {
    error.value = e.message
  } finally {
    busyId.value = null
  }
}

async function cancelBooking(booking) {
  if (!window.confirm(`Cancel ${booking.reference} for ${booking.client_name} and refund ${inr(booking.fee_inr)}? The client will be emailed.`)) return
  busyId.value = booking.id
  try {
    await api.admin.cancel(booking.id)
    flash.value = `${booking.reference} cancelled and refunded.`
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busyId.value = null
  }
}

function onEmployeesChanged(list) {
  employees.value = list
}
</script>

<template>
  <div class="page page--wide">
    <div class="head">
      <h1>Consultations</h1>
      <p class="small muted">The dashboard has no sign-in yet. Restrict access before going live.</p>
    </div>

    <nav class="tabs" aria-label="Dashboard sections">
      <button type="button" :aria-current="tab === 'bookings' ? 'page' : undefined" @click="tab = 'bookings'">Bookings</button>
      <button type="button" :aria-current="tab === 'employees' ? 'page' : undefined" @click="tab = 'employees'">Employees</button>
      <button type="button" :aria-current="tab === 'holidays' ? 'page' : undefined" @click="tab = 'holidays'">Holidays</button>
    </nav>

    <section v-if="tab === 'bookings'" class="stack">
      <div class="toolbar">
        <div class="row">
          <button class="btn btn--small" type="button" @click="shift(-7)">Previous week</button>
          <button class="btn btn--small" type="button" @click="shift(0)">Today</button>
          <button class="btn btn--small" type="button" @click="shift(7)">Next week</button>
        </div>
        <p class="small muted">{{ rangeLabel }}</p>
        <p class="stats">
          <strong>{{ weekStats.booked }}</strong> booked this view
          <span v-if="weekStats.unassigned" class="tag tag--held">{{ weekStats.unassigned }} not assigned</span>
        </p>
      </div>

      <p v-if="flash" class="notice" role="status">{{ flash }}</p>
      <p v-if="error" class="notice notice--error" role="alert">{{ error }}</p>
      <p v-if="loading && !days.length" class="muted">Loading bookings…</p>

      <article v-for="day in days" :key="day.date" class="day" :class="{ 'day--off': !day.working_day || day.holiday }">
        <header class="day__head">
          <h2>{{ longDate(day.date) }}</h2>
          <span v-if="day.holiday" class="tag tag--closed">Holiday: {{ day.holiday }}</span>
          <span v-else-if="!day.working_day" class="tag tag--closed">Closed</span>
          <span v-else class="small muted">{{ day.booked_count }} of {{ day.slots.length }} booked</span>
        </header>

        <ul v-if="day.working_day && !day.holiday" class="slots">
          <li v-for="slot in day.slots" :key="slot.time" class="slot" :class="{ 'slot--open': !slot.booking }">
            <div class="slot__time">{{ slot.label }}</div>

            <div v-if="!slot.booking" class="slot__body muted">Open</div>

            <template v-else-if="slot.booking.status === 'pending_payment'">
              <div class="slot__body">
                <span class="tag tag--held">Held while paying</span>
                <span class="small muted">{{ slot.booking.client_name }}, {{ slot.booking.service_name }}</span>
              </div>
            </template>

            <template v-else>
              <div class="slot__body">
                <div class="client">
                  <strong>{{ slot.booking.client_name }}</strong>
                  <span class="small muted">{{ slot.booking.service_name }}, {{ slot.booking.reference }}</span>
                </div>
                <div class="small contact">
                  <a :href="`mailto:${slot.booking.client_email}`">{{ slot.booking.client_email }}</a>
                  <a :href="`tel:${slot.booking.client_phone}`">{{ slot.booking.client_phone }}</a>
                  <a v-if="slot.booking.meet_link" :href="slot.booking.meet_link" target="_blank" rel="noopener">Google Meet</a>
                  <span v-else class="muted">No Meet link</span>
                </div>
              </div>
              <div class="slot__actions">
                <label class="sr-only" :for="`assign-${slot.booking.id}`">Assign employee</label>
                <select
                  :id="`assign-${slot.booking.id}`"
                  class="assign"
                  :class="{ 'assign--empty': !slot.booking.employee_id }"
                  :value="slot.booking.employee_id || ''"
                  :disabled="busyId === slot.booking.id || !activeEmployees.length"
                  @change="assign(slot.booking, $event.target.value)"
                >
                  <option value="" disabled>{{ activeEmployees.length ? 'Assign employee' : 'Add employees first' }}</option>
                  <option v-for="e in activeEmployees" :key="e.id" :value="e.id">{{ e.name }}</option>
                </select>
                <button class="btn btn--quiet btn--small" type="button" :disabled="busyId === slot.booking.id" @click="cancelBooking(slot.booking)">
                  Cancel
                </button>
              </div>
            </template>
          </li>
        </ul>
      </article>
    </section>

    <EmployeesPanel v-else-if="tab === 'employees'" @changed="onEmployeesChanged" />
    <HolidaysPanel v-else />
  </div>
</template>

<style scoped>
.head { display: grid; gap: 4px; margin-bottom: 20px; }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--line); margin-bottom: 20px; }
.tabs button {
  border: 0;
  background: none;
  font: 500 var(--step-0) var(--font);
  color: var(--muted);
  padding: 10px 14px;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
}
.tabs button[aria-current='page'] { color: var(--seal); border-bottom-color: var(--seal); }

.toolbar { display: flex; flex-wrap: wrap; gap: 12px 24px; align-items: center; }
.stats { margin-left: auto; display: flex; gap: 10px; align-items: center; }

.day { background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius-m); }
.day--off { background: transparent; border-style: dashed; }
.day__head { display: flex; gap: 12px; align-items: baseline; justify-content: space-between; padding: 14px 18px; flex-wrap: wrap; }
.day__head h2 { font-size: var(--step-1); }
.slots { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--line); }
.slot {
  display: grid;
  grid-template-columns: 170px 1fr auto;
  gap: 16px;
  align-items: center;
  padding: 12px 18px;
  border-bottom: 1px solid var(--line);
}
.slot:last-child { border-bottom: 0; }
.slot__time { font-weight: 500; }
.slot--open .slot__time { color: var(--muted); font-weight: 400; }
.slot__body { display: grid; gap: 4px; }
.client { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.contact { display: flex; gap: 14px; flex-wrap: wrap; }
.slot__actions { display: flex; gap: 6px; align-items: center; }
.assign {
  font: inherit;
  font-size: var(--step--1);
  padding: 7px 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius-s);
  background: var(--paper);
  min-width: 170px;
  min-height: 36px;
}
.assign--empty { border-color: var(--held); background: var(--held-soft); }
@media (max-width: 760px) {
  .slot { grid-template-columns: 1fr; gap: 8px; }
  .stats { margin-left: 0; }
}
</style>
