"""Acceptance checks require a disposable real PostgreSQL database (never production)."""

import io, json, os, uuid, zipfile
import base64, hashlib
from datetime import datetime, date, timedelta, timezone
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from app.db import engine
from app import schema as s
from app.main import app
from app.seed import seed
from app.domain import sm2, streak, next_task_date, calendar_occurrences, nutrition
from app.security import hasher, put_secret, get_secret
from app.backup import export_data, archive, parse_backup, restore, dumps
from app.services import muscle_volume, academic_summary, dashboard
from app.integrations.google import resolve


@pytest.fixture(autouse=True)
def database():
    if not engine.url.database.endswith("_test"):
        pytest.fail("Tests require a database name ending _test")
    os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "TRUNCATE "
            + ", ".join('"' + t.name + '"' for t in s.metadata.sorted_tables)
            + " CASCADE"
        )
    seed()
    with engine.begin() as conn:
        conn.execute(
            sa.insert(s.owners).values(
                username="owner", password_hash=hasher.hash("test-password-only")
            )
        )
    yield


@pytest.fixture
def client():
    c = TestClient(app)
    response = c.post(
        "/api/auth/login", json={"username": "owner", "password": "test-password-only"}
    )
    assert response.status_code == 200, response.text
    c.headers["Authorization"] = "Bearer " + response.json()["token"]
    return c


def create(c, table_name, **data):
    r = c.post("/api/data/" + table_name, json=data)
    assert r.status_code == 200, r.text
    return r.json()


def test_large_chunked_backup_restore_and_legacy_compatibility(client):
    # Incompressible content makes the ZIP exceed the host's 4.5 MB payload cap.
    body = base64.b64encode(os.urandom(1_700_000)).decode()
    with engine.begin() as conn:
        entry_id = conn.execute(
            sa.insert(s.journal_entries)
            .values(title="Large backup", body=body)
            .returning(s.journal_entries.c.id)
        ).scalar_one()
    response = client.post("/api/transfers/download")
    assert response.status_code == 200, response.text
    transfer = response.json()
    assert transfer["size"] > 4_500_000
    assert client.post("/api/transfers/download").status_code == 409
    pieces = []
    engine.dispose()  # no process-local state may be needed to resume
    for i in range(transfer["count"]):
        r = client.get(f'/api/transfers/{transfer["id"]}/chunks/{i}')
        assert r.status_code == 200 and len(r.content) <= 1_000_000
        pieces.append(r.content)
    raw = b"".join(pieces)
    assert hashlib.sha256(raw).hexdigest() == transfer["sha256"]
    data = parse_backup(raw)
    assert set(data["tables"]) == {*s.TABLES, "alembic_version"}
    assert data["tables"]["backup_transfers"] == []
    assert client.delete(f'/api/transfers/{transfer["id"]}').status_code == 200
    with engine.begin() as conn:
        conn.execute(
            sa.update(s.journal_entries)
            .where(s.journal_entries.c.id == entry_id)
            .values(body="After snapshot")
        )
    upload = client.post(
        "/api/transfers/upload",
        json={"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
    ).json()
    path = f'/api/transfers/{upload["id"]}'
    assert client.post(path + "/restore?replace=true").status_code == 422
    with engine.connect() as conn:
        assert (
            conn.execute(
                sa.select(s.journal_entries.c.body).where(
                    s.journal_entries.c.id == entry_id
                )
            ).scalar_one()
            == "After snapshot"
        )
    for i, part in enumerate(pieces):
        assert client.post(path + f"/chunks/{i}", content=part).status_code == 200
    assert client.post(path + "/chunks/0", content=pieces[0]).status_code == 200
    assert (
        client.post(path + "/chunks/0", content=b"x" * len(pieces[0])).status_code
        == 409
    )
    engine.dispose()
    assert client.post(path + "/restore?replace=true").status_code == 200
    with engine.connect() as conn:
        assert (
            conn.execute(
                sa.select(s.journal_entries.c.body).where(
                    s.journal_entries.c.id == entry_id
                )
            ).scalar_one()
            == body
        )
        assert (
            conn.execute(
                sa.select(sa.func.count()).select_from(s.backup_transfers)
            ).scalar()
            == 0
        )
    legacy = dict(
        data,
        schema="0001",
        tables={k: v for k, v in data["tables"].items() if k != "backup_transfers"},
    )
    legacy["tables"]["alembic_version"] = [{"version_num": "0001"}]
    with engine.begin() as conn:
        restore(conn, legacy, replace=True)
    with engine.connect() as conn:
        assert (
            conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            == "0002"
        )


def test_transfer_access_expiry_and_checksum(client):
    assert TestClient(app).post("/api/transfers/download").status_code == 401
    assert client.get("/api/data/backup_transfers").status_code == 404
    r = client.post("/api/transfers/upload", json={"size": 3, "sha256": "0" * 64})
    key = r.json()["id"]
    assert (
        client.post(f"/api/transfers/{key}/chunks/0", content=b"bad").status_code == 200
    )
    assert client.post(f"/api/transfers/{key}/restore?replace=true").status_code == 422
    with engine.begin() as conn:
        conn.execute(
            sa.update(s.backup_transfers).values(
                expires_at=s.now() - timedelta(seconds=1)
            )
        )
    assert client.get(f"/api/transfers/{key}/chunks/0").status_code == 404
    assert client.post("/api/transfers/download").status_code == 200


def test_every_module_persists_after_connection_restart(client):
    c = client
    at = "2026-09-13T08:00:00+00:00"
    journal = create(
        c,
        "journal_entries",
        title="A durable thought",
        body="Persistence matters",
        tags=["reflect"],
    )
    trait = create(c, "traits", name="Patience")
    create(
        c,
        "trait_ratings",
        trait_id=trait["id"],
        score=7,
        recorded_at=at,
        reflection="Paused before responding",
    )
    create(
        c,
        "reflections",
        domain="personality",
        body="A smaller response",
        recorded_at=at,
    )
    term = create(
        c, "terms", name="Term one", starts_on="2026-08-01", ends_on="2026-12-31"
    )
    course = create(c, "courses", term_id=term["id"], name="Algorithms", credits=3)
    create(c, "assignments", course_id=course["id"], title="Practice sheet", due_at=at)
    component = create(
        c, "grade_components", course_id=course["id"], name="Exam", weight=60
    )
    create(
        c,
        "grades",
        component_id=component["id"],
        title="Midterm",
        earned=45,
        possible=50,
    )
    create(c, "goals", domain="academic", title="Understand every week")
    project = create(c, "projects", name="Portfolio", tags=["career"])
    create(
        c,
        "custom_field_definitions",
        entity="work_notes",
        name="Effort",
        field_type="number",
    )
    create(
        c,
        "work_notes",
        project_id=project["id"],
        title="Next step",
        body="Start small",
        custom_fields={"Effort": 2},
    )
    parent = create(
        c,
        "tasks",
        title="Finish project",
        project_id=project["id"],
        due_at=at,
        priority=3,
    )
    create(c, "tasks", title="Write outline", parent_id=parent["id"])
    problem = c.get("/api/data/problems").json()[0]
    create(
        c,
        "problem_attempts",
        problem_id=problem["id"],
        solved=True,
        minutes=14,
        attempted_at=at,
    )
    note = create(
        c,
        "concept_notes",
        title="Recall a boundary",
        front="What is excluded?",
        back="The right boundary",
    )
    assert c.post("/api/reviews/" + note["id"], json={"grade": 5}).status_code == 200
    workout = create(c, "workouts", title="First session", performed_at=at)
    ex = c.get("/api/data/exercises").json()[0]
    create(
        c,
        "workout_sets",
        workout_id=workout["id"],
        exercise_id=ex["id"],
        reps=10,
        weight_kg=5,
        rpe=7,
    )
    assert (
        c.post(
            "/api/ingest",
            json=[
                dict(
                    metric="water",
                    value=250,
                    unit="ml",
                    recorded_at=at,
                    source="manual",
                    device="owner",
                    external_id="one",
                )
            ],
        ).status_code
        == 200
    )
    create(
        c,
        "calendar_events",
        title="Study hour",
        starts_at=at,
        ends_at="2026-09-13T09:00:00+00:00",
    )
    engine.dispose()
    for name in [
        "journal_entries",
        "trait_ratings",
        "reflections",
        "terms",
        "courses",
        "assignments",
        "grades",
        "goals",
        "projects",
        "work_notes",
        "tasks",
        "problem_attempts",
        "concept_notes",
        "reviews",
        "workouts",
        "workout_sets",
        "health_records",
        "calendar_events",
    ]:
        r = c.get("/api/data/" + name)
        assert r.status_code == 200 and len(r.json()) > 0, name
    assert c.get("/api/data/journal_entries?q=durable").json()[0]["id"] == journal["id"]
    assert c.get("/api/dashboard").status_code == 200


def test_sm2_hand_worked_five_reviews_and_reset():
    state = {"ease_factor": 2.5, "repetitions": 0, "interval_days": 0}
    day = date(2026, 1, 1)
    # 5,5,4,3,5: old EF drives intervals 1,6,16,43,110; EF 2.6,2.7,2.7,2.56,2.66.
    for grade, interval, ef in [
        (5, 1, 2.6),
        (5, 6, 2.7),
        (4, 16, 2.7),
        (3, 43, 2.56),
        (5, 110, 2.66),
    ]:
        state = sm2(state, grade, day)
        assert state["interval_days"] == interval
        assert state["ease_factor"] == ef
        assert state["due_on"] == day + timedelta(days=interval)
        day = state["due_on"]
    state = sm2(state, 0, day)
    assert state["repetitions"] == 0 and state["interval_days"] == 1
    for _ in range(10):
        state = sm2(state, 0, day)
    assert state["ease_factor"] == 1.3


def test_three_streaks_timezone_and_skipped_day():
    utc = timezone.utc
    at = datetime(2026, 1, 4, 6, tzinfo=utc)
    # These are three dates in UTC but only two in Los Angeles.
    instants = [
        datetime(2026, 1, 2, 23, tzinfo=utc),
        datetime(2026, 1, 3, 1, tzinfo=utc),
        datetime(2026, 1, 4, 1, tzinfo=utc),
    ]
    for source in ["journal", "attempt", "workout"]:
        assert streak(instants, "UTC", at) == 3
        assert streak(instants, "America/Los_Angeles", at) == 2
        assert streak([instants[0], instants[2]], "UTC", at) == 1
    with engine.begin() as conn:
        from app.services import setting

        for stamp in instants:
            conn.execute(
                sa.insert(s.journal_entries).values(
                    title="entry", body="body", created_at=stamp
                )
            )
            problem = conn.execute(sa.select(s.problems.c.id)).scalar()
            conn.execute(
                sa.insert(s.problem_attempts).values(
                    problem_id=problem, attempted_at=stamp
                )
            )
            conn.execute(
                sa.insert(s.workouts).values(title="session", performed_at=stamp)
            )
        setting(conn, "timezone", "UTC")
        assert set(dashboard(conn, at)["streaks"].values()) == {3}
        setting(conn, "timezone", "America/Los_Angeles")
        assert set(dashboard(conn, at)["streaks"].values()) == {2}


def test_backup_json_csv_roundtrip_every_table_and_atomic_failure(client):
    create(
        client,
        "journal_entries",
        title="Comma, newline",
        body='Line one\n"quoted" ✓',
        tags=["a,b"],
    )
    create(client, "tasks", title="parent")
    with engine.begin() as conn:
        put_secret(conn, "llm_api_key", "private-test-secret")
    with engine.begin() as conn:
        data = export_data(conn)
    raw = archive(data)
    assert b"private-test-secret" not in raw
    csv_only = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as original, zipfile.ZipFile(
        csv_only, "w"
    ) as target:
        for name in original.namelist():
            if name.startswith("csv/") or name == "manifest.json":
                target.writestr(name, original.read(name))
    for variant in [dumps(data).encode(), raw, csv_only.getvalue()]:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "TRUNCATE "
                + ", ".join('"' + t.name + '"' for t in s.metadata.sorted_tables)
                + " CASCADE"
            )
            restore(conn, parse_backup(variant))
        with engine.begin() as conn:
            again = export_data(conn)
        canonical = lambda d: {
            k: sorted(v, key=lambda r: str(r.get("id", "")))
            for k, v in json.loads(dumps(d))["tables"].items()
        }
        assert canonical(data) == canonical(again)
    broken = json.loads(dumps(data))
    broken["tables"]["journal_entries"][0]["id"] = "bad uuid"
    with pytest.raises(ValueError):
        with engine.begin() as conn:
            restore(conn, broken, replace=True)
    with engine.begin() as conn:
        assert len(export_data(conn)["tables"]["journal_entries"]) == 1


def test_ingest_idempotent_atomic_mapped_and_suggestions(client):
    record = dict(
        metric="water",
        value=250,
        unit="ml",
        recorded_at="2026-01-01T01:00:00Z",
        source="manual",
        device="owner",
        external_id="one",
    )
    assert client.post("/api/ingest", json=[record]).json()["accepted"] == 1
    assert client.post("/api/ingest", json=[record]).json()["duplicates"] == 1
    invalid = {**record, "external_id": "bad", "unit": "liters"}
    assert (
        client.post(
            "/api/ingest", json=[{**record, "external_id": "two"}, invalid]
        ).status_code
        == 422
    )
    assert len(client.get("/api/data/health_records").json()) == 1
    with engine.begin() as conn:
        put_secret(conn, "health_webhook_token", "bridge-secret-token")
    payload = {
        "records": [
            {
                **record,
                "source": "bridge",
                "metric": "weight",
                "unit": "kg",
                "value": 72,
                "external_id": "weight1",
            }
        ]
    }
    response = client.post(
        "/api/integrations/health/default",
        json=payload,
        headers={"Authorization": "Bearer bridge-secret-token"},
    )
    assert response.status_code == 200, response.text
    suggestion = client.get("/api/data/metric_suggestions").json()[0]
    cfg = client.get("/api/data/settings").json()
    assert next(x["value"]["weight_kg"] for x in cfg if x["key"] == "body") is None
    assert (
        client.post("/api/suggestions/" + suggestion["id"] + "/accept").status_code
        == 200
    )
    assert (
        next(
            x["value"]["weight_kg"]
            for x in client.get("/api/data/settings").json()
            if x["key"] == "body"
        )
        == 72
    )


def test_body_map_three_groups_and_weighted_grades(client):
    workout = create(client, "workouts", title="Three groups")
    with engine.connect() as conn:
        ex = (
            conn.execute(sa.select(s.exercises).where(s.exercises.c.name == "Push-up"))
            .mappings()
            .one()
        )
    for _ in range(3):
        create(
            client,
            "workout_sets",
            workout_id=workout["id"],
            exercise_id=str(ex["id"]),
            reps=10,
            weight_kg=0,
        )
    volume = client.get("/api/physical/volume?workout_id=" + workout["id"]).json()
    assert {g["map_key"]: g["volume"] for g in volume if g["volume"] > 0} == {
        "chest": 3,
        "shoulders": 1.5,
        "triceps": 1.5,
    }
    term = create(
        client, "terms", name="Term", starts_on="2026-01-01", ends_on="2026-06-01"
    )
    course = create(client, "courses", term_id=term["id"], name="Course", credits=3)
    for name, weight, earned in [("exam", 60, 80), ("assignment", 40, 100)]:
        part = create(
            client, "grade_components", course_id=course["id"], name=name, weight=weight
        )
        create(
            client,
            "grades",
            component_id=part["id"],
            title="result",
            earned=earned,
            possible=100,
        )
    assert client.get("/api/academics/summary").json()["courses"][0]["average"] == 88


def test_recurrence_completion_idempotent_and_dst(client):
    task = create(
        client,
        "tasks",
        title="Daily practice",
        rrule="FREQ=DAILY",
        due_at="2020-01-01T08:00:00Z",
    )
    assert client.post("/api/tasks/" + task["id"] + "/complete").status_code == 200
    assert client.post("/api/tasks/" + task["id"] + "/complete").status_code == 200
    tasks = client.get("/api/data/tasks").json()
    assert len(tasks) == 2
    nxt = next(t for t in tasks if t["previous_id"])
    assert datetime.fromisoformat(nxt["due_at"]) > s.now()
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/New_York")
    anchor = datetime(2026, 3, 7, 9, tzinfo=tz)
    nxt = next_task_date("FREQ=DAILY", anchor, anchor, "America/New_York")
    assert nxt.hour == 9 and nxt.utcoffset() == timedelta(hours=-4)


def test_calendar_recurrence_exception_and_soft_delete(client):
    master = create(
        client,
        "calendar_events",
        title="Daily",
        starts_at="2026-01-01T09:00:00Z",
        ends_at="2026-01-01T10:00:00Z",
        recurrence=["RRULE:FREQ=DAILY;COUNT=3"],
    )
    create(
        client,
        "calendar_events",
        title="Moved",
        starts_at="2026-01-02T11:00:00Z",
        ends_at="2026-01-02T12:00:00Z",
        master_id=master["id"],
        original_start="2026-01-02T09:00:00Z",
    )
    result = client.get(
        "/api/calendar/agenda",
        params={"start": "2026-01-01T00:00:00Z", "end": "2026-01-05T00:00:00Z"},
    )
    assert result.status_code == 200, result.text
    assert (
        len(result.json()) == 3
        and sum(e["title"] == "Moved" for e in result.json()) == 1
    )
    assert len(client.get("/api/data/calendar_events").json()) == 2
    client.delete("/api/data/calendar_events/" + master["id"])
    assert len(client.get("/api/data/calendar_events").json()) == 2


def test_seed_complete_and_idempotent_and_no_integrations(client):
    seed()
    patterns = client.get("/api/data/patterns").json()
    assert len(patterns) == 5
    assert all(
        not p["incomplete"]
        and len(p["explanation"]) > 300
        and len(p["walkthrough"]) >= 3
        for p in patterns
    )
    problems = client.get("/api/data/problems").json()
    assert len(problems) == 15
    assert all(
        len(p["hints"]) == 3
        and p["solution"].startswith("def ")
        and len(p["explanation"]) > 200
        for p in problems
    )
    lessons = client.get("/api/data/lessons").json()
    assert sum(l["incomplete"] for l in lessons) == 8
    assert client.get("/api/integrations/status").json()["llm_configured"] is False
    assert client.post("/api/ai/tutor/" + lessons[0]["id"], json={}).status_code == 409
    for route in [
        "/dashboard",
        "/academics/summary",
        "/dsa/progress",
        "/physical/volume?week=true",
        "/reminders",
        "/schema",
    ]:
        assert client.get("/api" + route).status_code == 200, route


def test_auth_encryption_and_validation(client):
    anonymous = TestClient(app)
    assert anonymous.get("/api/data/journal_entries").status_code == 401
    assert anonymous.get("/api/backup").status_code == 401
    assert client.get("/api/data/secrets").status_code == 404
    assert client.post("/api/data/owners", json={}).status_code == 404
    for _ in range(10):
        assert (
            anonymous.post(
                "/api/auth/login", json={"username": "wrong", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        anonymous.post(
            "/api/auth/login", json={"username": "wrong", "password": "wrong"}
        ).status_code
        == 429
    )
    with engine.begin() as conn:
        put_secret(conn, "llm_api_key", "not-plaintext")
        stored = conn.execute(sa.select(s.secrets.c.ciphertext)).scalar()
        assert (
            "not-plaintext" not in stored
            and get_secret(conn, "llm_api_key") == "not-plaintext"
        )
    trait = create(client, "traits", name="Focus")
    assert (
        client.post(
            "/api/data/trait_ratings", json={"trait_id": trait["id"], "score": 11}
        ).status_code
        == 409
    )


def test_google_tie_rule_and_nutrition():
    stamp = s.now()
    assert resolve({"updated_at": stamp}, {"updated_at": stamp}) == "google"
    assert (
        resolve({"updated_at": stamp + timedelta(seconds=1)}, {"updated_at": stamp})
        == "local"
    )
    assert nutrition(
        {
            "weight_kg": 70,
            "height_cm": 175,
            "age": 25,
            "sex": "male",
            "activity_multiplier": 1.2,
            "goal": "maintain",
            "protein_g_per_kg": {"maintain": 1.6},
        }
    ) == {"configured": True, "bmr": 1674, "maintenance": 2008, "protein_g": 112}


def test_all_fifteen_worked_solutions():
    from app.curriculum import PATTERNS

    examples = [
        [("level",), True, ("",), True],
        [([1, 2, 4, 7, 11], 9), (1, 3), ([], 3), None],
        [([1, 1, 2, 2, 3],), 3, ([],), 0],
        [([2, 1, 5, 1, 3], 3), 9, ([-5, -2, -9], 2), -7],
        [("abba",), 2, ("",), 0],
        [([2, 3, 1, 2, 4, 3], 7), 2, ([1, 1], 5), 0],
        [([3, 1, 4],), [0, 3, 4, 8], ([],), [0]],
        [([3, 1, 4, 2], [(1, 4), (0, 2), (2, 2)]), [7, 4, 0], ([], [(0, 0)]), [0]],
        [([1, -1, 1], 1), 3, ([0, 0], 0), 3],
        [([4, 2, 4, 4],), {4: 3, 2: 1}, ([],), {}],
        [("listen", "silent"), True, ("aab", "abb"), False],
        [([3, 2, 4], 6), (1, 2), ([3, 3], 6), (0, 1)],
        [([1, 3, 3, 6], 3), 1, ([], 4), -1],
        [([1, 3, 5], 4), 2, ([], 1), 0],
        [(20,), 4, (0,), 0],
    ]
    # Only repository-authored seed solutions execute here; app never executes user code.
    for problem, example in zip(
        [p for pattern in PATTERNS for p in pattern["problems"]], examples
    ):
        namespace = {}
        exec(problem["solution"], namespace)
        function = next(v for k, v in namespace.items() if k != "__builtins__")
        assert function(*example[0]) == example[1], problem["title"]
        assert function(*example[2]) == example[3], problem["title"]


def test_nested_stream_mapping_and_invalid_restore(client):
    from app.domain import normalize_body

    payload = {
        "steps": [{"n": 4, "id": "s", "at": 1000}],
        "water": [{"n": 250, "id": "w", "at": 2000}],
    }
    streams = []
    for metric, unit in [("steps", "count"), ("water", "ml")]:
        streams.append(
            {
                "records_path": metric,
                "timestamp_format": "unix_milliseconds",
                "fields": {
                    "metric": {"constant": metric},
                    "value": "n",
                    "external_id": "id",
                    "recorded_at": "at",
                    "source": {"constant": "bridge"},
                    "device": {"constant": "phone"},
                    "unit": {"constant": unit},
                },
            }
        )
    normalized = normalize_body(payload, {"streams": streams})
    assert [r["value"] for r in normalized] == [4, 250]
    assert normalized[0]["recorded_at"] == "1970-01-01T00:00:01+00:00"
    assert (
        client.post("/api/restore?replace=true", content=b"PKbroken").status_code == 422
    )
    assert client.get("/api/data/lessons").status_code == 200
