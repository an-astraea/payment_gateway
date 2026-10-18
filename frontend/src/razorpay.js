const SCRIPT = 'https://checkout.razorpay.com/v1/checkout.js'
let loading

function loadCheckout() {
  if (window.Razorpay) return Promise.resolve()
  loading ||= new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = SCRIPT
    s.onload = resolve
    s.onerror = () => {
      loading = null
      reject(new Error('The payment window could not load. Check your connection and try again.'))
    }
    document.head.appendChild(s)
  })
  return loading
}

/**
 * Opens Razorpay Checkout. Resolves with
 *   { status: 'paid', response }   when the payment succeeds
 *   { status: 'closed', failed }    when the client closes the window (failed = a payment attempt failed)
 */
export async function openCheckout({ order, hold, company }) {
  await loadCheckout()
  return new Promise((resolve) => {
    let failed = false
    const rzp = new window.Razorpay({
      key: order.key_id,
      amount: order.amount_paise,
      currency: order.currency,
      order_id: order.id,
      name: company,
      description: `${hold.service_name} (${hold.reference})`,
      prefill: { name: hold.client_name, email: hold.client_email, contact: hold.client_phone },
      theme: { color: '#0E5E54' },
      handler: (response) => resolve({ status: 'paid', response }),
      modal: { ondismiss: () => resolve({ status: 'closed', failed }), confirm_close: true },
    })
    // Razorpay lets the client retry inside the same window, so a failure does not close it.
    rzp.on('payment.failed', () => { failed = true })
    rzp.open()
  })
}
