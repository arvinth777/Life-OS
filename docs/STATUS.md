# Delivery status

14 September 2026. This document separates running features from scaffolding. No integration is represented as live merely because a configuration field exists.

## Phase 1

Implemented and running locally against real PostgreSQL: all nine modules, single-owner Argon2/JWT authentication, Alembic migrations, seeded curriculum and exercise library, in-app reminders, and complete CSV/JSON export/import. With the owner's explicit approval, migrations 0001–0002, seed and owner bootstrap were applied to Neon production after verification on a temporary branch. That test branch was deleted. Database connection and encryption key are in Vercel's encrypted environment settings. The API was deployed to the verified Hobby account and Vercel reports **Ready** at `https://life-os-api-six.vercel.app`. Local owner credentials also work for the separately initialized online owner. The frontend build targets that API; Sites deployment status is tracked separately in the delivery response. No personal journal, task or health history was copied from the local database. The separate Neon Hello function remains a demonstration and is not used by Life OS.

Live verification boundary: database migrations, seed counts and owner bootstrap were verified directly against Neon; Vercel build/deployment status is Ready. Production HTTP workflows have not been smoke-tested in this session. The backend acceptance suite and browser backup/restore checks ran locally.

| Acceptance criterion | Evidence |
|---|---|
| Fresh setup is documented | README lists runtimes, DB creation, environment values, migration, seed, owner creation and frontend/API startup. Python dependencies and npm packages have locks. Initial migration ran successfully from an empty local Postgres database. A separate remote-host fresh clone has not been executed. |
| All modules save and read back | PostgreSQL acceptance suite creates records across every module and disposes/reopens database connections. Browser tests create tasks, journal entries, traits, terms, projects, workouts/sets and calendar events through forms; task data survives a browser reload. Local API was also restarted during verification with records preserved. |
| Every table exports and restores | All **44 application tables**, including backup transport state, plus Alembic revision, export to per-table CSV/JSON. JSON, ZIP and CSV-only ZIP round trips into an empty DB preserve every row/type. Invalid restore rolls back. A ZIP larger than 4.5 MB was downloaded and atomically restored using 1 MB chunks. |
| Streaks handle timezone/skipped days | Direct calculations and dashboard query tests cover UTC versus America/Los_Angeles, midnight crossings, three qualifying sources and a skipped day. |
| SM-2 five-review sequence | Grades 5,5,4,3,5 produce intervals **1,6,16,43,110** and ease **2.6,2.7,2.7,2.56,2.66**. Failure resets repetitions/interval; repeated failures hit the 1.3 floor. |
| DSA spine is complete | Five Python primer lessons, arrays/strings foundations, five complete patterns with three-step visual walkthroughs, and **15 problems**, each with three hints and a worked solution. All 15 solutions pass hand-selected examples/edge cases. |
| Muscle map uses actual mappings | Three Push-up sets yield chest 3, shoulders 1.5, triceps 1.5 weighted sets. Browser verification checks front/back highlights after logging a real set. |
| No external integrations required | Missing-key tutor/feedback states are disabled; every module remains navigable. Core route checks run without LLM or wearable configuration. |
| Forward migrations require no manual SQL | Alembic 0001 creates the initial schema; 0002 adds encrypted backup transfers. Both are explicit forward migrations. Legacy 0001 backups remain restorable. |

Verification: **22 backend acceptance tests passed** against PostgreSQL. The original end-to-end browser suite covered loaded module views at **320, 375, 414, 768 and 1440 px**; a new isolated browser test also passed for chunked backup download, restore and subsequent sign-in. A genuine mobile overflow from a table's hidden accessibility label was corrected before the original pass. The React production build passes. The original frontend runtime dependency audit reported zero advisories; dependencies have not changed. A harmless Starlette test-client deprecation warning remains; it does not fail tests.

Visual inspection covered the loaded desktop dashboard, with a workbench layout, cobalt active controls, clearly separated tasks/agenda, and a functional reading surface. Browser geometry checks cover the mobile routes. No fake personal history is seeded. Temporary QA records are removed from the local workspace after tests.

## Wired integrations and deferred work

| Route / feature | Actual state |
|---|---|
| Manual normalized ingestion | Wired, owner authenticated, atomic and idempotent. Water entry is disabled when the owner chooses Samsung-only water; fresh installs default to manual. |
| Health Connect webhook | Receiver, separate bearer authentication, mapping editor/preview, nested-field normalization, multiple configured streams, dedupe and body-metric suggestions implemented. Tested synthetically, **not paired with a physical phone**. |
| LLM journal/tutor | Shared OpenAI adapter, encrypted key, explicit actions, stored feedback/usage implemented. Disabled by default. **No live inference call tested**; no provider key provisioned. |
| Google Calendar | Local calendar works. Schema, timestamp conflict resolver and detailed resumable-sync contract are scaffolded. **OAuth, incremental transport, two-way pushes, channel handling, and live polling are not implemented**. Settings cannot activate them yet. |
| Samsung private cloud | Pinned 0.7.1 client, encrypted account/session/cursor storage, macOS sign-in helper and bounded GET importer implemented. Synthetic auth/resume checks pass; real Samsung account and field units are not yet verified. |
| Open Wearables | Decision/status scaffold only. No mobile companion, SDK pin, Wearables backend or MCP connection built. Deferred pending webhook insufficiency. |

## Explicit content stubs

Eight visibly incomplete lessons: Stacks and queues; Linked lists; Recursion from first principles; Trees and traversal; Heaps and priority queues; Graphs and traversal; Backtracking; Dynamic programming. They have ordered titles, empty teaching bodies and `incomplete=true`, and can be authored in-app. No placeholder replaces any of the five required patterns.

## Remaining limits

- Vercel API deployment is Ready. Long-term unattended operation, real Google accounts, actual bridge payloads/Android background delivery and real Samsung Cloud retrieval remain unverified.
- CSV files intentionally use JSON-encoded cells to preserve exact values. They are designed for lossless restore, not automatic spreadsheet-type guessing.
- Health sum metrics expect nonoverlapping increments. The app cannot deduplicate overlapping readings from *different* sources using a contract that only keys by source and external ID. Select one active source per overlapping metric/window.
- Most reference/admin data use consistent table editors; nested curriculum/mapping/recurrence data use documented JSON fields. Body metrics, grading bands and everyday actions have ordinary labeled controls.
- On-demand reminders catch up when the app is opened; no promise of background delivery while it is closed.

See [INTEGRATIONS.md](INTEGRATIONS.md) for all deferred Phase 2/3 work; nothing has been silently removed from the planned scope. Publication results are recorded separately in the task handoff.

## Watch7 / S24 FE setup — 14 September 2026

The receiver has a pinned 37-reading preset for the free HC Webhook v1.9.20 APK. Samsung-only water excludes old manual drinks without deleting them. Incremental missing arrays, source filtering, sleep stages, deterministic legacy identities and 6,001-record retries are tested. Dashboard totals use SQL; history pages stay bounded. All 22 backend acceptance checks pass on disposable Postgres, including encrypted Samsung sign-in/replay and resumable raw stress pages. The watch/water browser checks pass at 375, 768 and 1440 px, and the production React build passes. Swift callback helper compilation passes with a macOS deprecation warning.

The live receiver token, Samsung mapping and Samsung-only water preference were configured through the authenticated API. The private header is delivered outside Git in WATCH_CONNECTION.md. Phone installation/permissions, Samsung sign-in and first real sync still need completion. No real health data was fabricated for live verification. The private importer excludes unsupported document structures; it does not claim a complete Samsung backup. The identity limits are documented in PHONE_SETUP.md and INTEGRATIONS.md. No paid plan, Android codebase or persistent worker was added.
