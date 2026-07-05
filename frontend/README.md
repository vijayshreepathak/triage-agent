# ViZ Triage Agent — Frontend

Next.js 16 App Router UI for the clinical triage agent. Deploy this folder to **Vercel**.

**Full documentation:** [../README.md](../README.md)  
**Repository:** [github.com/vijayshreepathak/triage-agent](https://github.com/vijayshreepathak/triage-agent)

## Quick start

```bash
npm install
cp .env.example .env.local   # set API_BACKEND_URL=http://127.0.0.1:8000
npm run dev
```

Open http://localhost:3000 (FastAPI backend must run on port 8000).

## Vercel deployment

1. Import the repo on [vercel.com](https://vercel.com)
2. Set **Root Directory** to `frontend`
3. Add env var: `API_BACKEND_URL=https://your-backend.onrender.com`
4. Deploy

See the [Production deployment](../README.md#production-deployment) section in the root README.
