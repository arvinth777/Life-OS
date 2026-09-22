# Delivery status

22 September 2026. This document separates running features from scaffolding. No integration is represented as live merely because a configuration field exists.

## Phase 1

Implemented and running locally against real PostgreSQL: all nine modules, single-owner Argon2/JWT authentication, Alembic migrations, seeded curriculum and exercise library, in-app reminders, and complete CSV/JSON export/import. With the owner's explicit approval, migrations 0001–0002, seed and owner bootstrap were applied to Neon production after verification on a temporary branch. That test branch was deleted. Database connection and encryption key are in Vercel's encrypted environment settings. The API was deployed to the verified Hobby account and Vercel reports **Ready** at `https://life-os-api-six.vercel.app`. Local owner credentials also work for the separately initialized online owner. The frontend build targets that API; Sites deployment status is tracked separately in the delivery response. No personal journal, task or health history was copied from the local database. The separate Neon Hello function remains a demonstration and is not used by Life OS.

Live verification boundary: database migrations, seed counts and owner bootstrap were verified directly against Neon; Vercel build/deployment status is Ready. The owner login, live bridge credential and Samsung account exchange were verified through authenticated production requests. After fixing source-field filtering, a real phone delivery saved 9,422 readings; the next recognized 1,039 duplicates. Production readback confirmed eight mapped metric types. Samsung Cloud also returned raw numeric records. Other production module workflows have not been smoke-tested in this session. The backend acceptance suite and browser backup/restore checks ran locally.

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

Verification: **41 backend acceptance tests passed** against disposable PostgreSQL. The current end-to-end browser suite passed four active workflows covering all nine modules, hydration, watch data, interaction states, and views at **320, 375, 414, 768 and 1440 px**; the isolated chunked-backup browser test passed in its dedicated earlier run. A genuine mobile overflow from a table's hidden accessibility label was corrected before the original pass. The React production build passes. The original frontend runtime dependency audit reported zero advisories; dependencies have not changed. Two harmless dependency deprecation warnings remain; they do not fail tests.

Visual inspection covered the loaded desktop dashboard, with a workbench layout, cobalt active controls, clearly separated tasks/agenda, and a functional reading surface. Browser geometry checks cover the mobile routes. No fake personal history is seeded. Temporary QA records are removed from the local workspace after tests.

## Wired integrations and deferred work

| Route / feature | Actual state |
|---|---|
| Manual normalized ingestion | Wired, owner authenticated, atomic and idempotent. Water entry is disabled when the owner chooses Samsung-only water; fresh installs default to manual. |
| Health Connect webhook | Receiver, separate bearer authentication, mapping editor/preview, nested-field normalization, multiple configured streams, dedupe and body-metric suggestions implemented. Synthetic checks pass. The physical phone saved 9,422 readings and reported success; the next delivery recognized 1,039 duplicates. Unverifiable distance rows were omitted and reported. Steps, heart rate, oxygen saturation and sleep/stages are confirmed; hydration and background delivery remain unverified. |
| LLM journal/tutor | Shared OpenAI adapter, encrypted key, explicit actions, stored feedback/usage implemented. Disabled by default. **No live inference call tested**; no provider key provisioned. |
| Google Calendar | Local calendar works. OAuth with PKCE/state, encrypted refresh tokens, one-calendar configuration, incremental pull/full 410 recovery, resumable page checkpoints, two-way create/update/delete, etag retry, timestamp conflict logs, recurring masters/exceptions, polling catch-up and validated push channels are implemented and covered by mocked transport tests. A real Google account/calendar authorization is still required for live verification. |
| Samsung private cloud | Pinned 0.7.1 client, encrypted account/session/cursor storage, macOS sign-in helper and bounded GET importer implemented. Real account authorization and raw cloud retrieval work. Stress is unavailable from the catalog route. Field units and complete coverage remain unverified. |
| Open Wearables | Decision/status scaffold only. No mobile companion, SDK pin, Wearables backend or MCP connection built. Deferred pending webhook insufficiency. |

## Explicit content stubs

Eight visibly incomplete lessons: Stacks and queues; Linked lists; Recursion from first principles; Trees and traversal; Heaps and priority queues; Graphs and traversal; Backtracking; Dynamic programming. They have ordered titles, empty teaching bodies and `incomplete=true`, and can be authored in-app. No placeholder replaces any of the five required patterns.

## Remaining limits

- Vercel API deployment is Ready and real phone ingestion is verified. Long-term unattended operation, real Google accounts, phone hydration, Android background delivery and complete Samsung Cloud coverage/units remain unverified.
- CSV files intentionally use JSON-encoded cells to preserve exact values. They are designed for lossless restore, not automatic spreadsheet-type guessing.
- Health sum metrics expect nonoverlapping increments. The app cannot deduplicate overlapping readings from *different* sources using a contract that only keys by source and external ID. Select one active source per overlapping metric/window.
- Most reference/admin data use consistent table editors; nested curriculum/mapping/recurrence data use documented JSON fields. Body metrics, grading bands and everyday actions have ordinary labeled controls.
- On-demand reminders catch up when the app is opened; no promise of background delivery while it is closed.

See [INTEGRATIONS.md](INTEGRATIONS.md) for integration limits and the optional Phase 3 path; nothing has been silently removed from the planned scope. Publication results are recorded separately in the task handoff.

## Watch7 / S24 FE setup — 14 September 2026

The receiver has a pinned 37-reading preset for the free HC Webhook v1.9.20 APK. Samsung-only water excludes old manual drinks without deleting them. Incremental missing arrays, source filtering, sleep stages, deterministic legacy identities and 6,001-record retries are tested. Dashboard totals use SQL; history pages stay bounded. The 41-check backend suite includes encrypted Samsung sign-in/replay, resumable raw stress pages, safe error diagnostics, missing-collection isolation and bounded server-revision retries. The watch/water browser checks pass at 375, 768 and 1440 px, and the production React build passes. Swift callback helper compilation passes with a macOS deprecation warning.

The live receiver token, Samsung mapping and Samsung-only water preference were configured through the authenticated API. The private header is delivered outside Git in WATCH_CONNECTION.md. The phone now authenticates. A real request exposed missing distance metadata. The receiver now excludes unverifiable rows and reports them in the response and Watch data status, while saving source-qualified valid records. Invalid qualified records still roll back the whole request. The successful phone delivery at 06:16 UTC saved 9,422 readings, with eight unverifiable distance rows omitted. A following delivery recognized 1,039 duplicates and omitted two distance rows; these omission counts are per delivery, not unique missing-record counts. Readback confirmed steps, heart rate, oxygen saturation, sleep, and awake/deep/light/REM stages. Hydration has not arrived. The owner confirmed that the phone reported success. Samsung sign-in is fixed: bare Samsung hostnames are normalized to HTTPS, with host restrictions preserved. Account, health and cloud credentials work, and actual raw numeric fields have been imported. Samsung reports the catalog stress collection does not exist. Absent collections are recorded and do not stop other imports. Explicit server schema hints are honored with at most two retries per collection/pass; unavailable collections retain full-history retry coverage. No real health data was fabricated for live verification. The private importer excludes unsupported document structures; it does not claim a complete Samsung backup. The identity limits are documented in PHONE_SETUP.md and INTEGRATIONS.md. No paid plan, Android codebase or persistent worker was added.


## ChatGPT connection update

Migration 0003 adds private OAuth state, change receipts, learning topics/sessions and course-linked exams. It passed a fresh empty PostgreSQL migration and an isolated schema-only Neon migration before production. The existing production health-record count was unchanged. The MCP API deployment reports Ready. The full 41-test acceptance suite and production frontend build pass. OAuth PKCE/code replay, refresh rotation/revocation, unauthenticated calls, atomic batches, retries, later-edit-safe undo, CSV round-trip, older backup restoration and journal/insight deletion privacy are covered locally.

The ChatGPT Life OS project exists with project-only memory. Private connector registration and a real ChatGPT tool call are pending verification. **The requested 09:00 Asia/Kolkata cloud brief is not yet scheduled.** The website displays that distinction. Mobile-client support, automatic project tool attachment, scheduling with a private connector and actual real-world timetable imports remain untested. A private GPT Actions fallback has not been activated. No paid model API is used.
