# Integration boundary and implementation contracts

## Wired now

Manual health entry goes through `POST /api/ingest`, owner JWT authenticated. All records require exactly `metric`, `value`, `unit`, `recorded_at`, `source`, `device`, `external_id`. The entire batch validates before writes; `(source,external_id)` duplicates are ignored. The normalized service owns persistence. No health file-upload adapter exists.

The configurable Health Connect receiver is `POST /api/integrations/health/{mapping_name}`. Use a distinct bearer secret saved as `health_webhook_token`. Default mapping expects `{"records":[normalized_record,...]}`. Select a mapping in Settings → Bridge mapping; nested dot paths, numeric array indices, per-field constants, a record-array path, a numeric value multiplier, and ISO/Unix-second/Unix-millisecond timestamps are supported. Mapping preview does not store data. Different metrics/arrays can use separate named mappings; heterogeneous vendor payloads can use {"streams": [mapping_for_steps, mapping_for_water]} to normalize several arrays in the same request. Each stream uses the same fields shown in the example below. Receiver behavior is tested with synthetic payloads; no physical phone has been paired in this session.

### HC Webhook preset

`hc-webhook-samsung` is seeded from `backend/app/data/hc_webhook_v1_9_20.json`. It targets the free v1.9.20 Android release and filters `metadata.data_origin` to Samsung Health. There are 37 mapped readings: steps, sleep and seven sleep stages, exercise/activity and five exercise details, hydration/water, weight, height, heart rate, HRV, resting heart rate, oxygen saturation, respiration, distance, active/total energy, body and skin temperature, body fat, lean/body-water/bone mass, VO₂ max, basal metabolic rate, blood pressure and glucose. Availability is determined by Samsung Health and the phone, not by this list. Nutrition/food is not imported. Use Full/Raw resolution and sleep stages; additive bucket/daily modes lack reliable source metadata or can overlap totals.

New generic mapping options: `optional: true` permits an absent record-array path in incremental requests; `where: {"path": "metadata.data_origin", "equals": "com.sec.android.app.shealth"}` filters origins; and an `external_id` field can use `{"hash_paths": ["metadata.data_origin", "start_time", "end_time"]}`. Hash inputs exclude mutable values and batch timestamps. `children_path` expands sleep stages while retaining parent metadata; `where_all` filters origin plus stage; `first_present` reads raw samples or an available average; `optional_value` skips absent optional exercise details. Each metric has a distinct source namespace. An empty normalized webhook batch returns zero accepted and duplicates. Present malformed records still reject the whole request.

The pinned bridge's JSON does not emit Health Connect IDs. These deterministic identities prevent unchanged records being counted on retry; they are **not** a substitute for native IDs when reconciling edited intervals or deletes. Same-identity corrections remain duplicates (the first saved value stays). Changed interval boundaries can appear new. Prefer native `metadata.id` mappings if a future bridge supplies them, after checking migration of existing identities. No random IDs or full-record hashes are used. The physical phone has not yet passed a real sync check.

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

## Google Calendar: scaffold, not a working integration

The Phase 1 local calendar is complete. Google transport is deliberately **not advertised as connected**. `app/integrations/google.py` contains the tested timestamp winner rule and an explicit not-implemented transport. The schema is ready for the following Phase 2 implementation, without a table rewrite:

1. Owner-triggered OAuth authorization; nonce/state validation; encrypted refresh token; only the designated calendar ID from `google` settings. Never loop over every calendar.
2. Acquire a database advisory lock for one bounded sync pass. Read durable cursor and dirty/tombstone events.
3. Pull with `singleEvents=false`, `showDeleted=true`, no time-window filtering alongside a sync token. Commit each page's events and next page checkpoint together. Promote `nextSyncToken` only when all pages commit.
4. On HTTP 410, clear both cursors and perform a full reconciliation. Preserve dirty local rows until they are compared. Do not treat missing results from a partial page as deletion.
5. Compare content `updated` times. Remote newer or equal wins; local newer wins. Log both full versions when both sides changed. Never let local sync bookkeeping change the content timestamp.
6. Push with deterministic Google-compatible IDs derived from local UUIDs for creates; reuse IDs on retries. Use etag preconditions for updates/deletes. On 412, reread and resolve rather than blind overwrite. Persist each acknowledged event state so interrupted runs resume.
7. Store masters and explicit exceptions, including original start. Never turn occurrence expansion into persisted rows. Test cancelled exceptions and moved instances separately.
8. Soft-delete locally, propagate deletion in both directions, and retain tombstones at least 30 days. Only acknowledged or local-only tombstones may be hard-deleted.
9. Poll mode defaults to 15 minutes on request/digest. Push mode provisions and renews Google notification channels, validates channel/resource/token headers, and invokes the same pull logic because notifications do not contain event bodies. Expired/missed channels fall back to catch-up.
10. Test with a real designated calendar: incremental pages, 410, 412, equal timestamps, retries, remote/local deletion, all-day events, DST, masters and exceptions, rate limits, expired credentials and a process kill after a committed page. Until that passes, this build remains local-calendar only.

Official contracts: [incremental sync](https://developers.google.com/workspace/calendar/api/guides/sync), [push notifications](https://developers.google.com/workspace/calendar/api/guides/push).

## Samsung private cloud: implemented, awaiting real-account verification

The optional client is pinned to `samsung-re-health==0.7.1`. `settings.samsung_cloud` defaults to `{"enabled":false,"interval_minutes":60}`. A successful owner-authorized sign-in enables it. No Samsung password is submitted to Life OS. The adapted MIT-licensed account/session flows keep master credentials, PKCE state, derived health/cloud tokens, failed callbacks eligible for a 15-minute retry, and page cursors encrypted in the existing Postgres `secrets` table using `ENCRYPTION_KEY`. The SDK's plaintext credential files and local SQLite mirror are not used. The MIT attribution is included in `THIRD_PARTY_LICENSES`.

Owner-authenticated endpoints: `POST /api/integrations/samsung/auth/start`, `/auth/finish`, `/auth/retry`, `/pull`, and `/disconnect`. The one-time macOS helper in `scripts/connect-samsung.py` opens Samsung's page and receives its exact callback through a temporary native protocol handler and a nonce-protected loopback server. It holds owner JWT/callback data only in memory, deletes the local nonce/port file at exit, and restores an existing protocol handler. It requires macOS and Xcode Command Line Tools; no Android companion app is added. The sign-in page uses the upstream default country `us`, overridable by `--country`.

Each pull requests at most one 100-document page using GET from Samsung's catalog, with stress tried first. A transaction-level Postgres advisory lock prevents concurrent pulls. Saved records and the encrypted cursor commit together; a later request resumes. The initial pass starts from the earliest server-available data, then subsequent passes overlap the previous completion time by one day. The browser's Import/resume action drives the history pass; app digest requests perform one catch-up page. There is no daemon or guaranteed scheduler while the app is closed. Credentials are never sent to the frontend by read endpoints.

Top-level finite numeric document fields with a stable ID and Unix-millisecond timestamp enter the same normalized ingestion service as `samsung_raw/<collection>/<field>`, source `samsung-cloud`, unit `raw`. Raw values are not summed into the dashboard, treated as health advice, or allowed to overwrite body settings. Their original scales remain unverified. Strings, nested arrays, attachments, encrypted documents requiring another decryption route, documents lacking IDs/timestamps and unavailable collections are not imported by this adapter. This is **not a complete archival copy of Samsung Cloud or a promise to retrieve every Watch7 metric**. Health Connect supplies validated metric/unit mappings separately. Water remains on the Samsung Health hydration mapping until a cloud water field/unit is verified.

Synthetic checks cover the encrypted sign-in exchange, callback replay rejection, resumable pages, duplicate raw stress fields, encrypted backup state and safe failures. Samsung browser sign-in reached completion, but its returned server address was rejected by the private client. Cloud authorization, real field semantics and phone hydration still need to be verified. The encrypted retry route supports investigating this handoff without repeatedly asking for credentials. No server-address validation has been bypassed. Errors leave saved data usable and do not block the rest of the app. Reconnect if Samsung invalidates the private protocol credentials.

Health history is paged at 200 records (maximum 1,000 via the data endpoint), daily totals use bounded SQL aggregates, and insertion uses 500-record statements. The normalized batch maximum is 25,000, with the host's 4.5 MB input cap usually reached first. Export still includes every row using the existing backup transport. Very large archives use the documented CLI backup/restore path.

## Remaining optional path

Open Wearables is deferred until the phone webhook route demonstrably lacks required coverage. No companion mobile app or backend stack was created. Start that as a separate, version-pinned Android/Kotlin or Flutter codebase; keep the main API independent. An optional MCP connection can retrieve health context but cannot perform LLM inference. Its multi-service recommended deployment is not silently added to the two-deployable free-host architecture.
