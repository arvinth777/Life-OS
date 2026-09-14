# ChatGPT connection — implementation plan

Life OS is the durable record; ChatGPT remains the place to talk, learn and reflect.
The private ChatGPT Life OS project opts in to relevant tracking. Other chats need an explicit Life OS invocation. Project instructions are behavioral guidance, not a technical guarantee that an app is attached to every chat.

- Keep the existing FastAPI API and managed Postgres; use the official Python MCP SDK with stateless HTTP, suitable for a cold-starting host.
- Authenticate the private connector using owner-approved OAuth with PKCE, separate scopes, expiring access tokens, refresh rotation and revocation. Encrypt OAuth state; never reuse the phone connection key.
- Expose bounded context and search, a morning-brief data tool, and validated, idempotent changes. Reuse task completion and concept review rules.
- Save journal summaries with AI insights clearly separated; never save whole conversations automatically.
- Add learning topics and dated sessions linked to courses/patterns/tasks. Evidence distinguishes studying, practice and demonstrated understanding; unknown duration stays unknown.
- Store exams as course-linked calendar events. Use stable identifiers to avoid repeated imports; ask when timetable dates are ambiguous.
- Record assistant batches and receipts. Support guarded undo for 30 days, refusing to overwrite subsequent changes.
- Keep learning progress prominent in the existing DSA module, retaining the curriculum. Keep connection and change history in Settings.
- Add forward Alembic migrations; preserve restoration of older backups and export every new table.
- Configure a cloud ChatGPT morning brief for 09:00 Asia/Kolkata only after a real connected read succeeds. No paid model API or always-on local computer is required by the design.

## External dependencies and fallbacks

| Dependency | Failure | Fallback |
| --- | --- | --- |
| Private ChatGPT MCP availability | Connector cannot attach in the desired chat/project or mobile client | Verify actual account support; private GPT Actions uses the same typed operations where available, with limitations stated |
| ChatGPT cloud scheduled tasks | Cannot run the connector or in project-only memory | Keep on-demand brief usable; explicitly report the scheduling limitation rather than claim automation |
| Vercel Hobby / Neon Free | Cold start, limits, outage | Bounded stateless requests, durable retries; existing manual app and backups |
| Phone Health Connect bridge | Delayed or absent readings | Brief reports timestamps/missing metrics; phone is only the watch-data relay |
| Google Calendar | Connection not configured | Use events already stored in Life OS; do not claim Google is synced |

## Verification gates

1. Migrations from empty, old backup compatibility, and regression tests.
2. OAuth code replay, PKCE, token rotation/revocation and unauthorized calls.
3. Atomic updates, duplicate requests, later-edit-safe undo and domain constraints.
4. Live ChatGPT read and reversible write through the private connector.
5. A visible, active daily schedule at 09:00 Asia/Kolkata using the verified connection.

## Setup status

The private ChatGPT project has been created with project-only memory and instructions. The MCP implementation is deployed to the existing Vercel API, which reports Ready. Migration 0003 was verified from empty local PostgreSQL and on a schema-only Neon branch before production; the production health-record count was unchanged. The original 30 tests plus six assistant tests pass. The website build passes. Account-level connector registration, a live ChatGPT read/write and the cloud morning schedule are still being verified. Creating a project or saving a time preference does not activate syncing or scheduling.
