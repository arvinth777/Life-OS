# Phone setup — Samsung Health to Life OS

**You can use Life OS fully without doing this.** The receiver is implemented and tested with sample requests. A physical phone connection has not been tested in this session. Complete the hosted Python API setup first: your phone needs its reachable HTTPS address, not your Mac's `localhost` address.

1. **Enable Samsung sharing.** Open Samsung Health → Settings → Data management → Health Connect. Enable synchronization and grant the read/write permissions appropriate to your metrics. Grant **Exercise separately from Steps**. Samsung Health 6.22.5 or later supports this route; menu wording may vary by installed version.

2. **Check Health Connect.** Open Android's Health Connect settings and confirm Samsung Health appears under app permissions. Record a small activity in Samsung Health, then verify it reaches Health Connect. If it does not, changing Life OS will not fix the upstream connection.

3. **Install a bridge.** Choose HC Webhook from the Play Store, or follow the installation instructions in the [mcnaveen/health-connect-webhook repository](https://github.com/mcnaveen/health-connect-webhook). Review its current permissions and source before installing. The user-provided alternative `angeloanan/HealthConnectExports` may also be evaluated; no release or payload compatibility for it was verified here. No custom mobile app is required for this route.

4. **Grant bridge access.** Allow the bridge to read the Health Connect data types you want: steps, water/hydration, sleep and exercise/activity where supported. Enable the bridge's scheduled sync and start with a 15-minute interval. Follow its instructions for Android battery/background restrictions. The [bridge release notes](https://github.com/mcnaveen/health-connect-webhook/releases) document foreground-service and battery-optimization behavior.

5. **Set a separate receiver secret.** In Life OS → Settings → Connections & AI, choose “Health bridge bearer token” and save a long random secret. Use that same value in the bridge's HTTP header: `Authorization: Bearer YOUR_SECRET`. This is separate from your owner password and session.

6. **Set destination and mapping.** Configure HTTP POST and JSON to `https://YOUR-API/api/integrations/health/default`. The `default` mapping expects a `records` array in the normalized shape. Most bridges use their own schema: obtain a sample from the bridge's payload preview/documentation, edit a mapping under Life OS → Settings → Bridge mapping, and use “Preview normalized records.” Point the bridge to the matching name at `/api/integrations/health/NAME`. Map stable Health Connect record IDs into `external_id`, give the bridge a fixed `source`, and ensure time offsets/units match. See [mapping examples](INTEGRATIONS.md). A successful preview does not itself ingest.

7. **Verify once, then repeat.** Send a test sync. Expect an `accepted` count. Send the same records again: they should count as `duplicates`, not create extra entries. Open Physical goals → Health records and check value, unit, source and time. Enter interval increments rather than overlapping daily-total snapshots. Body-weight/height differences appear as suggestions you must accept or reject in the physical overview.

If no records arrive, check bridge permissions, background restrictions, the HTTPS API address, bearer header, and mapping paths. An API returning 401 means the token is wrong; 404 means the mapping name is missing; 422 means the payload does not match the contract. You can keep logging everything by hand while correcting the connection. No health-data file upload is needed or supplied.
