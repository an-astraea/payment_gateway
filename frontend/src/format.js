const inrFormat = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })

export const inr = (n) => inrFormat.format(n)

/** Parse 'YYYY-MM-DD' as a local calendar date (no timezone shift). */
export function toDate(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function toIso(date) {
  const p = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}`
}

export const longDate = (iso) =>
  toDate(iso).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

export const weekday = (iso) => toDate(iso).toLocaleDateString('en-IN', { weekday: 'short' })
export const dayNumber = (iso) => toDate(iso).getDate()
export const monthShort = (iso) => toDate(iso).toLocaleDateString('en-IN', { month: 'short' })

export function addDays(iso, n) {
  const d = toDate(iso)
  d.setDate(d.getDate() + n)
  return toIso(d)
}

export const todayIso = () => toIso(new Date())

export const COMPANY = import.meta.env.VITE_COMPANY_NAME || 'Lextria Research'
