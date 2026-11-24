# UX review — Qurlish CRM v0.3

**Scope:** Redesign source vs legacy v0.2 in repository; screenshots not captured. Five issues below are based on inspected legacy source, not a measured usability study.

| Prioritized issue / screen | Evidence in prior source | v0.3 change | Verification |
|---|---|---|---|
| 1. Public landing / CRM separation | `index.html` + `app.js` contains a visible synthetic CRM demonstration; genuine staff data at `/staff` | Separate public React pages `/`, `/apartments` and protected `/crm` | Requires browser QA |
| 2. Product-selection trust | `live.js` replaced generated unit lookup dynamically; errors could expose synthetic inventory | React selector reads only `/api/public/units`; API-down/empty explicit, form never submitted offline | Requires connected API QA |
| 3. Product selection hierarchy | legacy large combined page + 2D interaction | Clear building → floor → unit panels with selected detail and text statuses | Requires keyboard/touch QA |
| 4. CRM hierarchy | prior `staff.js` assembled dashboard and Kanban in imperative markup | Persistent sidebar, KPI strip, period-based chart and funnel, task-oriented Kanban and clients | Requires viewport QA |
| 5. CRM error and undo | previous handlers performed stage changes then reload; rollback of one select only | React optimistic update with collection rollback, inline error and keyboard stage control | Requires API rejection test |

## States matrix

| Screen | Loading | Empty | Error | Success / blocked |
|---|---|---|---|---|
| Selector | loading panel | no inventory | API error; no fake leads | status+detail; reserve/sold submit disabled |
| Lead form | button disabled | n/a | preserves name/phone and retry key | server lead ID shown, duplicate click blocked |
| Dashboard | loading panel | zeros and empty chart | retry state | same selected period for metrics and lead list |
| Kanban | loads leads | empty columns | rollback alert | keyboard select or mouse drag |
| Client drawer | history fetch | no events | inline alert | notes are internal, `tel:` is not VoIP |

## Implementation / QA status

- React code and styling written. Dependencies could not be installed in the build environment; no successful full `npm run build`/`typecheck` has been verified here.
- Original Python API tests previously reported as passing; this redesign did **not** change the backend, nor claim new backend test execution.
- Browser screenshots 390/768/1440 and performance/contrast audits still pending. Avoid claiming results without measurement.
- No deploy, no production seed or live customer data. Browser cache and third-party illustrative imagery may impact perceived load; use verified local optimized images before production.
- Subsequent 3D scope: lazy-load React Three Fiber, static list fallback, isolate selected building without occlusion, no camera jumps, reset, previous/next, reduced motion, idle rendering, cutaway **concept** only.
