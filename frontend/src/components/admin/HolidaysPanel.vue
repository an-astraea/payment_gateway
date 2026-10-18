<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../../api.js'
import { longDate } from '../../format.js'

const list = ref([])
const form = reactive({ date: '', reason: '' })
const error = ref('')

async function load() {
  try {
    list.value = await api.admin.blocked()
  } catch (e) {
    error.value = e.message
  }
}
onMounted(load)

async function add() {
  error.value = ''
  try {
    await api.admin.addBlocked({ date: form.date, reason: form.reason.trim() })
    form.date = ''
    form.reason = ''
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function remove(item) {
  try {
    await api.admin.removeBlocked(item.id)
    await load()
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <section class="sheet stack">
    <h2>Holidays</h2>
    <p class="muted">No slots are offered on these dates. Existing bookings on a date you block are not cancelled automatically.</p>

    <form class="add" @submit.prevent="add">
      <div class="field"><label for="h-date">Date</label><input id="h-date" v-model="form.date" type="date" required /></div>
      <div class="field"><label for="h-reason">Reason (optional)</label><input id="h-reason" v-model="form.reason" placeholder="e.g. Diwali" /></div>
      <button class="btn btn--primary" type="submit">Block date</button>
    </form>
    <p v-if="error" class="notice notice--error" role="alert">{{ error }}</p>

    <table v-if="list.length" class="summary"><tbody>
      <tr v-for="h in list" :key="h.id">
        <th>{{ longDate(h.date) }}</th>
        <td class="h">
          <span>{{ h.reason || 'Closed' }}</span>
          <button class="btn btn--quiet btn--small" type="button" @click="remove(h)">Remove</button>
        </td>
      </tr>
    </tbody></table>
    <p v-else class="muted">No upcoming holidays.</p>
  </section>
</template>

<style scoped>
.add { display: grid; grid-template-columns: 200px 1fr auto; gap: 12px; align-items: end; }
.h { display: flex; gap: 10px; align-items: center; font-weight: 400; }
.h .btn { margin-left: auto; }
@media (max-width: 640px) { .add { grid-template-columns: 1fr; } }
</style>