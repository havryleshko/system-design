# Web App (Next.js)

Next.js UI for the System Design Agent.

## Prerequisites
- Node (recent LTS) + pnpm
- A Supabase project (for auth + persistence tables)
- The backend running locally or deployed

## Setup
1) Copy env:
- `apps/web/env.local.example` → `apps/web/.env.local`

2) Install deps (from repo root):
- `pnpm install`

3) Run:
- `cd apps/web && pnpm dev`

## Environment
### Required
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

### Backend wiring
- `NEXT_PUBLIC_BACKEND_URL` (optional; defaults to `http://localhost:8000`)

### Server-side (optional)
Used for admin/webhook routes:
- `SUPABASE_SERVICE_ROLE_KEY`

### Stripe (optional)
If you use the billing routes/webhooks:
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID_PRO`

## Related docs
- Root README: `README.md`
- Backend auth + persistence: `apps/backend/README.md`
