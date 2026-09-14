# Life OS

A single-owner personal workspace: Today, Journal, Personal growth, Academics, Work, DSA in Python, Physical goals, Calendar, and To-do list. Python/FastAPI + SQLAlchemy/Alembic + PostgreSQL + React. No SQLite, worker daemon, social features, or public registration.

Read [PLAN.md](PLAN.md) for the schema, design and risk register; [STATUS.md](docs/STATUS.md) for the exact implemented/deferred/tested boundary; [PHONE_SETUP.md](docs/PHONE_SETUP.md) for the phone bridge; and [INTEGRATIONS.md](docs/INTEGRATIONS.md) for integration contracts.

The selected hosting path is now **Vercel Hobby + Neon Free**, with the frontend on Sites. See [Vercel setup](docs/VERCEL.md) for exact deployment steps and backup transfer limits. The Render instructions below remain an alternative.

## What you need

- Python **3.13** (the pinned wheels were verified on 3.13; do not use 3.14 for this lock).
- Node.js **20.19+** and npm.
- PostgreSQL **16+**, locally for development or a managed connection for production.
- Two terminal windows. No Google, LLM or wearable key is needed for Phase 1.

Postgres is the permanent data store. The Python API reads and writes it. The React frontend is the website you use. They are separate so the API can sleep without losing your entries.

## Fresh-clone local setup

Run from this repository root. On macOS, `brew install python@3.13 postgresql@17 node` installs prerequisites; start Postgres with `brew services start postgresql@17`. On other systems install those same runtimes with your package manager. An already running PostgreSQL service also works.

```sh
createdb life_os
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the generated key into `ENCRYPTION_KEY` in `backend/.env`. Set `DATABASE_URL` to your Postgres connection string; the example uses your local operating-system Postgres username. If Postgres requires a username/password, use `postgresql+psycopg://USER:PASSWORD@HOST:PORT/life_os`. URL-encode special characters in credentials. Leave the other integration fields blank. Set `ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`.

```sh
alembic upgrade head
python -m app.seed
python -m app.cli owner --username owner
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If Homebrew installed PostgreSQL as keg-only, add its tools with `export PATH="$(brew --prefix postgresql@17)/bin:$PATH"` before `createdb`.

The owner command prompts privately for a password of at least 12 characters and refuses to overwrite an existing owner. The seed creates only reference/configuration data, never fabricated personal activity. Re-running seed preserves edits.

In the second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open [the local app](http://127.0.0.1:5173). Sign in with the owner/password you just created. The API address can stay blank locally because Vite proxies `/api` to port 8000. Stop either process with Ctrl+C. Restarting the processes preserves PostgreSQL data.

For the instance built in this task, PostgreSQL uses localhost port **55432** and its data directory is outside this repository under the task's `work/postgres`. The separately delivered `LOCAL_ACCESS.md` contains its generated local login. Those machine-specific files are not included in source or deployments. Use the fresh-clone instructions above on another machine.

## First ten minutes

1. Settings → Preferences: choose timezone and enter known body metrics. Grade bands are empty until you configure your own system.
2. Today: add a task or record 250 ml water. Tasks with due dates appear on Today and Calendar.
3. Journal: save an entry; AI feedback is a separate explicit action.
4. Personal growth: add traits, then record 1–10 ratings. Retire traits rather than deleting their history. Prompt schedule edits each prompt's interval.
5. Academics: add a term → course → weighted grade components → grade records. The average reports how much component weight has received grades.
6. Work: add projects and associated tasks/notes. Define custom fields before adding their values. Career goals/reflections remain separate records.
7. DSA: read the Python primer, then arrays/strings and the five patterns. Expand problems to reveal hints and solutions. Log attempts; save concept notes for reviews.
8. Physical goals: log a workout, then sets. Exercise-to-muscle rows determine weighted-set intensity. Record health readings by hand whenever you like.
9. Calendar: create local events; recurrence accepts RFC 5545 RRULE lines in the advanced event form. Exceptions link to a master and preserve the original occurrence start.
10. Settings → Backup & restore: download your first backup.

A recurring task creates only its own next instance; completed subtasks remain historical. If a subtask itself recurs, its next instance becomes an independent task that can be assigned a new parent. This prevents a future subtask from blocking completion of the current parent.

All entered times use the browser's timezone (identified beside date-time controls) and are saved as instants. Display, streak boundaries, and task recurrence use the configured owner timezone. Date-only fields have no time conversion.

## Environment variables and credentials

| Variable | Required / purpose |
|---|---|
| `DATABASE_URL` | Required PostgreSQL connection. Use TLS (`sslmode=require`) for managed hosts. `postgres://` and `postgresql://` are normalized to psycopg. |
| `ENCRYPTION_KEY` | Required Fernet key generated above. Encrypts integration secrets and derives a domain-separated JWT signing key. Back it up independently; keep the same key across redeploys. |
| `ALLOWED_ORIGINS` | Comma-separated exact frontend origins, no trailing slash. Local examples above; production uses your Sites origin. |
| `SESSION_HOURS` | Optional; default 12. JWTs have issuer/audience/expiry validation and a hashed database record for logout revocation. |
| `OWNER_USERNAME` | Host bootstrap only, default `owner`; ignored once an owner exists. |
| `OWNER_PASSWORD_HASH` | Host bootstrap only; generate an Argon2 hash locally as shown below. Never a plaintext password. Ignored once an owner exists. |
| `PORT` | Host-provided API port, usually automatic. |
| `VITE_API_URL` | Optional frontend build-time API origin. Alternatively set the API connection on the sign-in screen; this stores only its URL locally. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Reserved for Phase 2 OAuth transport. Setting them does **not** activate Google sync in this version. |
| Samsung cloud | No additional environment secret is required. `settings.samsung_cloud.enabled` defaults false; successful Samsung sign-in enables it. All private state uses `ENCRYPTION_KEY`. |
| `OPEN_WEARABLES_URL`, `OPEN_WEARABLES_API_KEY` | Reserved for an optional companion route; not consumed by this Phase 1 build. |

Settings → Connections & AI accepts an LLM provider key, a health bridge bearer token, and a digest trigger token. They are encrypted in `secrets`, never exposed by normal table endpoints. Empty removal revokes the configured secret. The shared inference adapter currently supports OpenAI; the model is editable in advanced `llm` settings. No LLM account/key is bundled and no call runs without an explicit feedback/tutor action. External inference is optional and may have provider charges; the app requires no paid tooling to operate manually.

## Backup and restore

Export is one action: `/api/backup` returns a ZIP with `life-os.json`, a per-table `json/` folder, a per-table `csv/` folder, and `manifest.json`. It covers every application table plus `alembic_version`, including owner hashes, hashed sessions and encrypted credentials. Store backups privately. CSV cells contain JSON-encoded values, preserving nulls, arrays, Unicode, embedded commas and exact types; they are not lossy spreadsheet display exports.

Restore from Settings explicitly replaces the current database in one PostgreSQL transaction and signs you out. Use the owner credentials from the backup afterward. An invalid archive, schema mismatch or foreign-key failure rolls back the entire restore. Encrypted credentials need the original encryption key; JWTs also become invalid if the key changes.

To restore a genuinely empty database (no login yet):

```sh
cd backend
source .venv/bin/activate
alembic upgrade head
python -m app.cli restore /absolute/path/life-os-backup.zip
```

Run migration first but **do not seed or create an owner before an empty restore**. For intentional replacement use `--replace`. A standalone `life-os.json` works too. To exercise CSV restoration, ZIP `csv/` and `manifest.json` without `life-os.json`; the importer then reads the CSV tables. This backup facility is not a health file-ingestion adapter.

## Tests and builds

Use a disposable Postgres database whose name ends in `_test`; the suite truncates it and refuses other names.

```sh
createdb life_os_test
cd backend
source .venv/bin/activate
DATABASE_URL=postgresql+psycopg://localhost/life_os_test alembic upgrade head
DATABASE_URL=postgresql+psycopg://localhost/life_os_test python -m pytest -q
```

The frontend checks require the running local app and its owner password. Set `LIFE_OS_TEST_PASSWORD` in your shell without committing it, then:

```sh
cd frontend
npx playwright install chromium
npx playwright test
npm run build
```

Browser checks create records with a `QA` prefix and remove their tracked records afterward. Use an isolated local database for these checks; do not aim them at production. The tests cover manual forms, all module routes, persistence after page reload, inactive AI, curriculum interaction, body-map highlights, and viewport widths 320, 375, 414, 768 and 1440.

The initial Alembic revision loads an immutable schema snapshot. Future schema edits need a new reviewed migration; changing current metadata alone never changes the database. Run `alembic upgrade head` on each deployment. Production startup runs migrations then idempotent bootstrap before accepting requests.

## Free hosting: two application deployables

The static frontend can run on Sites. The Python API must run on a Python host. Managed Postgres is the datastore, separate from these two application deployables. No production API or database was provisioned by this task. See `docs/STATUS.md` for actual publication state.

**1. Permanent database (Neon).** Create a free Neon project at [Neon](https://neon.com). Create the `life_os` database and copy the standard Postgres connection string with TLS enabled. Set it as the API's `DATABASE_URL`. Do not put this URL into frontend settings. Free plans have quotas; check [current plan details](https://neon.com/pricing).

**2. Generate the two bootstrap values locally.** With the backend virtual environment active:

```sh
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "from argon2 import PasswordHasher; import getpass; print(PasswordHasher().hash(getpass.getpass('Owner password: ')))"
```

The first output is `ENCRYPTION_KEY`; the second is `OWNER_PASSWORD_HASH`. Save them in the host's secret environment settings. Never commit them. Keep the chosen plaintext password in your password manager. Use at least 12 characters.

**3. Python API (Render).** Put this repository in a private Git repository accessible to Render. In Render create a free Python Web Service with root directory `backend`, Python version `3.13.5`, build command `pip install -r requirements.lock`, and start command `alembic upgrade head && python -m app.bootstrap && uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set `DATABASE_URL`, `ENCRYPTION_KEY`, `OWNER_PASSWORD_HASH`, and `ALLOWED_ORIGINS` (your exact Sites origin). Health check is `/api/health`. The included `render.yaml` captures the service configuration. Bootstrap creates only the initial owner if absent, so restarts cannot reset your password. Remove `OWNER_PASSWORD_HASH` from host settings after successful bootstrap if preferred. Render's free service can [sleep after inactivity](https://render.com/docs/free); the next request wakes it. Do not use its ephemeral disk for data.

**4. Frontend (Sites).** Use the privately published frontend from this task, if publication succeeded. In its sign-in screen, expand API connection and enter the HTTPS API origin Render provides. Add that exact Sites origin to `ALLOWED_ORIGINS` on Render. Or set `VITE_API_URL` in `frontend/.env.production`, run `npm ci && npm run build` inside `frontend`, and run `npm run build` from the repository root to stage `frontend/dist` into the root `dist` folder accepted by Sites, then publish through Sites. `.openai/hosting.json` identifies this Site and its static directory. Sites publication must be performed with its connector workflow; a local build alone does not publish.

**5. Verify.** Open `https://YOUR-API/api/health` and expect `{"status":"ok","database":"postgresql"}`. Open the frontend, sign in, add an entry, restart/redeploy the API, and verify the entry remains. Export and restore a backup into a separate empty test database before relying on unattended operation. If a free host requires a payment method or upgrades, stop and select another free Python host using the supplied Dockerfile; no paid upgrade is necessary for manual Life OS functionality.

## Scheduled work

In-app reminders evaluate when the app opens and through authenticated `POST /api/digest`. Configure a long random digest token in Settings if an external scheduler will call it. No scheduler is required: the next app load catches up. No push notifications, email delivery, persistent background worker, or guarantee of work while the app is closed. Google polling and webhook channel transport are Phase 2 work, not simulated schedules.

## Samsung account sign-in for private fields

The phone bridge is configured separately using [PHONE_SETUP.md](docs/PHONE_SETUP.md). To connect Samsung Cloud for its additional raw numeric fields on macOS, install Xcode Command Line Tools if absent, then run from the repository root:

```bash
backend/.venv/bin/python scripts/connect-samsung.py --api https://YOUR_API_HOST
```

Enter your Life OS owner password at the private terminal prompt, then sign in on Samsung's page. Do not paste Samsung callback URLs, passwords, or tokens into chat. `--country` changes the Samsung page's two-letter country (the upstream default is `us`). The script creates a small native callback helper beside the checkout, waits up to 15 minutes, deletes its temporary session file, and signs out its temporary Life OS session. It does not run continuously. Linux/Windows callback helpers are not supplied in this version.

After success, open Physical goals → Watch data → Import / resume Samsung history. Pause and resume between batches; later app loads run bounded catch-up work. Settings → Connections & AI can disconnect the Samsung account without deleting imported readings. The private protocol may stop working; unknown fields stay labeled raw, and a successful sign-in alone does not verify metric coverage. See [INTEGRATIONS.md](docs/INTEGRATIONS.md) for exact exclusions and limits.
