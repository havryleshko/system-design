# Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                            │
└───────────────────────┬─────────────────────────────────────────┘
                        │ HTTPS
                        │
        ┌───────────────▼───────────────┐
        │   VERCEL (Next.js Frontend)   │
        │   - Server Components          │
        │   - API Routes                 │
        │   - Static Assets (CDN)        │
        └───────────────┬───────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        │                               │
┌───────▼────────┐          ┌──────────▼────────┐
│   SUPABASE     │          │   RENDER (Python)  │
│   - Auth       │◄─────────┤   - FastAPI        │
│   - Database   │   JWT    │   - LangGraph API  │
│   - RLS        │          │   - Port 2024      │
└────────────────┘          └──────────┬─────────┘
                                       │
                                       │ API Calls
                                       │
                          ┌────────────▼────────────┐
                          │   LANGGRAPH CLOUD API   │
                          │   - Thread Management   │
                          │   - State Persistence    │
                          │   - Agent Execution     │
                          └────────────┬────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │      OPENAI API         │
                          │   - GPT Models          │
                          │   - Embeddings          │
                          └─────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    STRIPE (External)                             │
│   - Checkout Sessions                                            │
│   - Webhooks → Vercel API Routes                                │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Example: User Creates a Thread

1. **User clicks "Start Design"**
   - Browser → Next.js Server Component
   - Server Component checks Supabase session (JWT cookie)
   - If authenticated, proceed; else redirect to `/login`

2. **Create Thread**
   - Next.js Server Action calls `createThread()`
   - Makes authenticated request to Render backend: `POST /threads`
   - Backend validates JWT, extracts `user_id`
   - Backend calls LangGraph API: `POST /threads` (with user_id)
   - LangGraph creates thread, returns `thread_id`
   - Backend stores mapping (thread_id → user_id)
   - Returns `thread_id` to frontend

3. **Frontend stores thread_id**
   - Sets HTTP-only cookie via Server Action
   - Redirects to `/chat` or `/clarifier`

4. **Chat Interaction**
   - User sends message
   - Frontend → Next.js API Route → Render backend
   - Backend → LangGraph: `POST /threads/{id}/runs/{assistant}/wait`
   - LangGraph executes agent graph (may take seconds/minutes)
   - LangGraph calls OpenAI API during execution
   - Returns final state when complete
   - Frontend displays result

## Cost Breakdown (Monthly)

### Free Tier (MVP)
- Vercel: $0 (Hobby)
- Render: $0 (Free - sleeps after inactivity)
- Supabase: $0 (500MB DB, 2GB bandwidth)
- **Total: $0** (with limitations)

### Starter Tier ($7-20/month)
- Vercel: $0 (Hobby) or $20 (Pro)
- Render: $7 (Starter - 512MB RAM, no sleep)
- Supabase: $0 (Free tier)
- **Total: $7-27/month**

### Production Tier ($70-100/month)
- Vercel: $20 (Pro)
- Render: $25 (Standard - 2GB RAM)
- Supabase: $25 (Pro - 8GB DB, 100GB bandwidth)
- **Total: $70/month**

### Scale Tier ($100-300/month)
- Vercel: $20-100 (Pro/Enterprise)
- Render: $75+ (Pro) or Fly.io multi-region
- Supabase: $25-100 (Pro/Enterprise)
- **Total: $120-300/month**

## Latency Targets

| Operation | Target | Typical |
|-----------|--------|---------|
| Page Load (SSR) | < 200ms | 100-300ms |
| API Call (Auth) | < 100ms | 50-150ms |
| Database Query | < 50ms | 20-100ms |
| LangGraph Call | < 500ms | 200-1000ms |
| AI Execution | 5-60s | Variable |

## Environment Variables Reference

### Frontend (Vercel)
```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx...

# Backend API
NEXT_PUBLIC_LANGGRAPH_BASE_URL=https://langgraph-backend.onrender.com

# App URL
NEXT_PUBLIC_APP_URL=https://yourapp.vercel.app

# Stripe (public)
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_xxx...

# Stripe (server-side only)
STRIPE_SECRET_KEY=sk_xxx...
STRIPE_PRICE_ID_PRO=price_xxx...
STRIPE_WEBHOOK_SECRET=whsec_xxx...
```

### Backend (Render)
```env
# LangGraph
LANGGRAPH_API_KEY=xxx...

# OpenAI
OPENAI_API_KEY=sk-xxx...

# Supabase (for admin operations)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJxxx...

# Stripe (for webhooks)
STRIPE_SECRET_KEY=sk_xxx...
STRIPE_WEBHOOK_SECRET=whsec_xxx...
```

## Deployment Checklist

- [ ] Set up Supabase project
- [ ] Configure Supabase RLS policies
- [ ] Create Stripe account and products
- [ ] Get API keys for all services
- [ ] Deploy backend to Render
- [ ] Configure Render environment variables
- [ ] Test backend health endpoint
- [ ] Deploy frontend to Vercel
- [ ] Configure Vercel environment variables
- [ ] Set up Stripe webhooks pointing to Vercel
- [ ] Test authentication flow
- [ ] Test API integration
- [ ] Test payment flow
- [ ] Configure custom domain (optional)
- [ ] Set up monitoring/error tracking
- [ ] Configure backup strategy

