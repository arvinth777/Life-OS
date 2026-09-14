# Vercel Hobby + Neon

Life OS runs as a Python FastAPI function on Vercel Hobby. The existing React frontend stays on Sites; Postgres stays in the owner's Neon Free project. Select Hobby, with no paid add-ons or Pro trial.

Current API: `https://life-os-api-six.vercel.app`. Vercel project: `arvinth777s-projects/life-os-api`, production deployment `dpl_FB3gzu6FkEicQk6eee77LUYMAsoe`, reported Ready. Set `VITE_API_URL=https://life-os-api-six.vercel.app` when rebuilding the frontend. The account remains on Hobby. Existing local owner credentials were reused for the online owner's password hash; no plaintext password was sent to Vercel.

## Setup

1. Follow the README's Python environment setup. Use Python 3.13 and `pip install -r requirements.lock`.
2. Link the Neon project. Store its direct connection as `DATABASE_URL` in the shell for migrations. Keep connection strings and encryption keys out of Git and frontend code.
3. Generate `ENCRYPTION_KEY` and `OWNER_PASSWORD_HASH` as described in the README. Preserve both across redeploys. Test migrations on a temporary Neon branch, then run `alembic upgrade head` and `python -m app.bootstrap` from `backend/` against the production database. Delete the temporary branch afterward. Bootstrap creates the owner only if absent.
4. Sign into Vercel, select a Hobby account, and create a FastAPI project with root directory `backend`. The checked-in `vercel.json` sets the function timeout; `.python-version` pins Python 3.13. Use the CLI (`vercel link`, then `vercel deploy`) or a Git repository that you explicitly authorize for upload.
5. Set encrypted environment variables for the intended deployment environment: `DATABASE_URL` (Neon's **pooled** connection), `ENCRYPTION_KEY`, and `ALLOWED_ORIGINS` (the exact frontend origin). `OWNER_PASSWORD_HASH` is only needed when running bootstrap; normal API requests never create or reset an owner.
6. The deployment needs to allow requests from your frontend and phone webhook. Vercel's separate login protection must not intercept those API requests. Life OS itself requires the owner session token for data access and a separate bearer token for the phone receiver. Keep secrets in Vercel settings, never in a frontend bypass token.
7. Set `VITE_API_URL` to the completed deployment's HTTPS origin, rebuild the frontend and publish it through Sites. Check deployment build status and run the acceptance tests before treating the hosting migration as complete.

Database migration and bootstrap are explicit deployment steps, not function startup work. For later releases, test and run the new Alembic migration before deploying code that requires it.

## Backups under request limits

The Settings backup and restore buttons transfer at most **1 MB per request/response**, avoiding Vercel's 4.5 MB payload limit. The existing ZIP contains every application table in CSV and JSON, including the transfer table and Alembic revision. Downloads capture a consistent snapshot before creating their own transport row.

Revision `0002` adds `backup_transfers`: UUID primary key, owner foreign key, direction, total size, SHA-256, encrypted chunk map, timestamps and indexed expiry. Only the authenticated owner can use the dedicated transfer routes. It is hidden from general data editors. One transfer may be active at a time. The client releases it when finished or cancelled; abandoned transfers expire after one hour and are purged by the next transfer request. A network failure does not partially restore data. Final restore checks completeness and checksum, then replaces the database in one transaction. Revision `0001` JSON and CSV backups remain importable after migration.

The existing browser restore limit remains 25 MB (100 MB expanded archive limit). Downloads larger than 25 MB use the README's CLI export. No paid storage service or background worker is required. The CLI continues to support the full backup format directly.

## Free plan limitations

Vercel Hobby is for personal, non-commercial projects. Usage limits can pause service; cold starts remain possible. Functions have finite execution times. This app's reminders run on requests and its digest endpoint, so it does not require a resident worker. Google polling is still deferred; do not assume a 15-minute scheduler has been configured.

References: [FastAPI deployment](https://vercel.com/docs/frameworks/backend/fastapi), [Hobby](https://vercel.com/docs/plans/hobby), [function limits](https://vercel.com/docs/functions/limitations).
