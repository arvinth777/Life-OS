# Life OS — implementation plan

Written before application code, 13 September 2026.

## Environment and delivery boundary

This session can browse, execute Python/JavaScript, run a real local PostgreSQL server, and access Sites publishing tools. Sites hosts static React, but cannot host this FastAPI application. Production therefore needs a separately configured Python API host and managed PostgreSQL connection. No production database or Python-host credentials have been provided. Build and verify locally; publish the static client if Sites permits, explicitly label any missing API connection, and include exact deployment instructions. A frontend-only deployment is not a completed live Phase 1 app.

## Stack and operating model

- Python 3.11+, FastAPI, SQLAlchemy 2, psycopg 3, Alembic: ordinary synchronous transactions, constrained relational schema, versioned migrations from the first source revision.
- React, TypeScript, Vite: static frontend; no server-side JavaScript deployment or frontend database.
- PostgreSQL for development, tests, and managed production (Neon free plan recommended); never SQLite for application storage.
- Render free Python web service plus Sites static frontend: at most two application deployables. Database is the managed datastore. Render can sleep after inactivity; show a retryable connection state and use request-triggered work. No worker, cron daemon, paid tier, or required integration.
- One owner created by an explicit initialization command; Argon2 password hash, signed HS256 JWT bearer session with explicit issuer/audience/expiry, plus a server-side token hash for revocation. Browser keeps session only in sessionStorage. No signup or additional users. Bearer auth avoids cross-site third-party-cookie blocking between Sites and Render.
- Fernet authenticated encryption with ENCRYPTION_KEY for LLM keys and OAuth credentials; only ciphertext in database/backups. Preserve encryption key separately to restore encrypted credentials.
- All times stored as timezone-aware UTC instants; civil-date configuration and recurrence use the owner's IANA timezone. PostgreSQL transactions enforce atomic ingestion, task completion, reviews, and imports.

## Visual and navigation decisions

- Audience: the single owner; primary use: deciding what to do today and recording progress; tone: utilitarian and calm.
- Genre: modern minimal; Hallmark theme: Cobalt; composition: an adapted Workbench that opens on the live app.
- Desktop navigation: persistent left rail grouped into Today, Reflect, Learn & work, and Life; Settings anchored at the bottom.
- Mobile navigation: compact horizontally scrollable labeled navigation, with content below and no hidden modules.
- Hierarchy: page title and one primary action, contextual summary, then saved records and focused forms.
- Today: task list and agenda dominate; water, steps, and three query-derived streaks remain compact.
- Typography: system sans for body, locally available geometric-style fallbacks for headings, system monospace for Python; no runtime font service.
- Palette: cool near-white canvas, dark ink, cobalt for active controls, restrained semantic colors for outcomes.
- Editing: dedicated forms with labeled controls and reference selectors; secondary data types use a consistent table editor.
- DSA: ordered learning outline beside a reading surface; progressive hints, inspectable Python solutions, and interactive walkthrough steps.
- Physical: front/back functional SVG muscle diagram accompanied by a numeric legend; no decorative imagery.
- Empty states: real empty data with a direct entry action; seed only curriculum, configuration, prompts, and exercise reference data.

## Database schema

Every table below has `id UUID PRIMARY KEY`, `created_at timestamptz NOT NULL`, and `updated_at timestamptz NOT NULL` unless noted. All foreign keys are indexed. JSONB columns default to empty objects/arrays as appropriate. Required domain fields are NOT NULL. Mutable entity creation and edits use server timestamps. Relationship deletion is restricted unless explicitly described. Data tables support authenticated CRUD, except security/system records which are managed by dedicated endpoints.

| Table | Additional columns, relationships, constraints and indexes |
|---|---|
| owners | username text UNIQUE, password_hash text, singleton boolean UNIQUE CHECK true |
| sessions | owner_id FK owners CASCADE, token_hash text UNIQUE, expires_at timestamptz indexed |
| settings | key text UNIQUE, value JSONB; timezone, body metrics, grading/GPA, sync mode, thresholds, reflection schedule, streak definitions |
| secrets | name text UNIQUE, ciphertext text; never returned through normal settings reads |
| journal_entries | title text, body text, tags JSONB; GIN to_tsvector('english',title + body) full-text index |
| ai_feedback | entry_id FK journal_entries CASCADE, body text, provider text; timestamp independent of journal |
| traits | name text UNIQUE, retired boolean |
| trait_ratings | trait_id FK traits, score integer CHECK 1..10, recorded_at timestamptz indexed, reflection text |
| reflection_prompts | title text, body text, interval_days integer CHECK >0, enabled boolean |
| reflections | prompt_id nullable FK reflection_prompts, domain text, body text, recorded_at timestamptz |
| terms | name text, starts_on date, ends_on date |
| courses | term_id FK terms, name text, credits numeric CHECK >0 |
| assignments | course_id FK courses, title text, due_at timestamptz indexed, status text, notes text |
| grade_components | course_id FK courses, name text, weight numeric CHECK >0 |
| grades | component_id FK grade_components, title text, earned numeric CHECK >=0, possible numeric CHECK >0 |
| goals | domain text, title text, target_date nullable date, status text, notes text |
| projects | name text, deadline nullable timestamptz, status text, notes text, tags JSONB, custom_fields JSONB |
| custom_field_definitions | entity text, name text, field_type text, options JSONB; UNIQUE(entity,name) |
| work_notes | project_id nullable FK projects, title text, body text, tags JSONB, custom_fields JSONB |
| tasks | title text, notes text, due_at nullable timestamptz indexed, priority integer CHECK 1..4, status text, parent_id nullable self-FK, project_id nullable FK projects, rrule nullable text, recurrence_anchor nullable timestamptz, series_id UUID, previous_id nullable self-FK UNIQUE, completed_at nullable timestamptz, tags JSONB, custom_fields JSONB |
| curriculum_modules | title text, position integer, description text |
| lessons | module_id FK curriculum_modules, title text, position integer, body text, incomplete boolean |
| patterns | lesson_id FK lessons, title text, position integer, explanation text, walkthrough JSONB, incomplete boolean |
| problems | pattern_id FK patterns, title text, position integer, difficulty text, statement text, hints JSONB, solution text, explanation text |
| problem_attempts | problem_id FK problems, solved boolean, minutes numeric CHECK >=0, notes text, attempted_at timestamptz indexed |
| concept_notes | pattern_id nullable FK patterns, title text, front text, back text, ease_factor numeric default 2.5 CHECK >=1.3, repetitions integer default 0, interval_days integer default 0, due_on date indexed |
| reviews | note_id FK concept_notes CASCADE, grade integer CHECK 0..5, reviewed_at timestamptz indexed, previous_state JSONB, next_state JSONB |
| health_records | metric text, value numeric, unit text, recorded_at timestamptz indexed, source text, device text, external_id text; UNIQUE(source,external_id); index(metric,recorded_at) |
| ingestion_mappings | name text UNIQUE, enabled boolean, mapping JSONB; record path, per-field paths/constants, explicit time units and value multipliers |
| metric_suggestions | record_id FK health_records, setting_key text, proposed_value JSONB, status text; UNIQUE(record_id,setting_key) |
| muscle_groups | name text UNIQUE, map_key text UNIQUE, view text |
| exercises | name text UNIQUE, instructions text |
| exercise_muscles | exercise_id FK exercises CASCADE, muscle_id FK muscle_groups, contribution numeric CHECK >0 and <=1; UNIQUE(exercise_id,muscle_id) |
| workouts | title text, performed_at timestamptz indexed, notes text |
| workout_sets | workout_id FK workouts CASCADE, exercise_id FK exercises, reps integer CHECK >0, weight_kg numeric CHECK >=0, rpe nullable numeric CHECK 1..10 |
| calendar_events | title text, description text, starts_at timestamptz, ends_at timestamptz CHECK >start, all_day boolean, timezone text, recurrence JSONB, master_id nullable self-FK, original_start nullable timestamptz, google_event_id nullable text UNIQUE, etag nullable text, sync_state text, deleted_at nullable timestamptz; index(starts_at,deleted_at) |
| calendar_sync | calendar_id text UNIQUE, sync_token nullable text, page_token nullable text, channel_id nullable text, channel_resource_id nullable text, channel_expires_at nullable timestamptz, last_synced_at nullable timestamptz, pending boolean, last_error nullable text |
| sync_conflicts | event_id nullable FK calendar_events SET NULL, local_version JSONB, remote_version JSONB, winner text |
| reminder_rules | kind text, title text, config JSONB, enabled boolean |
| reminder_dismissals | rule_id FK reminder_rules CASCADE, occurrence_key text, dismissed_at timestamptz; UNIQUE(rule_id,occurrence_key) |
| ai_usage | feature text, provider text, model text, input_tokens integer, output_tokens integer |
| integration_runs | provider text, status text, detail text, cursor JSONB |
| auth_attempts | fingerprint text UNIQUE, failures integer, window_started_at timestamptz |

Alembic owns schema creation; startup never substitutes `create_all` for migrations. Initial migration contains an immutable schema snapshot. Later changes are additive, reviewed revision files with upgrade/downgrade paths. Seed is idempotent and does not overwrite user edits. UUIDs permit ordered, lossless backup restoration. JSON and CSV ZIP exports include every table, including Alembic revision and encrypted security rows. Restore validates format, exact schema revision, columns, constraints and foreign keys in one transaction; incompatible backups fail without partial writes. Restore requires owner authentication or the local CLI for a genuinely empty database. Import is a backup-restoration operation, not a health file adapter.

## Health ingestion

`POST /api/ingest` accepts normalized records and is the sole persistence path for health readings; manual UI calls it under owner authentication. `(source, external_id)` uniqueness makes retries idempotent. A dedicated service is shared by adapters, so no adapter bypasses validation. Times require offsets; numeric values must be finite; known units are validated. Settings body metrics remain authoritative. Nonmanual body weight/height differences create accept/reject suggestions, never overwrite settings.

Phase 2 `POST /api/integrations/health/{mapping}` authenticates a separately provisioned bearer secret, enforces bounded payloads, extracts records from a configured JSON path and maps nested keys to normalized fields. Missing IDs, unknown units, malformed timestamps and partial malformed batches fail atomically with actionable errors. Settings offers editable JSON mapping and a sample preview. No manual health file-upload route.

Phase 3 Samsung adapter stays disabled behind an environment flag. Treat the beta client as an isolated read-only source. Do not install it by default or persist its plaintext token/SQLite cache on the API disk; implementation requires an encrypted token/cache adaptation and verified unit map. Catch all adapter exceptions into integration status. Open Wearables remains a separately version-pinned companion-mobile project only if webhook coverage is insufficient. Main schema and manual workflows are independent of both.

## Calendar synchronization

Phase 1 provides local CRUD, recurring masters/exceptions and an agenda merging due tasks and assignments. Store masters and explicit exceptions; expand occurrences only in response memory within a bounded date window. Task recurrence completes atomically and creates at most one next instance after completion time; no future backlog.

Phase 2 scaffolding reserves one configured Google calendar, encrypted refresh credentials and a sync cursor. OAuth uses state and least necessary calendar event scope. Pull uses `singleEvents=false`, `showDeleted=true`, persisted page checkpoints, and a final sync token only after the last committed page. HTTP 410 clears cursors and starts full reconciliation without removing pending local changes. Push uses deterministic Google IDs for newly created local events, etags/conditional writes, and resumable per-event state. Compare local and Google `updated` instants; latest wins, Google wins exact ties; log both full versions for every competing change. Do not use sync bookkeeping timestamps as user-change timestamps. Local deletes create 30-day tombstones; hard removal only after remote acknowledgement or local-only status. Master/exception links preserve recurrence identity. Interval polling defaults to 15 minutes, evaluated on app load or authenticated digest trigger. Optional Google notification endpoint validates channel identity and schedules the same bounded sync pass; renew expiring channels on requests. No persistent worker. Live OAuth/Google sync is explicitly deferred until configured and verified; local Calendar remains fully functional.

## Derived behavior

- Streaks query distinct local dates from journal creation, attempts/reviews, and workout performance. The editable config selects journal, attempt, review and workout qualifying sources; today may be pending, but a missed yesterday breaks the current streak. Timezone changes recalculate all dates.
- SM-2: grade <3 resets repetitions to zero and interval to one day; successful intervals are 1, 6, then nearest integer(previous interval × previous ease). Update ease with `max(1.3, EF + 0.1 - (5-q)*(0.08+(5-q)*0.02))` after interval calculation. Save before/after state per review.
- Course grade: weighted component earned/possible percentages, normalized across graded component weights with explicit coverage. Term average uses course credits. User edits grade bands and GPA aggregation (credit-weighted or equal-course); no national scale assumed.
- Training intensity: sum exercise-muscle contribution per logged set for selected workout/week; numeric legend explains the map. Mifflin–St Jeor BMR uses user-entered mass, height, age and sex constant; activity and configurable goal protein g/kg derive targets. No food/calorie logging.
- AI: explicit journal feedback and current-lesson tutor requests only, shared provider adapter, encrypted key, stored usage; no key means disabled controls. No inference through MCP.
- Reminders: rules for water, due tasks, and journal evaluated on load/digest; dismissals keyed by local day/occurrence. Reflection prompts have configurable intervals.

## Build sequence and checkpoints

1. Plan, repository, immutable migration, constrained schema, owner/session auth and settings.
2. Shared validated CRUD, navigation, backup export/import and idempotent reference seeds.
3. Journal/personality, academics/work/tasks/calendar, health/workouts and derived dashboard.
4. Fully written DSA primer/foundations/five patterns/15 problems, authoring, progress and SM-2.
5. Automated acceptance tests against real PostgreSQL; restart/readback and empty-to-current migration; inspect desktop/mobile UI.
6. Phase 2 configurable webhook and optional LLM adapter; Google state/schema/contract scaffolding. Declare live integration verification gaps.
7. Phase 3 disabled adapters and companion decision record; setup/deployment/phone docs and status report.
8. Publish static frontend if available; report actual deployed state, local running state and missing host provisioning separately.

## Risk register

| Dependency | Failure impact | Fallback / mitigation |
|---|---|---|
| Managed Postgres / Neon free quotas | All durable reads/writes unavailable | Retryable offline state; local PostgreSQL for development; full JSON/CSV backups; migrate standard Postgres URL. Never silently fall back to browser/SQLite storage. |
| Python host / Render free cold starts and quotas | Delayed or unavailable API | User-visible retry, bounded requests, on-load catch-up, no daemon; documented alternate Python host using same container. |
| Sites connector / static hosting | Frontend publication unavailable | Vite build artifacts and exact static-host deployment instructions; backend unaffected. |
| npm / PyPI registries | Fresh installation fails | Lock dependencies, retry when registry available; no runtime package downloads. |
| Browser network / storage | Cannot reach API / session lost | Reload and log in; database remains source of truth. |
| Encryption key loss | Encrypted API/OAuth credentials cannot be decrypted | Separate offline key backup; reauthorize providers; manual features unaffected. |
| Owner password / session compromise | Unauthorized personal-data access | Argon2, short-lived hashed sessions, rate limiting, TLS, explicit logout, no public signup. |
| Google OAuth consent/token revocation | Calendar sync stops | Local calendar continues; clear reconnect status and preserved dirty events. |
| Google quota, etag races, invalid sync token | Delayed/conflicting sync | Backoff, logged versions, idempotent retries, full resync on 410, Google-wins-ties contract. |
| Google notification channel expiration / sleeping API | Missed immediate notifications | Polling catch-up, renewal on requests, explicit last-sync state. |
| External digest scheduler | No evaluation while app closed | Evaluate on next app load; no promise of background delivery. |
| Samsung Health / Health Connect permissions | Live health data absent | Manual entry always available; phone guide includes separate Exercise permission. |
| Phone bridge app background restrictions/payload drift | Delayed or rejected webhooks | Editable mapping, visible last ingestion, idempotent retry, manual entry. |
| samsung-re-health private protocol, units and unsafe token storage | Optional Samsung-specific data unavailable | Off by default, not imported at startup, isolated failure; manual stress/HRV/body composition. |
| Open Wearables pre-1.0 and mobile toolchain | Companion route costly or incompatible | Deferred separate codebase, version pin before implementation, webhook/manual primary path. |
| LLM provider/key/quota/network | Feedback/tutor unavailable | Explicit disabled/error state; all stored content and non-AI learning usable. Provider inference may incur charges; no calls without owner action. |
| Timezone database / DST | Ambiguous civil time/recurrence | Require IANA zone and offset-aware timestamps; date-boundary and DST tests. |
| Malformed backup / old schema | Restore fails | Versioned strict validation and atomic rollback; migrate compatible version before restore. |

Sources checked: [Render free services](https://render.com/docs/free), [Neon pricing](https://neon.com/pricing), [Google incremental sync](https://developers.google.com/workspace/calendar/api/guides/sync), [Google push notifications](https://developers.google.com/workspace/calendar/api/guides/push). Free tiers and availability can change; no paid service is activated by this repository.
# Hosting update — Vercel Hobby

The Python API is prepared for Vercel Hobby; the React frontend stays on Sites and the data stays in Neon Free. This changes deployment configuration, not module contracts. See `docs/VERCEL.md` for setup, limits and verification.

Migration `0002` adds the `backup_transfers` table with UUID primary key; owner foreign key with cascading deletion; direction constrained to upload/download; size constrained to 1–25,000,000 bytes; SHA-256 checksum; encrypted JSON chunk map; creation/update/expiry timestamps; and indexes on owner and timestamps. It is included in the full CSV/JSON backup schema and accessed only through owner-authenticated transfer endpoints. One active transfer is permitted at a time. The download captures every table before creating its own transport row. Chunk size is 1 MB. Abandoned transfers expire after one hour and are removed on the next transfer request. Restore validates the assembled archive and applies it in one transaction. Revision 0001 archives remain compatible.

Additional dependency risk: Vercel enforces payload, execution-time and monthly usage limits. Small chunk requests address the payload limit, while bounded synchronous actions retain the existing request-driven architecture. Free-limit exhaustion can pause service; the documented Render alternative and local setup remain available. No paid plan, persistent worker or additional storage provider is introduced.

## September 14 visual refresh

The pixel/voxel design audit, one-line decisions, motion behavior, and verification are documented in [Design refresh](docs/DESIGN_REFRESH.md). Module contracts, data semantics, and the free hosting architecture are unchanged.

## Purpose-led placement revision

The owner requested removing water from Home and tying animation to actions. [Purpose-led design](docs/INTENTIONAL_DESIGN.md) records the placement rationale for all nine modules, hydration behavior, and verification. It supersedes the original dashboard placement of water and steps.
