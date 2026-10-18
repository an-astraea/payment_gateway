<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../../api.js'

const emit = defineEmits(['changed'])
const list = ref([])
const form = reactive({ name: '', email: '' })
const error = ref('')
const busy = ref(false)

async function load() {
  try {
    list.value = await api.admin.employees()
    emit('changed', list.value)
  } catch (e) {
    error.value = e.message
  }
}
onMounted(load)

async function add() {
  error.value = ''
  busy.value = true
  try {
    await api.admin.addEmployee({ name: form.name.trim(), email: form.email.trim() })
    form.name = ''
    form.email = ''
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function toggle(emp) {
  try {
    await api.admin.updateEmployee(emp.id, { is_active: !emp.is_active })
    await load()
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <section class="sheet stack">
    <h2>Employees</h2>
    <p class="muted">People who give the sessions. When you assign one to a booking, they get an email and a calendar invite with the Meet link.</p>

    <form class="add" @submit.prevent="add">
      <div class="field"><label for="emp-name">Name</label><input id="emp-name" v-model="form.name" required minlength="2" /></div>
      <div class="field"><label for="emp-email">Email</label><input id="emp-email" v-model="form.email" type="email" required /></div>
      <button class="btn btn--primary" type="submit" :disabled="busy">Add employee</button>
    </form>
    <p v-if="error" class="notice notice--error" role="alert">{{ error }}</p>

    <table v-if="list.length" class="summary"><tbody>
      <tr v-for="e in list" :key="e.id">
        <th>{{ e.name }}</th>
        <td class="emp">
          <span>{{ e.email }}</span>
          <span v-if="!e.is_active" class="tag tag--closed">Inactive</span>
          <button class="btn btn--quiet btn--small" type="button" @click="toggle(e)">{{ e.is_active ? 'Deactivate' : 'Reactivate' }}</button>
        </td>
      </tr>
    </tbody></table>
    <p v-else class="muted">No employees yet. Add the first one above.</p>
  </section>
</template>

<style scoped>
.add { display: grid; grid-template-columns: 1fr 1fr auto; gap: 12px; align-items: end; }
.emp { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; font-weight: 400; }
.emp .btn { margin-left: auto; }
@media (max-width: 640px) { .add { grid-template-columns: 1fr; } }
</style>