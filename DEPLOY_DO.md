# Deploy (DigitalOcean Droplet + Caddy + Docker Compose)

This repo supports a simple production deployment:

- **Web**: Vercel at `app.systesign.com`
- **API**: FastAPI on a DigitalOcean Droplet at `api.systesign.com` behind **Caddy** (TLS + WebSockets)

## Prereqs on the Droplet
- Ubuntu 24.04
- Docker + Docker Compose installed and working (`docker ps` works as `deploy`)
- DNS: `api.systesign.com` **A record** → Droplet public IP

Ports that must be open: **80/tcp** and **443/tcp**.

## 1) Clone the repo on the Droplet

```bash
sudo apt-get update && sudo apt-get install -y git
cd /home/deploy
git clone https://github.com/havryleshko/system-design.git
cd system-design
git checkout chore/prod-rollout-prep
```

## 2) Create backend env file

Create `/home/deploy/system-design/apps/backend/.env` (do not commit it).

Minimum required:
- `OPENAI_API_KEY`
- `LANGGRAPH_PG_URL`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_JWT_SECRET` (recommended)
- `SENTRY_DSN` (backend DSN)

Recommended guardrails (launch defaults):
- `RUN_CONCURRENCY_LIMIT=1`
- `RUN_DAILY_LIMIT=3`
- `RUN_TIMEOUT_SECONDS=420`
- `RUN_MAX_TOTAL_TOKENS=20000`
- `CORS_ALLOW_ORIGINS=https://app.systesign.com`

## 3) Start the stack

From repo root on the Droplet:

```bash
docker compose up -d --build
docker compose ps
```

Follow logs (optional):

```bash
docker compose logs -f --tail=200
```

## 4) Smoke tests

### API health

```bash
curl -fsSL https://api.systesign.com/
curl -fsSL https://api.systesign.com/health/checkpointer
```

You should get `{"status":"ok"}`.

### Web flow
- Open `app.systesign.com`
- Login
- Start a run and confirm:
  - streaming works (WebSocket)
  - it completes and stores output

## Rollback (quick)

```bash
git log --oneline -5
git checkout <previous_commit_or_tag>
docker compose up -d --build
```


