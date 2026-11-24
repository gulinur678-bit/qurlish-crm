# Qurlish CRM · React frontend v0.3

React + TypeScript + Vite redesign, deliberately integrated with the **existing** FastAPI endpoints. Both public and staff pages use live API responses; no synthetic data is silently generated in the React frontend.

## Run on your Mac (two terminals)

Terminal A — existing backend (from repository root):

```bash
cd ~/Desktop/qurlish-crm
source .venv/bin/activate
# configure your existing local development DATABASE_URL/JWT_SECRET
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal B — React development server:

```bash
cd ~/Desktop/qurlish-crm/frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. Choose **Xodimlar uchun** for the protected CRM. Vite forwards `/api` to the local backend; do **not** open the old backend's `:8000` homepage when checking the new React UI. The Vite proxy rewrites the dev-only Origin header to satisfy the backend's origin guard. Do not re-use that origin rewrite in production reverse-proxy configuration.

## Verify

```bash
cd frontend
npm run typecheck
npm run build
```

Existing backend tests: from repository root `python -m pytest -q tests/test_api.py tests/smoke_test.py`.

## Screens

- `/`: premium editorial landing, image-led hero, features, selected-apartment CTA.
- `/apartments`: progressive selection by building → floor → unit; conceptual 2D floorplan (not a technical drawing), real unit records from `/api/public/units`, application form to `/api/public/leads` with idempotency key. Does not submit when API offline.
- `/crm`: employee login, API-based dashboard with period filter, lead table, Kanban and lead history/internal notes.

## Intentional limitations

- No 3D/WebGL or true floorplan/cutaway in v0.3. Dedicated 2D fallback functions now; `React Three Fiber` would be a separate v0.4.
- Photos are illustrative third-party images; do not imply they represent actual property, plan, award, pricing or reviews.
- No sale-confirmation UI because the server has no approved sale-confirmation workflow.
- Backend dev database needs explicitly created inventory and users. No automatic seeding or deployment.
- Existing backend SQLite local demo is not production. Harden security and migrate to PostgreSQL before real customer use.
- Public and staff performance, accessibility and device screenshot checks require manual browser runs. No measured FPS, LCP or production-grade accessibility claims.
