<<<<<<< HEAD
# qurlish-crm
=======
# Qurlish CRM — single-company MVP (v0.3 React redesign)

**New React frontend is in `frontend/`**. The existing FastAPI API and legacy HTML/JS version are preserved. For the NEW premium landing and professional CRM UI, use **http://127.0.0.1:5173/** after starting both servers. Port 8000 displays the **old legacy UI**.

## New React frontend setup

1. In terminal A, start existing backend as documented below; ensure development DB and `JWT_SECRET` are configured.
2. In terminal B:

```bash
cd frontend
npm install
npm run dev
```

3. Open `http://127.0.0.1:5173/` for landing; click **Xonadon tanlash** to view inventory, **Xodimlar uchun** for CRM login. `npm run build` and `npm run typecheck` are local verification commands.

Read `frontend/README.md`, `DESIGN.md` and `docs/ux-review.md` for scope and limitations. **Real 3D is not yet included.**

---

# Qurlish CRM — single-company MVP

**Status:** working local API + frontend integration, demo inventory only; **not production ready**. Public landing and 2D selection remain available without login; `/staff` is a separate authenticated CRM. **One company only**. `app.js` still contains a clearly labeled, public synthetic CRM demonstration; real staff data is accessible only through `/staff` and authenticated endpoints.

## Quick start (local, demo-only SQLite)

```bash
cd qurlish-crm
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
export DATABASE_URL=sqlite:///./demo-only.db
export JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DEMO_DATABASE_ONLY=1
export DEMO_ADMIN_EMAIL=admin@example.test
export DEMO_ADMIN_PASSWORD='set-a-unique-password-at-least-12-chars'
python backend/demo_seed.py
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/` (public) and `http://127.0.0.1:8000/staff` (staff). SQLite is **only for local demo and tests**. Seed refuses existing inventory. Never run demo seed on production.

### PostgreSQL deployment preparation (NO deployment performed)

Set `DATABASE_URL=postgresql+psycopg://user:password@host:5432/database`, `JWT_SECRET` a long random secret, `COOKIE_SECURE=1` behind HTTPS. The app currently uses `Base.metadata.create_all` for initial local prototyping; **Alembic migrations, production inventory import, backups, TLS, reverse-proxy trust configuration, rate limiting, monitoring, CSRF hardening, secret management and operational security review are required before real customer data**. Do not run this app publicly or use real leads until these are complete.

## Features
- Public inventory `GET /api/public/units`; no login required, reads database, no fake inventory when connected.
- Public lead POST with required idempotency key, availability recheck, duplicate replay, backend persistence.
- Staff login/logout via HttpOnly, SameSite=Strict cookie; passwords hashed using Argon2id.
- Authenticated staff `/api/crm/leads`, `/api/crm/metrics`, stage changes, notes and event history; no sale confirmation endpoint.
- Admin-only reservation changes; **sold** state cannot be set via UI/API in this version.
- `/staff` dashboard/kanban/contacts/API errors; keyboard-operable stage select and tel link.
- 4 × 7 × 3 = 84 **synthetic demo** inventory rows via explicit seed command.

## Tests

```bash
pytest -q tests/test_api.py tests/smoke_test.py
node --check app.js && node --check live.js && node --check staff.js
```

## Missing / limitations
- True interactive Three.js, cutaway/interior, 3D fallback switch (2D works), authoritative plans, real prices, sale approvals, full lead lifecycle, WebSocket/realtime, uploads, staff management UI, reporting time-zone rules, deployment, migration/versioning, robust rate limiting, and anti-spam. These features are not claimed as ready.
- Tenant isolation is not applicable because this instance represents ONE company. Do not use it to service multiple companies without a tenant model and authorization tests.
- No verified browser screenshots or measured FPS/Core Web Vitals in this deliverable.
>>>>>>> main
