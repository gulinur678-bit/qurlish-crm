# Qurlish CRM — v0.3 Design decisions

**Date:** 2026-11-23. **Status:** React frontend source authored; dependencies/build/browser visual verification still pending. Single-company prototype, not production-ready.

## Users, journeys and IA

1. Buyer (no login): landing → **Xonadon tanlash** → building → floor → unit → details → enquiry; API success/error shown and idempotent retry key held for that attempt.
2. Sales manager: `/crm` login → dashboard (7/30/90 days) → Kanban or client table → lead history → internal note/`tel:`. Admin and manager both use backend-authorized operations. **No sale confirmation action**.

Landing IA: navbar → hero → company concept → values → apartment selector CTA → enquiry CTA → contact clarification. Staff login is separate from public primary CTA.

## Wireframes / intended page states

- Landing desktop: fixed-height hero with editorial headline and one primary action; below, airy two-column about section, ruled list, split-screen selection CTA; mobile stacks content, a collapsible nav never covers sections.
- Apartment selection desktop: 3-column building/floor controls | apartment grid | selected detail; medium screens detail moves under grid, small screens one column; states loading, empty inventory, failed API, available/reserved/sold, pending/success/error form. Selectable even without 3D.
- CRM desktop: dark 253px sidebar | topbar | KPI row | chart/status | funnel/recent; 768px mobile navigation toggles; 390px KPIs are 2 columns and tables scroll. States loading, empty 7/30/90 period and API error.
- Kanban: 4 existing authorized backend stages; dragging or stage select changes a card. Response rejection rolls back local state. Keyboard users use the stage select.
- Client drawer: contact phone, status, events, internal note. Escape/close returns focus to invoking element; **complete focus trapping is not yet independently verified**.

## Design language and color roles

- Typeface: Manrope for headings, DM Sans for interface/body, Georgia italic selectively for editorial emphasis.
- Background `#f7f9f7`, paper `#fff`, ink `#20322f`, forest primary `#243d38`, muted text `#78817d`, warm editorial accent `#aa8861`, border `#e6e9e5`.
- State: available `#2e7b63`, reserved `#d9a35e`, sold neutral `#b9c0c1`. Status is *always* shown in readable text too.
- Layout: container up to 1320px; desktop spacing 40–134px based on section context; compact CRM panels have 14–28px padding; corners 6–12px; shadows minimal.
- Motion: single subtle hero entrance, hover states; `prefers-reduced-motion` disables entrance/transitions and smooth scrolling.
- Contrast: all relevant text/interactive states require browser verification at >=4.5:1 normal and >=3:1 large; **not yet measured**.
- Touch: important navigation/actions aim at >=44 CSS px; compact secondary links may be smaller and should be checked in device QA.

## API mappings

`GET /api/public/units`, `POST /api/public/leads` with `Idempotency-Key`; `/api/auth/login`, `/api/auth/logout`, `/api/crm/me`, `/api/crm/metrics?days=`, `/api/crm/leads?days=`, `/api/crm/leads/{id}/stage`, `/api/crm/leads/{id}/events`, `/api/crm/leads/{id}/notes`.

Never synthesize backend inventory in this React UI. Dashboard metrics and lead records use the same selected period. Unit statuses are current inventory, not filtered by leads' date; legends explain units.

## Files added/changed in v0.3

- Added `frontend/index.html`, `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/src/{api.ts,main.tsx,styles.css}`, `frontend/README.md`.
- Added `.gitignore` for secrets, virtual env, dev databases and node artifacts.
- Updated `DESIGN.md`, `docs/ux-review.md` and project `README.md`.
- **Unchanged:** `backend/main.py`, database structure, legacy frontend, tests, auth and API contracts. Production unmodified.

## Measured outcomes and limits

- React source authored; direct dependency installation did not finish in the execution environment. **No passing npm build/typecheck evidence yet**.
- Static syntax transpilation performed separately if noted in UX review; not equivalent to typecheck/build.
- No verified desktop/mobile before/after screenshots; no measured Core Web Vitals/FPS.
- Actual WebGL, cutaway, authoritative plans, approved sales, Alembic migrations, PostgreSQL verification, production security, anti-spam, company brand assets and phone details pending.
