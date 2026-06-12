# ShopPulse

> AI-native CRM engine for consumer brands. ShopPulse continuously scans your customer base, surfaces revenue opportunities ranked by urgency and rupee value, and helps you act on them intelligently.

## Structure

```
shoppulse/
├── backend/          FastAPI + PostgreSQL + AI agents
├── channel-stub/     Simulated WhatsApp/SMS delivery with async callbacks
└── frontend/         React + Vite + TailwindCSS
```

## Running locally

### 1. Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in your DB password
createdb shoppulse
python -m app.core.seed     # seeds 500 customers, 1847 orders, 12 campaigns
uvicorn app.main:app --reload --port 8000
```

### 2. Channel Stub
```bash
cd channel-stub
source ../backend/venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env        # set VITE_API_URL
npm run dev                 # opens localhost:5173
```

## Architecture

```
[React Frontend :5173]
        |
        | HTTP (axios)
        v
[FastAPI Backend :8000] ──POST /send──► [Channel Stub :8001]
        ^                                       |
        │                               async callbacks
        └───────POST /callbacks/delivery────────┘
        
[PostgreSQL] ← SQLAlchemy
```

## Scale tradeoffs

**Built for this scope:**
- FastAPI BackgroundTasks for message dispatch — simple, zero infra overhead, fine for hundreds of customers
- 3s polling for live campaign stats instead of WebSockets — simpler to implement, acceptable latency at this scale
- No auth — intentionally skipped, not in CRM demo scope
- WhatsApp + SMS only, no Email/RCS
- Single backend instance, no load balancing

**Would change at scale:**
- Replace BackgroundTasks with Redis + Celery queue. If the server restarts mid-send, messages currently in flight are lost. A durable queue makes dispatch retryable and survivable.
- Dedicated callback worker consuming from queue instead of direct DB writes per callback — at high volume (thousands of callbacks/sec from a real provider), direct writes become a bottleneck fast.
- WebSockets instead of polling — eliminates unnecessary requests, true real-time.
- PgBouncer for DB connection pooling, read replicas to separate analytics queries from write traffic.
- Streaming AI agent responses instead of synchronous — better UX, user sees agent reasoning as it happens.
- Multi-region deployment, CDN for frontend assets.

**Conscious cuts:**
- No user authentication or sessions
- No multi-tenant / multi-brand support
- No Email or RCS channels
- No mobile app
- No real messaging provider integration (Twilio, Meta)
