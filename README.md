# Consultation Booking Module

A standalone consultation booking module (Vue 3 + FastAPI + Razorpay) built to be added to the
company website later.

## What it does

1. The client clicks **Book a consultation** and picks a service (Service 1, 2 or 3, Rs 10,000 each).
2. They pick a date and one of the 3 fixed daily slots: 10:00 AM, 2:00 PM and 5:00 PM IST, one hour each,
   Monday to Saturday, from tomorrow up to 30 days ahead. Each slot takes one booking, so once a slot is
   taken that day shows only the remaining slots.
3. They enter name, email and phone, review, and pay through Razorpay. **The booking exists only after the
   payment is verified.**
4. On payment, the system automatically creates a Google Calendar event on the company calendar
   (info@lextria.in) **with a Google Meet link**, and emails the client an acknowledgement with the Meet
   link, payment details and a manage-booking link.
5. The admin dashboard shows bookings day by day. The admin assigns an employee to each booking; the
   employee is emailed automatically and added to the calendar invite.

### Rules built in

| Rule | Behaviour |
| --- | --- |
| Double booking | Impossible: a database unique constraint allows only one booking per slot, even if two people click at the same moment. |
| Slot hold while paying | The slot is held until the payment succeeds or fails (the client closes the payment window). Safety net: an unfinished payment releases the slot after 15 minutes. |
| Late payment | If a payment arrives after the slot went to someone else, it is refunded in full automatically. |
| Cancel | Client can cancel up to 24 hours before for a full refund. Within 24 hours, online changes are closed. |
| Reschedule | Client can reschedule once, free, up to 24 hours before. |
| Admin cancel | Always a full refund. |
| Price | Always set by the server. A later fee change never affects existing bookings. |

## Project layout

```
backend/                FastAPI
  app/main.py           app entry, CORS, hold sweeper (runs every minute)
  app/database.py       DATABASE ENTRY POINT (change DATABASE_URL only)
  app/config.py         all settings, read from .env
  app/slots.py          slot rules (times, days, booking window)
  app/policy.py         cancel / reschedule / refund policy
  app/booking_service.py core logic
  app/models.py         tables: services, employees, bookings, slot_locks, blocked_dates
  app/routers/          public.py (client), admin.py (dashboard), webhooks.py (Razorpay)
  app/integrations/     razorpay_client.py, google_calendar.py, mailer.py (Zoho SMTP)
  app/emails.py         email content
  scripts/google_auth.py one-time Google sign-in for info@lextria.in
  tests/                unit tests + end-to-end API test
frontend/               Vue 3 + Vite
  src/views/BookView.vue    4-step booking + payment + confirmation
  src/views/ManageView.vue  client reschedule / cancel (link from email)
  src/views/AdminView.vue   dashboard: bookings by day, assign, cancel, employees, holidays
  src/components/SlotPicker.vue  date strip + 3 daily slots
```

## Run it locally (test mode, no keys needed)

With no Razorpay, Google or SMTP keys, the module runs in **test mode**: payments are simulated, calendar
steps are skipped, and emails are printed in the backend terminal.

**Requirements:** Python 3.11+ and Node.js 18+.

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs to see every API endpoint.

### 2. Frontend (second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173/book for the booking page and http://localhost:5173/admin for the dashboard.

### 3. Run the tests

```bash
cd backend
python -m unittest discover -s tests -t . -v
```

## Connect the real services

Edit `backend/.env`, then restart the backend. The startup log shows which services are on.

### Razorpay

1. In the Razorpay Dashboard switch to **Test mode**, then go to Account & Settings > API Keys and
   generate a key.
2. Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.
3. Webhook (recommended, confirms bookings even if the client closes the browser right after paying):
   Dashboard > Webhooks > Add. URL `https://<your-api-domain>/api/webhooks/razorpay`, events
   `payment.captured` and `order.paid`, set a secret and copy it to `RAZORPAY_WEBHOOK_SECRET`.
   Webhooks need a public URL; for local testing use a tunnel such as ngrok.
4. Make sure payments are set to auto-capture (the default for orders).
5. Switch to live keys only after KYC is approved and everything works in test mode.

### Google Calendar + Meet (info@lextria.in)

1. Go to Google Cloud Console, create a project and enable **Google Calendar API**.
2. Configure the OAuth consent screen and add info@lextria.in as a test user.
3. Create credentials > OAuth client ID > **Desktop app**. Download the JSON as `backend/client_secret.json`.
4. Run `python scripts/google_auth.py`, sign in as **info@lextria.in**, allow access.
5. Copy the three printed values into `.env`.

Every booking then appears in that account's calendar with a Meet link. With `GOOGLE_SEND_UPDATES=all`
Google also sends calendar invites to the client and the assigned employee.

### Zoho Mail

1. In Zoho Mail for info@lextria.in, create an **app-specific password** (My Account > Security >
   App Passwords). Use it if two-factor sign-in is on.
2. Set `SMTP_USERNAME=info@lextria.in` and `SMTP_PASSWORD=<app password>`.
3. `smtp.zoho.in` on port 465 is for Zoho's India data centre. If the account is on zoho.com, use `smtp.zoho.com`.

### Database

Only `DATABASE_URL` changes, for example:

```
DATABASE_URL=postgresql+psycopg://user:password@host:5432/consultations   # pip install "psycopg[binary]"
DATABASE_URL=mysql+pymysql://user:password@host:3306/consultations        # pip install pymysql
```

Tables are created automatically on startup. Add Alembic migrations before changing the schema in production.

## Change the settings

All in `backend/.env`: slot times (`SLOT_TIMES=10:00,14:00,17:00`), session length, working days,
booking window, hold minutes, cut-off hours and number of reschedules. Service names, descriptions and
fees live in the `services` table (seeded in `app/seed.py` on first run).

## Adding it to the company website

1. Deploy the backend (any Python host) and the frontend (`npm run build`, then host `frontend/dist`).
2. Set `VITE_API_BASE_URL` (frontend) to the backend URL, and `FRONTEND_BASE_URL` and `CORS_ORIGINS`
   (backend) to the frontend URL.
3. Point the website's **Book a consultation** button to `https://<booking-domain>/book`, or embed that
   page in an iframe.

## Before going live

- **Protect the admin dashboard.** It has no sign-in yet. All admin API routes go through
  `require_admin()` in `backend/app/routers/admin.py`, so authentication is added in one place. Also
  protect the `/admin` route in the frontend.
- Serve both apps over HTTPS.
- Test the full flow with Razorpay test keys, including closing the payment window and two people booking
  the same slot.
- Replace the placeholder service names and descriptions.

## API summary

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/services | Active services |
| GET | /api/availability | Next 30 days with open slots |
| POST | /api/bookings/hold | Hold a slot and create the Razorpay order |
| POST | /api/bookings/verify | Verify payment, confirm booking |
| POST | /api/bookings/release | Release the slot when the payment window is closed |
| GET | /api/manage/{token} | Client booking details |
| POST | /api/manage/{token}/reschedule | Client reschedule |
| POST | /api/manage/{token}/cancel | Client cancel with refund |
| GET | /api/admin/days | Bookings by day |
| POST | /api/admin/bookings/{id}/assign | Assign employee (emails them) |
| POST | /api/admin/bookings/{id}/cancel | Company cancel, full refund |
| GET/POST/PATCH | /api/admin/employees | Employees |
| GET/POST/DELETE | /api/admin/blocked-dates | Holidays |
| POST | /api/webhooks/razorpay | Razorpay webhook |
