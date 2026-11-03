# Stripe Donations Setup Checklist

Account: Bowen Public Charitable Trust (set up October 2026). The old keys
from Joe's personal account expired and must not be reused.

## What the code actually needs

The backend (`backend/app/main.py`, "Stripe Donation Endpoints") uses only:

- `STRIPE_SECRET_KEY` — `sk_test_...` locally, `sk_live_...` in production
- `STRIPE_WEBHOOK_SECRET` — `whsec_...` for the endpoint that receives events
- `FRONTEND_URL` (optional) — e.g. `https://bowenpublic.com`, used for the
  success/cancel redirects. Without it the backend uses the request Origin if
  it is an allowed CORS origin.

`STRIPE_PUBLISHABLE_KEY` and `STRIPE_PRICE_ID` are **not** used. Checkout is
created server-side with an inline price for whatever amount the donor types,
so no Product or Price needs to exist in the dashboard.

## 1. Keys (test mode first)

- [ ] Dashboard → Developers → API keys, toggle **Test mode** → copy the secret key
- [ ] Put it in `backend/.env` as `STRIPE_SECRET_KEY`
- [ ] Run `backend/venv/bin/python -m pytest tests/stripe -v -s` (see `tests/stripe/README.md`)

## 2. Webhook endpoint (production)

- [ ] Developers → Webhooks → Add endpoint
- [ ] URL: `https://<railway-backend-host>/api/stripe/webhook`
- [ ] Events: `checkout.session.completed`
- [ ] Copy the signing secret (`whsec_...`) into Railway as `STRIPE_WEBHOOK_SECRET`

## 3. Production env vars (Railway backend service)

- [ ] `STRIPE_SECRET_KEY` = `sk_live_...`
- [ ] `STRIPE_WEBHOOK_SECRET` = `whsec_...` from step 2
- [ ] `FRONTEND_URL` = `https://bowenpublic.com`
- [ ] `ALLOWED_ORIGINS` includes `https://bowenpublic.com`

## 4. Local webhook testing

- [ ] `stripe login` (choose the Trust account)
- [ ] `stripe listen --forward-to localhost:8105/api/stripe/webhook`
- [ ] Use the `whsec_` it prints as `STRIPE_WEBHOOK_SECRET` in `backend/.env`
- [ ] `stripe trigger checkout.session.completed` and watch for `[DONATION]` in the backend log

## 5. Go-live check

- [ ] Account shows charges and payouts enabled (the test suite asserts this with a live key)
- [ ] Bank account for payouts is the Trust's
- [ ] Statement descriptor reads as Bowen Public
- [ ] One real $1 donation on bowenpublic.com/donate, then refund it from the dashboard
