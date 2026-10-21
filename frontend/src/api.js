const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

const FIELD_NAMES = { name: 'Name', email: 'Email', phone: 'Phone number', date: 'Date', time: 'Time' }

function messageFrom(detail, status) {
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && detail.message) return detail.message
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0]
    const field = FIELD_NAMES[first.loc?.[first.loc.length - 1]] || 'A field'
    return `${field}: ${first.msg.replace(/^Value error, /, '')}`
  }
  return status >= 500 ? 'The server could not complete this. Try again in a moment.' : 'The request could not be completed.'
}

async function request(path, { method = 'GET', body, params } = {}) {
  const url = new URL(BASE + path, window.location.origin)
  if (params) Object.entries(params).forEach(([k, v]) => v != null && url.searchParams.set(k, v))
  let res
  try {
    res = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw Object.assign(new Error('Cannot reach the booking server. Check your connection and try again.'), { status: 0 })
  }
  if (res.status === 204) return null
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    // code: 'coupon' means the problem is the coupon, not the slot
    throw Object.assign(new Error(messageFrom(data.detail, res.status)), { status: res.status, code: data.detail?.code })
  }
  return data
}

export const api = {
  services: () => request('/api/services'),
  availability: (start, days) => request('/api/availability', { params: { start, days } }),
  checkCoupon: (code, serviceId, email) =>
    request('/api/coupons/check', { method: 'POST', body: { code, service_id: serviceId, email } }),
  hold: (payload) => request('/api/bookings/hold', { method: 'POST', body: payload }),
  verify: (payload) => request('/api/bookings/verify', { method: 'POST', body: payload }),
  release: (orderId) => request('/api/bookings/release', { method: 'POST', body: { razorpay_order_id: orderId } }),
  manage: (token) => request(`/api/manage/${token}`),
  cancel: (token) => request(`/api/manage/${token}/cancel`, { method: 'POST' }),
  reschedule: (token, date, time) => request(`/api/manage/${token}/reschedule`, { method: 'POST', body: { date, time } }),
  admin: {
    days: (start, days) => request('/api/admin/days', { params: { start, days } }),
    assign: (id, employeeId) => request(`/api/admin/bookings/${id}/assign`, { method: 'POST', body: { employee_id: employeeId } }),
    cancel: (id) => request(`/api/admin/bookings/${id}/cancel`, { method: 'POST' }),
    employees: () => request('/api/admin/employees'),
    addEmployee: (e) => request('/api/admin/employees', { method: 'POST', body: e }),
    updateEmployee: (id, e) => request(`/api/admin/employees/${id}`, { method: 'PATCH', body: e }),
    blocked: () => request('/api/admin/blocked-dates'),
    addBlocked: (b) => request('/api/admin/blocked-dates', { method: 'POST', body: b }),
    removeBlocked: (id) => request(`/api/admin/blocked-dates/${id}`, { method: 'DELETE' }),
    couponConfig: () => request('/api/admin/coupons/config'),
    coupons: (status) => request('/api/admin/coupons', { params: { status } }),
    createCoupon: (percent) => request('/api/admin/coupons', { method: 'POST', body: { percent } }),
    // clientEmail empty = resend to the saved email
    sendCoupon: (id, clientEmail) =>
      request(`/api/admin/coupons/${id}/send`, { method: 'POST', body: { client_email: clientEmail || null } }),
    deactivateCoupon: (id) => request(`/api/admin/coupons/${id}/deactivate`, { method: 'POST' }),
  },
}