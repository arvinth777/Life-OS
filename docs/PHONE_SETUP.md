# Phone setup — Galaxy Watch7 + Galaxy S24 FE

Life OS is ready to receive Samsung Health readings. The phone permissions and a first real sync still need to be completed. No purchase or watch app is required.

1. **Check Samsung Health.** Open it on the S24 FE and confirm recent Watch7 readings appear. Enable Settings → Sync with Samsung Cloud for the separate stress import.
2. **Enable Health Connect.** Samsung Health → Settings → Data management → Health Connect. Allow Samsung Health to write the available data you want. Exercise needs its own permission. Allow hydration/water if offered. Menu wording varies by Android/Samsung Health version.
3. **Install the free bridge.** On the phone, open the [HC Webhook v1.9.20 release](https://github.com/mcnaveen/health-connect-webhook/releases/tag/v1.9.20) and download **app-foss-release.apk** from Assets. Use this free GitHub build; the Play Store edition is paid. Android may ask to allow this browser to install the APK.
4. **Grant bridge access.** In HC Webhook, grant Health Connect read permissions. Enable the available types: steps, sleep, exercise, heart rate, HRV, resting heart rate, oxygen, respiration, distance, activity energy, temperatures, hydration and body measurements. The receiver also supports blood pressure, glucose and VO₂ max when another supported measurement supplies them; listing a type does not mean the Watch7 measures it. Nutrition/food records are not mapped. Enable background and older-history access if offered.
5. **Choose Full / Raw resolution.** Use unaggregated data, particularly for steps, distance and calories; daily/bucket summaries omit source metadata or overlap existing totals. Choose sleep **with stages**. Start with a short range (one hour, or a night for sleep). Large full-resolution histories must be sent in smaller date ranges; keep each request below 4.5 MB and 25,000 normalized readings. One-minute heart-rate summaries are supported but do not preserve every sample.
6. **Add the destination.** Choose **JSON / POST**, and copy the URL and the `Authorization` header from the private **WATCH_CONNECTION.md** delivered alongside the source. Use the bridge token there, not your owner password.

   `https://life-os-api-six.vercel.app/api/integrations/health/hc-webhook-samsung`

7. **Test and schedule.** Tap **Sync Now**, then view the webhook log. HTTP 200 with an accepted count means the receiver saved readings. Compare Life OS → Physical goals → Watch data / Health records with Samsung Health. Repeat the same sync; unchanged readings should not be added again. Then enable **15-minute** syncing. Android may delay it; this is periodic delivery, not a continuous watch connection. Import older history with successive short date ranges within the access Health Connect grants.

**Water:** Life OS is set to **Samsung Health only**. Log drinks in Samsung Health. Life OS refreshes the received amount without adding a second drink. Confirm one test drink appears: Samsung's hydration export must be verified on your phone and is not guaranteed by the existence of the mapping. Old manual records are kept but excluded from this water total.

**Stress:** Health Connect/this bridge does not supply Samsung stress. Complete Samsung sign-in using the included Mac helper, then use **Physical goals → Watch data → Import / resume Samsung history**. It reads cloud data in resumable batches. Private numeric fields are labeled raw until their meaning/units are verified; a raw stress number is not yet a validated Samsung stress score.

**Troubleshooting:** 401 = wrong/missing bearer header; 404 = mapping missing; 413 = shorten the date range; 422 = incompatible record, inspect the bridge log. Zero accepted can mean no new Samsung-origin records, missing permissions, or aggregation removing origin information. If background delivery stops, check the bridge's battery settings. The preset accepts only `com.sec.android.app.shealth` origins.

**Identity limit:** This bridge's JSON omits native record IDs. Repeatable identities use origin and record times. Same-identity edits keep the first saved value; changed time boundaries and deletes cannot be reliably reconciled. Verify initial totals before relying on them.

Sources: [pinned usage guide](https://github.com/mcnaveen/health-connect-webhook/blob/v1.9.20/docs/usage.md), [JSON implementation](https://github.com/mcnaveen/health-connect-webhook/blob/v1.9.20/app/src/main/java/com/hcwebhook/app/SyncManager.kt), [Samsung cloud client](https://github.com/charlesbel/samsung-re-health). Checked 14 September 2026.
