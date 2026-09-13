# Integration boundary and implementation contracts

## Wired now

Manual health entry goes through `POST /api/ingest`, owner JWT authenticated. All records require exactly `metric`, `value`, `unit`, `recorded_at`, `source`, `device`, `external_id`. The entire batch validates before writes; `(source,external_id)` duplicates are ignored. The normalized service owns persistence. No health file-upload adapter exists.

The configurable Health Connect receiver is `POST /api/integrations/health/{mapping_name}`. Use a distinct bearer secret saved as `health_webhook_token`. Default mapping expects `{"records":[normalized_record,...]}`. Select a mapping in Settings → Bridge mapping; nested dot paths, numeric array indices, per-field constants, a record-array path, a numeric value multiplier, and ISO/Unix-second/Unix-millisecond timestamps are supported. Mapping preview does not store data. Different metrics/arrays can use separate named mappings; heterogeneous vendor payloads can use {"streams": [mapping_for_steps, mapping_for_water]} to normalize several arrays in the same request. Each stream uses the same fields shown in the example below. Receiver behavior is tested with synthetic payloads; no physical phone has been paired in this session.

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

## Phase 3 optional paths

Samsung private-cloud pull is disabled by default. No `samsung-re-health` package is installed or imported. The status function reports disabled/not implemented rather than triggering application errors. Before activation: pin a tested release, isolate its read-only calls, replace plaintext token persistence with encrypted storage, ensure local SQLite is only an ephemeral adapter cache, verify every unit, and bound each request-triggered run. Login constraints and protocol changes must never stop manual navigation or ingestion.

Open Wearables is deferred until the phone webhook route demonstrably lacks required coverage. No companion mobile app or backend stack was created. Start that as a separate, version-pinned Android/Kotlin or Flutter codebase; keep the main API independent. An optional MCP connection can retrieve health context but cannot perform LLM inference. Its multi-service recommended deployment is not silently added to the two-deployable free-host architecture.
