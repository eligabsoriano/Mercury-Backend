---
name: mercury-codegen
description: >-
  Runbook for synchronizing the FastAPI OpenAPI 3.1 schema specification and
  generating TypeScript interface definitions for Mercury Web and Mobile clients.
---

# Mercury Client Codegen Runbook

This skill outlines how to export the OpenAPI 3.1 specification and synchronize the TypeScript types for downstream client applications (`Mercury-Web`, Flutter mobile app).

## Overview

When FastAPI route handlers or Pydantic schemas in `backend/` are updated, client contracts must be refreshed so frontend and mobile developers receive typed interfaces matching the backend.

- Source of Truth: FastAPI route signatures and Pydantic v2 schemas (`backend/routers/`, `backend/schemas/`).
- Specification Target: `openapi.json` and `docs/openapi.json`.
- TypeScript Definitions: `types/api.ts` (generated via `openapi-typescript`).

## Execution Workflow

Run the unified npm command:

```bash
npm run codegen
```

Or execute the steps individually:

```bash
# 1. Export OpenAPI 3.1 specification
.venv/bin/python scripts/export_openapi.py

# 2. Generate TypeScript definitions
npx openapi-typescript openapi.json -o types/api.ts
```

## Verification Checklist

1. Confirm that `openapi.json` contains 25 endpoints across the 6 route modules:
   - System/Health (`/`, `/health`, `/api/health`)
   - Analytics (`/api/analytics/*`)
   - Customers (`/api/customers/*`)
   - Products (`/api/products/*`)
   - Sellers (`/api/sellers/*`)
   - Auth (`/api/auth/*`)
2. Verify that `types/api.ts` compiles cleanly without TypeScript syntax errors.
3. Check `git diff --stat` to verify only the expected schemas were modified.
