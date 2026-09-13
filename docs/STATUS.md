# Delivery status

13 September 2026. This document separates running features from scaffolding. No integration is represented as live merely because a configuration field exists.

## Phase 1

Implemented and running locally against real PostgreSQL: all nine modules, single-owner Argon2/JWT authentication, Alembic migration, seeded curriculum and exercise library, in-app reminders, and complete CSV/JSON export/import. Production uses a managed Postgres connection supplied through `DATABASE_URL`; no remote database or Python API host has been provisioned in this session.

| Acceptance criterion | Evidence |
|---|---|
| Fresh setup is documented | README lists runtimes, DB creation, environment values, migration, seed, owner creation and frontend/API startup. Python dependencies and npm packages have locks. Initial migration ran successfully from an empty local Postgres database. A separate remote-host fresh clone has not been executed. |
| All modules save and read back | PostgreSQL acceptance suite creates records across every module and disposes/reopens database connections. Browser tests create tasks, journal entries, traits, terms, projects, workouts/sets and calendar events through forms; task data survives a browser reload. Local API was also restarted during verification with records preserved. |
| Every table exports and restores | All **43 application tables**, plus Alembic revision, export to per-table CSV/JSON. JSON, ZIP and CSV-only ZIP round trips into an empty DB preserve every row/type. Invalid restore rolls back. |
| Streaks handle timezone/skipped days | Direct calculations and dashboard query tests cover UTC versus America/Los_Angeles, midnight crossings, three qualifying sources and a skipped day. |
| SM-2 five-review sequence | Grades 5,5,4,3,5 produce intervals **1,6,16,43,110** and ease **2.6,2.7,2.7,2.56,2.66**. Failure resets repetitions/interval; repeated failures hit the 1.3 floor. |
| DSA spine is complete | Five Python primer lessons, arrays/strings foundations, five complete patterns with three-step visual walkthroughs, and **15 problems**, each with three hints and a worked solution. All 15 solutions pass hand-selected examples/edge cases. |
| Muscle map uses actual mappings | Three Push-up sets yield chest 3, shoulders 1.5, triceps 1.5 weighted sets. Browser verification checks front/back highlights after logging a real set. |
| No external integrations required | Missing-key tutor/feedback states are disabled; every module remains navigable. Core route checks run without LLM or wearable configuration. |
| Forward migrations require no manual SQL | Alembic 0001 created the complete schema from an empty database. Current schema matches its immutable migration snapshot. |

Verification: **13 backend acceptance tests passed** against PostgreSQL; **one end-to-end browser suite passed**, covering loaded module views at **320, 375, 414, 768 and 1440 px**. A genuine mobile overflow from a table's hidden accessibility label was corrected before the final pass. The React production build passes. Frontend runtime dependency audit reports zero advisories. A harmless Starlette test-client deprecation warning remains; it does not fail tests.

Visual inspection covered the loaded desktop dashboard, with a workbench layout, cobalt active controls, clearly separated tasks/agenda, and a functional reading surface. Browser geometry checks cover the mobile routes. No fake personal history is seeded. Temporary QA records are removed from the local workspace after tests.

## Wired integrations and deferred work

| Route / feature | Actual state |
|---|---|
| Manual normalized ingestion | Wired, owner authenticated, atomic and idempotent, always available. |
| Health Connect webhook | Receiver, separate bearer authentication, mapping editor/preview, nested-field normalization, multiple configured streams, dedupe and body-metric suggestions implemented. Tested synthetically, **not paired with a physical phone**. |
| LLM journal/tutor | Shared OpenAI adapter, encrypted key, explicit actions, stored feedback/usage implemented. Disabled by default. **No live inference call tested**; no provider key provisioned. |
| Google Calendar | Local calendar works. Schema, timestamp conflict resolver and detailed resumable-sync contract are scaffolded. **OAuth, incremental transport, two-way pushes, channel handling, and live polling are not implemented**. Settings cannot activate them yet. |
| Samsung private cloud | Disabled feature-flag scaffold only; SDK not installed. Encrypted SDK token/cache adaptation, login and verified units deferred. |
| Open Wearables | Decision/status scaffold only. No mobile companion, SDK pin, Wearables backend or MCP connection built. Deferred pending webhook insufficiency. |

## Explicit content stubs

Eight visibly incomplete lessons: Stacks and queues; Linked lists; Recursion from first principles; Trees and traversal; Heaps and priority queues; Graphs and traversal; Backtracking; Dynamic programming. They have ordered titles, empty teaching bodies and `incomplete=true`, and can be authored in-app. No placeholder replaces any of the five required patterns.

## Remaining limits

- Complete production hosting needs the owner's managed Postgres project and Python API host setup. A published static frontend alone cannot save data until its API address is configured.
- Remote deployment, long-term unattended operation, real Google accounts, actual bridge payloads/Android background delivery, and optional private Samsung APIs were not tested.
- CSV files intentionally use JSON-encoded cells to preserve exact values. They are designed for lossless restore, not automatic spreadsheet-type guessing.
- Health sum metrics expect nonoverlapping increments. The app cannot deduplicate overlapping readings from *different* sources using a contract that only keys by source and external ID. Select one active source per overlapping metric/window.
- Most reference/admin data use consistent table editors; nested curriculum/mapping/recurrence data use documented JSON fields. Body metrics, grading bands and everyday actions have ordinary labeled controls.
- On-demand reminders catch up when the app is opened; no promise of background delivery while it is closed.

See [INTEGRATIONS.md](INTEGRATIONS.md) for all deferred Phase 2/3 work; nothing has been silently removed from the planned scope. Publication results are recorded separately in the task handoff.
