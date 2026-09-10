# Mercury Backend Deployment Guide

This guide details containerization, local orchestration, and cloud deployment procedures for the Mercury Customer Intelligence API.

---

## 1. Docker Containerization

Mercury uses a multi-stage production `Dockerfile` based on `python:3.13-slim` to produce lightweight, secure container images.

### Key Architectural Characteristics
- **Multi-Stage Build**: Separate `builder` stage compiles dependencies into a virtual environment (`/opt/venv`). The final `runner` stage contains only the runtime and dependencies, stripping build tools and compilers.
- **Unprivileged Security**: Runs under an unprivileged system user `mercury` (UID `1000`, GID `1000`).
- **Healthcheck**: Automatic container healthcheck probing `GET /health` every 30 seconds via `curl`.
- **Port**: Listens on port `8000` by default.

### Building and Running Locally
```bash
# Build the production image
docker build -t mercury-backend:latest .

# Run container with environment configuration
docker run -d \
  --name mercury-backend \
  -p 8000:8000 \
  --env-file .env \
  mercury-backend:latest

# Check container health status
docker ps --filter "name=mercury-backend"

# View access and application logs
docker logs -f mercury-backend
```

---

## 2. Local Orchestration with Docker Compose

`docker-compose.yml` provides a streamlined development and staging workflow with live code mounting and `.env` binding.

```bash
# Start backend in detached mode
docker compose up -d

# Verify services and health status
docker compose ps

# Follow live access logs
docker compose logs -f backend

# Stop and remove containers
docker compose down
```

---

## 3. Cloud Deployment Descriptors

### 3.1 Render Blueprint (`render.yaml`)
Mercury includes an Infrastructure-as-Code blueprint for Render:
1. Connect repository to [Render](https://render.com).
2. Create a new **Blueprint** and select `render.yaml`.
3. Fill in the sensitive `DATABASE_URL` parameter in the Render Dashboard (pointing to your Neon PostgreSQL cluster with `sslmode=require`).
4. Automatic deployment initializes with zero downtime, using `/health` for zero-downtime rolling deploys.

### 3.2 Heroku / Railway / PaaS (`Procfile`)
Mercury includes a standard `Procfile`:
```text
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```
Railway and Heroku automatically detect the `Procfile` and bind the web process to the dynamically allocated `$PORT`.

---

## 4. Production Environment Configuration Checklist

| Variable | Description | Example / Recommended |
|:---|:---|:---|
| `DATABASE_URL` | Neon PostgreSQL pooled connection string | `postgresql://user:pass@ep-xyz-pooler.neon.tech/mercury?sslmode=require` |
| `ENV` | Application environment | `production` |
| `REQUIRE_AUTH` | Enforce API Key / Bearer JWT auth | `true` |
| `API_KEYS` | Comma-separated pre-shared API keys | `mercury_live_key_xyz...` |
| `JWT_SECRET_KEY` | High-entropy signing secret for JWTs | `64+ char random hex string` |
| `CORS_ORIGINS` | Permitted client origins | `https://mercury.vercel.app` |
| `CACHE_ENABLED` | In-memory TTL caching | `true` |
| `CACHE_DEFAULT_TTL_SECONDS` | Analytical cache TTL | `300` |
| `RATE_LIMIT_ENABLED` | Sliding-window rate limiter | `true` |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | Max requests per minute per IP | `120` |
| `DB_POOL_SIZE` | SQLAlchemy connection pool size | `10` |
| `DB_MAX_OVERFLOW` | Max pool overflow connections | `20` |
