# Integration boundary and implementation contracts

## Wired now

Manual health entry goes through `POST /api/ingest`, owner JWT authenticated. All records require exactly `metric`, `value`, `unit`, `recorded_at`, `source`, `device`, `external_id`. The entire batch validates before writes; `(source,external_id)` duplicates are ignored. The normalized service owns persistence. No health file-upload adapter exists.

The configurable Health Connect receiver is `POST /api/integrations/health/{mapping_name}`. Use a distinct bearer secret saved as `health_webhook_token`. Default mapping expects `{"records":[normalized_record,...]}`. Select a mapping in Settings → Bridge mapping; nested dot paths, numeric array indices, per-field constants, a record-array path, a numeric value multiplier, and ISO/Unix-second/Unix-millisecond timestamps are supported. Mapping preview does not store data. Different metrics/arrays can use separate named mappings; heterogeneous vendor payloads can use {"streams": [mapping_for_steps, mapping_for_water]} to normalize several arrays in the same request. Each stream uses the same fields shown in the example below. Synthetic payload checks pass. A real S24 FE delivery on 14 September 2026 saved 9,422 readings; a following delivery recognized 1,039 duplicates. Eight distance rows in the first delivery and two in the next lacked source metadata and were omitted. The phone reported success.

### HC Webhook preset

`hc-webhook-samsung` is seeded from `backend/app/data/hc_webhook_v1_9_20.json`. It targets the free v1.9.20 Android release and filters `metadata.data_origin` to Samsung Health. There are 37 mapped readings: steps, sleep and seven sleep stages, exercise/activity and five exercise details, hydration/water, weight, height, heart rate, HRV, resting heart rate, oxygen saturation, respiration, distance, active/total energy, body and skin temperature, body fat, lean/body-water/bone mass, VO₂ max, basal metabolic rate, blood pressure and glucose. Availability is determined by Samsung Health and the phone, not by this list. Nutrition/food is not imported. Use Full/Raw resolution and sleep stages; additive bucket/daily modes lack reliable source metadata or can overlap totals.

New generic mapping options: `optional: true` permits an absent record-array path in incremental requests; `where: {"path": "metadata.data_origin", "equals": "com.sec.android.app.shealth"}` filters origins; and an `external_id` field can use `{"hash_paths": ["metadata.data_origin", "start_time", "end_time"]}`. Hash inputs exclude mutable values and batch timestamps. `children_path` expands sleep stages while retaining parent metadata; `where_all` filters origin plus stage; `first_present` reads raw samples or an available average; `optional_value` skips absent optional exercise details. Each metric has a distinct source namespace. An empty normalized webhook batch returns zero accepted and duplicates. Rows missing a field required by an origin/type filter are excluded and counted in skipped_unverified. They are never assigned a guessed source. Qualified malformed records still reject the whole request atomically. Each accepted attempt stores counts only in integration_runs; Watch data displays the latest attempt and omitted types.

The pinned bridge's JSON does not emit Health Connect IDs. These deterministic identities prevent unchanged records being counted on retry; they are **not** a substitute for native IDs when reconciling edited intervals or deletes. Same-identity corrections remain duplicates (the first saved value stays). Changed interval boundaries can appear new. Prefer native `metadata.id` mappings if a future bridge supplies them, after checking migration of existing identities. No random IDs or full-record hashes are used. Production readback confirmed steps, heart rate, oxygen saturation, sleep, and awake/deep/light/REM stages. Hydration has not arrived; Android background delivery remains unverified. Authenticated 422 errors retain only their validation stage, metric, error type and missing field in integration_runs; request bodies and keys are not retained.

Example for a bridge's steps list:

```json
{
  "records_path": "data.steps",
  "timestamp_format": "unix_milliseconds",
  "fields": {
    "metric": {"constant": "steps"},
    "value": {"path": "count"},
    "unit": {"constant": "count"},
    "recorded_at": {"path": "endTime"},
    "source": {"constant": "phone-health-connect"},
    "device": {"constant": "my-phone"},
    "external_id": {"path": "metadata.id"}
  }
}
```

The example is illustrative, not a claim that all listed bridge versions emit those exact paths. Use the installed bridge's current payload documentation/sample. Missing stable IDs, overlapping cumulative totals, unsupported units and unavailable timestamps need mapping correction; do not invent random IDs for retries. Health readings are interval increments for daily sum metrics. Choose one source for overlapping readings to avoid double-counting manual and bridge data. Health Connect does not guarantee every Samsung-specific metric is available.

Weight and height from a nonmanual source produce suggestion rows when different from Settings. Accepting updates the owner's body configuration; rejecting preserves it. No ingestion route changes body settings silently.

The LLM adapter sends explicit journal-feedback and current-lesson tutor requests to one OpenAI key. It stores per-call provider/model/input/output usage and journal feedback separately. Tutor messages are conversation-local in the browser; only token usage is stored. It never advances through a lesson automatically. Missing configuration produces a clear disabled state. No paid key was provisioned and no live inference request was made during verification.

## Google Calendar: implemented, awaiting real-account authorization

The local calendar remains fully usable without Google. The optional transport in `app/integrations/google.py` is implemented around one owner-designated calendar and never enumerates or syncs every calendar.

- OAuth uses a short-lived state nonce and PKCE. The refresh token is encrypted in `secrets`; credentials come only from `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `PUBLIC_API_URL`.
- Pulls use `singleEvents=false`, `showDeleted=true`, durable page checkpoints, and incremental sync tokens. HTTP 410 clears the invalid cursor and performs a full reconciliation.
- Local and Google edits use content `updated` timestamps. The latest writer wins and Google wins ties. When both versions changed, the conflict log stores both snapshots.
- Creates use deterministic Google-compatible IDs, so retries cannot create duplicate events. Updates and deletes use etag preconditions; HTTP 412 rereads the remote event and resolves it instead of overwriting blindly.
- Deletes propagate in both directions. Local events keep 30-day tombstones, and hard cleanup only removes acknowledged or local-only deletions.
- Recurring series remain master rows with explicit exceptions and original occurrence starts. The integration never expands a whole recurring series into stored instances.
- Poll mode defaults to 15 minutes and catches up during authenticated digest/app requests. Push mode provisions renewable Google notification channels, validates channel/resource/token headers, and then runs the same incremental pull because notifications contain no event body.
- A PostgreSQL advisory lock permits one bounded sync pass at a time. Each page and push acknowledgement commits independently, so a cold start or interrupted request resumes safely.

Automated tests cover incremental paging, token invalidation, equal-timestamp conflict resolution, recurrence exceptions, creates, deletes, OAuth state, and configuration. The remaining verification is an end-to-end run against the owner's real Google OAuth client and designated calendar, including Google-side rate limits and credential expiry. Until that authorization is completed, Settings reports the integration as not connected and local events continue normally.

Official contracts: [incremental sync](https://developers.google.com/workspace/calendar/api/guides/sync), [push notifications](https://developers.google.com/workspace/calendar/api/guides/push).

## Samsung private cloud: connected, partial real-data retrieval verified

The optional client is pinned to `samsung-re-health==0.7.1`. `settings.samsung_cloud` defaults to `{"enabled":false,"interval_minutes":60}`. A successful owner-authorized sign-in enables it. No Samsung password is submitted to Life OS. The adapted MIT-licensed account/session flows keep master credentials, PKCE state, derived health/cloud tokens, failed callbacks eligible for a 15-minute retry, and page cursors encrypted in the existing Postgres `secrets` table using `ENCRYPTION_KEY`. The SDK's plaintext credential files and local SQLite mirror are not used. The MIT attribution is included in `THIRD_PARTY_LICENSES`.

Owner-authenticated endpoints: `POST /api/integrations/samsung/auth/start`, `/auth/finish`, `/auth/retry`, `/pull`, and `/disconnect`. The one-time macOS helper in `scripts/connect-samsung.py` opens Samsung's page and receives its exact callback through a temporary native protocol handler and a nonce-protected loopback server. It holds owner JWT/callback data only in memory, deletes the local nonce/port file at exit, and restores an existing protocol handler. It requires macOS and Xcode Command Line Tools; no Android companion app is added. The sign-in page uses the upstream default country `us`, overridable by `--country`.

Each pull requests at most one 100-document page using GET from Samsung's catalog, with stress tried first. A transaction-level Postgres advisory lock prevents concurrent pulls. Saved records and the encrypted cursor commit together; a later request resumes. The initial pass starts from the earliest server-available data, then subsequent passes overlap the previous completion time by one day. The browser's Import/resume action drives the history pass; app digest requests perform one catch-up page. There is no daemon or guaranteed scheduler while the app is closed. Credentials are never sent to the frontend by read endpoints.

Top-level finite numeric document fields with a stable ID and Unix-millisecond timestamp enter the same normalized ingestion service as `samsung_raw/<collection>/<field>`, source `samsung-cloud`, unit `raw`. Raw values are not summed into the dashboard, treated as health advice, or allowed to overwrite body settings. Their original scales remain unverified. Strings, nested arrays, attachments, encrypted documents requiring another decryption route, documents lacking IDs/timestamps and unavailable collections are not imported by this adapter. This is **not a complete archival copy of Samsung Cloud or a promise to retrieve every Watch7 metric**. Health Connect supplies validated metric/unit mappings separately. Water remains on the Samsung Health hydration mapping until a cloud water field/unit is verified.

Checks cover encrypted sign-in/replay, resumable pages, duplicate raw fields, encrypted backup state and credential-redacted errors. Real Samsung sign-in works after normalizing a bare Samsung callback hostname to HTTPS; all hostname restrictions remain. Actual raw cloud records have been saved. Samsung reports that the catalog stress collection does not exist. HTTP 404 or the exact missing-collection response is marked unavailable and the import continues. Unavailable collections are retried with full history in later passes. Explicit server schema-version hints trigger at most two retries per collection/pass, without skipping the collection. Original scales, complete historical coverage and phone hydration remain unverified. Errors leave saved data usable and do not block the rest of the app. Reconnect if Samsung invalidates the private protocol credentials.

Health history is paged at 200 records (maximum 1,000 via the data endpoint), daily totals use bounded SQL aggregates, and insertion uses 500-record statements. The normalized batch maximum is 25,000, with the host's 4.5 MB input cap usually reached first. Export still includes every row using the existing backup transport. Very large archives use the documented CLI backup/restore path.

## Remaining optional path

Open Wearables is deferred until the phone webhook route demonstrably lacks required coverage. No companion mobile app or backend stack was created. Start that as a separate, version-pinned Android/Kotlin or Flutter codebase; keep the main API independent. An optional MCP connection can retrieve health context but cannot perform LLM inference. Its multi-service recommended deployment is not silently added to the two-deployable free-host architecture.
