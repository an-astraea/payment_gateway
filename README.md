# Lextria Research: Consultation Booking Module

A self-contained online consultation booking module for **Lextria Research**, built with
**Vue 3** and **FastAPI**. Clients book and pay for a consultation in four steps, and every
confirmed booking gets a Google Meet link and an email confirmation. The firm manages
bookings, staff, holidays and discount coupons from an admin dashboard.

The module is styled to match [lextria.in](https://lextria.in) and is designed to be added to
the company website later.

---

## Contents

- [Features](#features)
- [How a booking works](#how-a-booking-works)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Quick start (test mode)](#quick-start-test-mode)
- [Configuration](#configuration)
- [Connecting the real services](#connecting-the-real-services)
- [Coupons](#coupons)
- [Business rules](#business-rules)
- [Running the tests](#running-the-tests)
- [API reference](#api-reference)
- [Adding it to the company website](#adding-it-to-the-company-website)
- [Before going live](#before-going-live)
- [Troubleshooting](#troubleshooting)

---

## Features

**For clients**
- Four-step booking: service, date and time, details, review and pay
- Three fixed one-hour slots a day (10:00 AM, 2:00 PM, 5:00 PM IST), Monday to Saturday
- Bookings open from tomorrow up to 30 days ahead; booked slots disappear for everyone else
- The price appears only on the final review and pay step
- Optional **Use coupon** field on the final step (25%, 50%, 75% or 100% off)
- Secure payment through **Razorpay** (UPI, cards, net banking, wallets)
- Automatic **Google Meet** link and **email confirmation**
- Self-service reschedule (once) and cancel (full refund) up to 24 hours before, through a link in the email

**For the firm (admin dashboard)**
- **Bookings:** day-by-day view, a week at a time
- **Assign an employee** to each booking; they are emailed and added to the calendar invite
- **Cancel** any booking with a full refund
- **Employees:** add, deactivate and reactivate the people who give sessions
- **Holidays:** block dates so no slots are offered
- **Coupons:** generate single-use `LEX-XXXXX` coupons with a 25 / 50 / 75 / 100% bar, copy or email them, deactivate them and track usage

---

## How a booking works

```
Client                         System                               Firm
──────                         ──────                               ────
1. Choose a service
2. Pick a date and slot  ───▶  shows only free slots
3. Enter details
4. Review, add coupon    ───▶  checks coupon, sets the price
   Pay (Razorpay)        ───▶  holds the slot while paying
                               verifies the payment
                               creates the Google Calendar event ─▶ appears on info@lextria.in
                               with a Meet link
   Confirmation email   ◀───   sends booking ID, Meet link,
                               receipt and manage-booking link
                                                                    Admin assigns an employee
                               adds the employee to the event  ───▶ employee gets email + invite
```

A booking exists **only after the payment is verified**. A 100% coupon makes the booking free,
so it is confirmed straight away with no payment step.

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | Vue 3, Vue Router, Vite |
| Backend | FastAPI, SQLAlchemy 2, Pydantic 2 |
| Database | SQLite by default; any SQLAlchemy database (PostgreSQL, MySQL) via one setting |
| Payments | Razorpay (REST API, no SDK) |
| Calendar and video | Google Calendar API with Google Meet |
| Email | Zoho Mail (SMTP) |

---

## Project structure

```
consultation-booking/
├── backend/                         FastAPI
│   ├── app/
│   │   ├── main.py                  app entry, CORS, hold sweeper (runs every minute)
│   │   ├── config.py                all settings, read from .env
│   │   ├── database.py              DATABASE ENTRY POINT + automatic column upgrades
│   │   ├── models.py                services, employees, bookings, slot_locks, blocked_dates, coupons
│   │   ├── schemas.py               request and response models
│   │   ├── slots.py                 slot rules (times, days, booking window)  [pure Python]
│   │   ├── policy.py                cancel / reschedule / refund policy        [pure Python]
│   │   ├── coupon_rules.py          coupon codes, discounts, status            [pure Python]
│   │   ├── booking_service.py       core booking logic
│   │   ├── coupons.py               coupon logic: generate, send, validate, reserve, use
│   │   ├── emails.py                email content
│   │   ├── seed.py                  starting services (Service 1, 2, 3)
│   │   ├── routers/
│   │   │   ├── public.py            client API
│   │   │   ├── admin.py             admin dashboard API
│   │   │   └── webhooks.py          Razorpay webhook
│   │   └── integrations/
│   │       ├── razorpay_client.py
│   │       ├── google_calendar.py
│   │       └── mailer.py            Zoho SMTP
│   ├── scripts/
│   │   ├── google_auth.py           one-time Google sign-in for info@lextria.in
│   │   └── send_test_email.py       sends one test email through Zoho
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
└── frontend/                        Vue 3 + Vite
    ├── index.html
    ├── public/logo.png              put the Lextria seal logo here
    └── src/
        ├── App.vue                  header matching lextria.in
        ├── styles.css               Lextria theme (colours, fonts, buttons, fields)
        ├── api.js                   API client
        ├── razorpay.js              Razorpay Checkout loader
        ├── format.js                dates and rupee formatting
        ├── router.js
        ├── components/
        │   ├── PageHero.vue         dark banner with floating bubbles
        │   ├── SlotPicker.vue       date strip + daily slots
        │   └── admin/
        │       ├── EmployeesPanel.vue
        │       ├── HolidaysPanel.vue
        │       └── CouponsPanel.vue
        └── views/
            ├── BookView.vue         4-step booking, coupon, payment, confirmation
            ├── ManageView.vue       client reschedule / cancel
            └── AdminView.vue        dashboard: Bookings, Employees, Holidays, Coupons
```

---

## Quick start (test mode)

With no Razorpay, Google or SMTP keys the module runs in **test mode**:
- payments are simulated with **Simulate successful payment** and **Simulate failed payment** buttons
- the calendar step is skipped, so there is no Meet link
- emails are printed in the backend terminal instead of being sent

**Requirements:** Python 3.11+ and Node.js 18+.

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

The startup log shows which services are connected, for example:

```
Payments: MOCK | Google Calendar: off | Email: console
```

API docs: http://localhost:8000/docs

### 2. Frontend (second terminal)

```bash
cd frontend
npm install
npm run dev
```

| Page | URL |
| --- | --- |
| Booking page | http://localhost:5173/book |
| Admin dashboard | http://localhost:5173/admin |
| Manage a booking | link in the confirmation email (`/manage/<token>`) |

The admin dashboard is not in the public menu. Open it by its address.

---

## Configuration

All settings live in `backend/.env` (copy from `.env.example`). Restart the backend after changing it.

| Setting | Default | Meaning |
| --- | --- | --- |
| `COMPANY_NAME` | Lextria Research | Shown in emails and pages |
| `FRONTEND_BASE_URL` | http://localhost:5173 | Used for links in emails |
| `CORS_ORIGINS` | http://localhost:5173 | Frontend address(es) allowed to call the API |
| `DATABASE_URL` | sqlite:///./consultation.db | Any SQLAlchemy URL |
| `TIMEZONE` | Asia/Kolkata | Company timezone |
| `SLOT_TIMES` | 10:00,14:00,17:00 | Daily slot start times |
| `SLOT_DURATION_MINUTES` | 60 | Session length |
| `WORKING_DAYS` | 0,1,2,3,4,5 | 0 = Monday ... 6 = Sunday |
| `MIN_DAYS_AHEAD` | 1 | 1 = no same-day booking |
| `BOOKING_HORIZON_DAYS` | 30 | How far ahead clients can book |
| `HOLD_MINUTES` | 15 | Safety net: an unfinished payment releases the slot after this |
| `CHANGE_CUTOFF_HOURS` | 24 | Online cancel / reschedule closes this many hours before |
| `MAX_RESCHEDULES` | 1 | Reschedules allowed per booking |
| `DEFAULT_FEE_INR` | 10000 | Fee for the seeded services |
| `COUPON_VALID_HOURS` | 24 | An unused coupon expires this many hours after it is generated |
| `COUPON_LOCK_TO_EMAIL` | true | Once emailed, a coupon works only with that email address |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | empty | Empty = test mode payments |
| `RAZORPAY_WEBHOOK_SECRET` | empty | Secret for the Razorpay webhook |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN` | empty | Empty = no calendar or Meet link |
| `GOOGLE_CALENDAR_ID` | primary | Calendar to add events to |
| `GOOGLE_SEND_UPDATES` | all | Google also emails calendar invites |
| `SMTP_HOST` | smtppro.zoho.in | Zoho server (see below) |
| `SMTP_PORT` | 465 | SSL port |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | empty | Empty = emails printed to the console |
| `MAIL_FROM` / `MAIL_FROM_NAME` | info@lextria.in / Lextria Research | Sender |

Service names, descriptions and fees are stored in the `services` table and seeded from
`app/seed.py` on the first run.

> **Never commit `backend/.env`.** It holds passwords and keys. It is already listed in `.gitignore`.

---

## Connecting the real services

### Zoho Mail (emails)

1. Sign in at https://accounts.zoho.in as **info@lextria.in**.
2. Go to **Security > App Passwords > Generate New Password** and copy it.
3. In Zoho Mail, check **Settings > Mail Accounts** and make sure IMAP access is on.
4. In `backend/.env`:
   ```
   SMTP_HOST=smtppro.zoho.in        # paid plan with domain email; free plan: smtp.zoho.in
   SMTP_PORT=465
   SMTP_USERNAME=info@lextria.in
   SMTP_PASSWORD=<app password>
   MAIL_FROM=info@lextria.in
   ```
   Accounts on zoho.com use `smtppro.zoho.com` or `smtp.zoho.com`.
5. Test it:
   ```bash
   cd backend
   python scripts/send_test_email.py you@example.com
   ```
6. Restart the backend. The startup log should say `Email: Zoho SMTP`.

### Google Calendar and Meet (info@lextria.in)

1. In Google Cloud Console, create a project and enable **Google Calendar API**.
2. Configure the **OAuth consent screen**:
   - Google Workspace account: choose **Internal**.
   - Regular Google account: choose **External**, add info@lextria.in as a test user, then
     **publish the app to Production**. Apps left in Testing get sign-in tokens that expire after 7 days.
3. Create **Credentials > OAuth client ID > Desktop app**. Download the JSON as `backend/client_secret.json`.
4. Run:
   ```bash
   cd backend
   python scripts/google_auth.py
   ```
   Sign in as **info@lextria.in** and allow access.
5. Copy the three printed values into `backend/.env` and restart. The log should say `Google Calendar: on`.

Every confirmed booking then appears on the company calendar with a Meet link. Assigned
employees are added to the same event.

### Razorpay (payments)

1. In the Razorpay Dashboard switch to **Test mode**, then **Account & Settings > API Keys > Generate Key**.
2. Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.
3. **Webhook** (recommended; confirms the booking even if the client closes the browser right after paying):
   - Dashboard > Webhooks > Add
   - URL: `https://<your-api-domain>/api/webhooks/razorpay`
   - Events: `payment.captured`, `order.paid`
   - Copy the secret to `RAZORPAY_WEBHOOK_SECRET`
   - Webhooks need a public URL; for local testing use a tunnel such as ngrok.
4. Keep payments on auto-capture (the default for orders).
5. Switch to live keys only after KYC is approved and everything works in test mode.

### Database

Only `DATABASE_URL` changes:

```
DATABASE_URL=postgresql+psycopg://user:password@host:5432/consultations   # pip install "psycopg[binary]"
DATABASE_URL=mysql+pymysql://user:password@host:3306/consultations        # pip install pymysql
```

Tables are created on startup. When a new version adds columns, the backend adds them
automatically and keeps existing data (`Database upgraded, added columns: ...` in the log).
For renames or type changes in production, add Alembic migrations.

---

## Coupons

Coupons are managed from **Admin > Coupons**.

1. **Pick the discount** on the bar: **25%, 50%, 75% or 100%**. A preview shows the price the client will pay.
2. Click **Generate**. A single-use code like `LEX-7KQ2M` appears with a **Copy code** button.
3. Optionally type the client's email and click **Send to client**. The coupon email includes the code, the expiry time and a booking button.
4. The client enters the code in **Use coupon** on the final booking step.

| Rule | Behaviour |
| --- | --- |
| Format | `LEX-` + 5 characters, without look-alikes such as 0/O or 1/I |
| Discounts | 25%, 50%, 75% or 100% off, on every service |
| Single use | Works for one booking only. Once used it stays used, even if the booking is cancelled |
| Expiry | `COUPON_VALID_HOURS` (24) after it is generated. It cannot be extended; generate a new one |
| Email lock | Once emailed, it works only with that email address (`COUPON_LOCK_TO_EMAIL`). An unsent coupon works for whoever enters it |
| One per booking | No combining |
| 100% | Free booking: no payment step, the client clicks **Confirm free booking** |
| Abandoned payment | Closing the payment window does not use up the coupon |
| Expiry during payment | If the client started paying before it expired, the discount still applies |
| Refunds | A cancelled booking refunds what the client actually paid |

The coupon list shows each code's discount, client, time left or usage (booking ID, client,
amount paid) and status: **Unused, Used, Expired or Deactivated**. Unused coupons can be
copied, sent or resent, and deactivated.

---

## Business rules

| Rule | Behaviour |
| --- | --- |
| Double booking | Impossible. A database unique constraint allows one booking per slot, even if two people pay at the same moment |
| Slot hold | The slot is held while the client pays. It is released when they close the payment window, or after `HOLD_MINUTES` (15) |
| Late payment | A payment that arrives after the slot went to someone else is refunded in full automatically |
| Client cancels | 24 hours or more before: full refund. Within 24 hours: online changes are closed |
| Client reschedules | Once, free, up to 24 hours before |
| Firm cancels | Always a full refund |
| Prices | Always set by the server. Each booking stores its fee, discount and amount paid, so later changes never affect it |
| Data collected | Name, email and phone only. No case or invention details |

---

## Running the tests

```bash
cd backend
python -m unittest discover -s tests -t . -v
```

- `test_rules.py`: slots, booking window, refund policy, emails
- `test_coupon_rules.py`: coupon codes, discounts, status, coupon email
- `test_api_flow.py`: end-to-end API flows in test mode. Booking, double booking, payment,
  assignment, reschedule, cancel, slot release, late payment, hold expiry, and coupons
  (generate, send, email lock, single use, deactivate, expiry, free booking)

The API tests need the backend requirements installed and use their own temporary database.

---

## API reference

Interactive docs: http://localhost:8000/docs

**Client**

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/services` | Active services |
| GET | `/api/availability` | Next 30 days with open slots |
| POST | `/api/coupons/check` | Preview a coupon's discount |
| POST | `/api/bookings/hold` | Hold a slot, apply a coupon, create the Razorpay order (or confirm a free booking) |
| POST | `/api/bookings/verify` | Verify the payment and confirm the booking |
| POST | `/api/bookings/release` | Release the slot when the payment window is closed |
| GET | `/api/manage/{token}` | Booking details for the client |
| POST | `/api/manage/{token}/reschedule` | Client reschedule |
| POST | `/api/manage/{token}/cancel` | Client cancel with refund |

**Admin** (no sign-in yet, see below)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/admin/days` | Bookings by day |
| POST | `/api/admin/bookings/{id}/assign` | Assign an employee (emails them) |
| POST | `/api/admin/bookings/{id}/cancel` | Firm cancel, full refund |
| GET / POST / PATCH | `/api/admin/employees` | Employees |
| GET / POST / DELETE | `/api/admin/blocked-dates` | Holidays |
| GET | `/api/admin/coupons/config` | Allowed discounts and coupon settings |
| GET | `/api/admin/coupons` | Coupon list with usage |
| POST | `/api/admin/coupons` | Generate a coupon |
| POST | `/api/admin/coupons/{id}/send` | Email (or resend) a coupon to the client |
| POST | `/api/admin/coupons/{id}/deactivate` | Deactivate an unused coupon |

**Webhooks**

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/webhooks/razorpay` | Razorpay payment confirmation |

---

## Adding it to the company website

1. Deploy the backend (any Python host) and the frontend (`npm run build`, then host `frontend/dist`).
2. Set `VITE_API_BASE_URL` in `frontend/.env` to the backend URL, and `FRONTEND_BASE_URL` and
   `CORS_ORIGINS` in `backend/.env` to the frontend URL.
3. Point the website's **Book a consultation** button to `https://<booking-domain>/book`, or embed that page in an iframe.
4. Add the Lextria seal logo as `frontend/public/logo.png`.

---

## Before going live

- [ ] **Add sign-in to the admin dashboard.** All admin API routes go through `require_admin()` in
      `backend/app/routers/admin.py`, so authentication is added in one place. Also protect the `/admin` page.
- [ ] Serve both apps over **HTTPS**.
- [ ] Connect Zoho Mail, Google Calendar and Razorpay, and test the full flow with Razorpay test keys.
- [ ] Set up the Razorpay webhook.
- [ ] Replace the placeholder service names and descriptions.
- [ ] Update the frontend packages (`npm audit`) before deploying.
- [ ] Switch Razorpay to live keys after KYC approval.

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `npm run dev`: could not read package.json | Run it inside the `frontend` folder |
| Booking page says it cannot reach the server | Start the backend on port 8000 |
| Startup log says `Email: console` | `SMTP_USERNAME` or `SMTP_PASSWORD` is empty, or the file is not named exactly `.env` inside `backend` |
| Zoho login fails | Use an app-specific password, check `SMTP_HOST` (`smtppro.zoho.in` vs `smtp.zoho.in`), and enable IMAP access |
| No Meet link in emails | Google is not connected yet (`Google Calendar: off` in the log) |
| Meet links stop after a week | The Google OAuth app is still in Testing; publish it to Production |
| `KeyboardInterrupt` while uvicorn starts | Ctrl+C was pressed during startup; start it again and wait |
| Coupon "sent to a different email address" | Book with the email the coupon was sent to |