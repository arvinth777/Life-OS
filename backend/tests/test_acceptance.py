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


def test_bridge_validation_diagnostics_do_not_store_payload_or_key(client):
    token = "private-phone-secret"
    client.post("/api/secrets/health_webhook_token", json={"value": token})
    endpoint = "/api/integrations/health/hc-webhook-samsung"
    payload = {"steps": [{"count": 12, "start_time": "2026-09-14T01:00:00Z", "private_note": "private-health-content", "metadata": {"data_origin": "com.sec.android.app.shealth"}}]}
    assert client.post(endpoint, json=payload).status_code == 401
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(s.integration_runs)).scalar_one() == 0
    headers = {"Authorization": "Bearer " + token}
    result = client.post(endpoint, headers=headers, json=payload)
    assert result.status_code == 422
    malformed = client.post(endpoint, headers={**headers, "Content-Type": "application/json"}, content='{"private-health-content":')
    assert malformed.status_code == 422
    with engine.connect() as conn:
        entries = conn.execute(sa.select(s.integration_runs)).mappings().all()
    assert len(entries) == 2
    mapping = next(row["cursor"] for row in entries if row["cursor"]["stage"] == "mapping")
    assert mapping == {"stage": "mapping", "metric": "steps", "error_type": "KeyError", "missing_field": "end_time"}
    assert any(row["cursor"].get("error_types") == ["json_invalid"] for row in entries)
    diagnostic = json.dumps([dict(row) for row in entries], default=str)
    assert token not in diagnostic and "private-health-content" not in diagnostic


def test_bridge_saves_verified_readings_and_reports_unverified_ones(client):
    token = "partial-phone-test"
    client.post("/api/secrets/health_webhook_token", json={"value": token})
    headers = {"Authorization": "Bearer " + token}
    endpoint = "/api/integrations/health/hc-webhook-samsung"
    start, end = "2026-09-14T01:00:00Z", "2026-09-14T01:15:00Z"
    meta = {"data_origin": "com.sec.android.app.shealth"}
    payload = {
        "steps": [{"count": 12, "start_time": start, "end_time": end, "metadata": meta}],
        "distance": [{"meters": 99, "start_time": start, "end_time": end}],
        "hydration": [
            {"liters": .25, "start_time": start, "end_time": end, "metadata": meta},
            {"liters": 99, "start_time": start, "end_time": end},
            {"liters": 88, "start_time": start, "end_time": end, "metadata": {"data_origin": "another.app"}},
        ],
    }
    result = client.post(endpoint, headers=headers, json=payload)
    assert result.status_code == 200 and result.json()["accepted"] == 2
    assert {item["metric"]: item["count"] for item in result.json()["skipped_unverified"]} == {"water": 1, "distance": 1}
    saved = client.get("/api/data/health_records").json()
    assert {r["metric"]: r["value"] for r in saved} == {"steps": 12, "water": 250}
    retry = client.post(endpoint, headers=headers, json=payload).json()
    assert retry["accepted"] == 0 and retry["duplicates"] == 2
    phone = client.get("/api/physical/readings").json()["phone_sync"]
    assert phone["status"] == "partial" and phone["cursor"]["skipped_unverified"] == retry["skipped_unverified"]
    # Source-qualified malformed records still reject atomically.
    payload["steps"][0]["end_time"] = "2026-09-14T02:00:00Z"
    payload["hydration"][0]["liters"] = -1
    assert client.post(endpoint, headers=headers, json=payload).status_code == 422
    assert len(client.get("/api/data/health_records").json()) == 2


def test_samsung_bridge_incremental_batches_and_retries(client):
    token = "separate-test-phone-bridge-secret"
    assert client.post("/api/secrets/health_webhook_token", json={"value": token}).status_code == 200
    headers = {"Authorization": "Bearer " + token}
    endpoint = "/api/integrations/health/hc-webhook-samsung"
    meta = {"data_origin": "com.sec.android.app.shealth"}
    start, end = "2026-09-13T10:00:00Z", "2026-09-13T10:15:00Z"
    payload = {
        "timestamp": "2026-09-13T10:20:00Z", "app_version": "1.9.20",
        "steps": [{"count": 321, "start_time": start, "end_time": end, "metadata": meta}],
        "sleep": [{"duration_seconds": 28800, "session_end_time": end, "stages": [], "metadata": meta}],
        "exercise": [{"type": "walking", "duration_seconds": 900, "start_time": start, "end_time": end, "metadata": meta}],
    }
    assert client.post(endpoint, json=payload).status_code == 401
    first = client.post(endpoint, json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json() == {"accepted": 3, "duplicates": 0}
    engine.dispose()
    payload["timestamp"] = "2026-09-13T10:35:00Z"
    assert client.post(endpoint, json=payload, headers=headers).json() == {"accepted": 0, "duplicates": 3}
    stored = client.get("/api/data/health_records").json()
    assert {r["metric"]: (r["value"], r["unit"]) for r in stored} == {
        "steps": (321, "count"), "sleep": (8, "hours"), "activity": (15, "minutes")
    }
    # A batch can contain just one changed type. Corrections to an existing
    # identity are ignored, rather than being counted as another interval.
    steps = payload["steps"][0]
    partial = {"steps": [{**steps, "count": 333}, {**steps, "start_time": end, "end_time": "2026-09-13T10:30:00Z", "count": 100}]}
    assert client.post(endpoint, json=partial, headers=headers).json() == {"accepted": 1, "duplicates": 1}
    partial["steps"].reverse()
    assert client.post(endpoint, json=partial, headers=headers).json() == {"accepted": 0, "duplicates": 2}
    other = {"steps": [{**steps, "metadata": {"data_origin": "another.app"}}]}
    assert client.post(endpoint, json=other, headers=headers).json() == {"accepted": 0, "duplicates": 0}
    assert client.post(endpoint, json={"timestamp": end}, headers=headers).json() == {"accepted": 0, "duplicates": 0}
    before = len(client.get("/api/data/health_records").json())
    bad = {"steps": [{**steps, "end_time": "2026-09-13T11:00:00Z"}, {"count": 5, "metadata": meta}]}
    assert client.post(endpoint, json=bad, headers=headers).status_code == 422
    assert len(client.get("/api/data/health_records").json()) == before
    bad["steps"] = [{**steps, "metadata": {"data_origin": ""}}]
    # Excluded origins never enter the database.
    assert client.post(endpoint, json=bad, headers=headers).json()["accepted"] == 0


def test_samsung_bridge_water_and_body_suggestions(client):
    token = "separate-test-phone-bridge-secret"
    client.post("/api/secrets/health_webhook_token", json={"value": token})
    meta = {"data_origin": "com.sec.android.app.shealth"}
    stamp = "2026-09-13T10:00:00Z"
    payload = {
        "hydration": [{"liters": .25, "start_time": stamp, "end_time": stamp, "metadata": meta}],
        "weight": [{"kilograms": 70, "time": stamp, "metadata": meta}],
        "height": [{"meters": 1.75, "time": stamp, "metadata": meta}],
    }
    response = client.post("/api/integrations/health/hc-webhook-samsung", json=payload, headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] == 3
    stored = client.get("/api/data/health_records").json()
    assert {r["metric"]: (r["value"], r["unit"]) for r in stored} == {"water": (250, "ml"), "weight": (70, "kg"), "height": (175, "cm")}
    assert len(client.get("/api/data/metric_suggestions").json()) == 2
    cfg = {r["key"]: r["value"] for r in client.get("/api/data/settings").json()}
    assert cfg["body"]["weight_kg"] is None and cfg["body"]["height_cm"] is None


def test_samsung_only_water_excludes_manual_history_and_latest_sensor_values(client):
    from app.services import setting
    stamp = datetime.now(timezone.utc).isoformat()
    base = {"metric": "water", "value": 500, "unit": "ml", "recorded_at": stamp, "source": "manual", "device": "owner", "external_id": str(uuid.uuid4())}
    assert client.post("/api/ingest", json=[base]).status_code == 200
    with engine.begin() as conn:
        setting(conn, "water_source", "samsung_health")
        put_secret(conn, "health_webhook_token", "watch-test-token")
    assert client.get("/api/dashboard").json()["metrics"].get("water", 0) == 0
    assert client.post("/api/ingest", json=[{**base, "external_id": str(uuid.uuid4())}]).status_code == 422
    meta = {"data_origin": "com.sec.android.app.shealth"}
    payload = {
        "hydration": [{"liters": .25, "start_time": stamp, "end_time": stamp, "metadata": meta}],
        "heart_rate": [{"bpm": 72, "time": stamp, "metadata": meta}, {"avg": 80, "min": 70, "max": 90, "time": "2026-01-01T00:00:00Z", "metadata": meta}],
        "skin_temperature": [{"delta_celsius": -.3, "time": stamp, "metadata": meta}],
        "sleep": [{"duration_seconds": 3600, "session_end_time": stamp, "metadata": meta, "stages": [{"stage": "5", "start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-01T00:15:00Z", "duration_seconds": 900}]}],
    }
    result = client.post("/api/integrations/health/hc-webhook-samsung", json=payload, headers={"Authorization": "Bearer watch-test-token"})
    assert result.status_code == 200, result.text
    assert result.json()["accepted"] == 6
    assert client.get("/api/dashboard").json()["metrics"]["water"] == 250
    assert client.get("/api/dashboard").json()["water_received_at"]
    readings = client.get("/api/physical/readings").json()
    assert len(readings["supported"]) == 37
    latest = {r["metric"]: r for r in readings["readings"]}
    assert latest["heart_rate"]["value"] == 72  # latest reading, never a sum of heart rates
    assert latest["skin_temperature_delta"]["value"] == -.3
    assert latest["sleep_deep"]["value"] == 15
    assert len(client.get("/api/data/health_records").json()) == 7  # old manual drink retained


def test_large_watch_batch_is_atomic_and_idempotent(client):
    with engine.begin() as conn:
        put_secret(conn, "health_webhook_token", "large-watch-test")
    payload = {"records": [{"metric": "heart_rate", "value": 70, "unit": "bpm", "recorded_at": "2026-09-13T10:00:00Z", "source": "synthetic-watch", "device": "test", "external_id": str(i)} for i in range(6001)]}
    headers = {"Authorization": "Bearer large-watch-test"}
    endpoint = "/api/integrations/health/default"
    assert client.post(endpoint, json=payload, headers=headers).json() == {"accepted": 6001, "duplicates": 0}
    assert client.post(endpoint, json=payload, headers=headers).json() == {"accepted": 0, "duplicates": 6001}
    first_page = client.get("/api/data/health_records").json()
    next_page = client.get("/api/data/health_records?limit=200&offset=200").json()
    assert len(first_page) == len(next_page) == 200
    assert not ({r["id"] for r in first_page} & {r["id"] for r in next_page})
    assert len(client.get("/api/data/health_records?offset=6000").json()) == 1
    assert client.get("/api/data/health_records?limit=1001").status_code == 422


def test_samsung_cloud_is_opt_in_and_private_state_is_encrypted(client):
    from app.integrations.samsung_storage import SecretSlot, read_json, write_json
    assert client.post("/api/integrations/samsung/pull").json()["state"] == "not_connected"
    with engine.begin() as conn:
        slot = SecretSlot(conn, "samsung_pending")
        write_json(slot, {"code_verifier": "private-test-verifier", "state": "private-state"})
        assert read_json(slot)["code_verifier"] == "private-test-verifier"
    with engine.connect() as conn:
        exported = json.dumps(export_data(conn), default=str)
        assert "private-test-verifier" not in exported
        assert "private-state" not in exported
    assert client.post("/api/integrations/samsung/auth/finish", json={"callback": "https://evil.example/?secret=test"}).status_code == 400
    assert client.get("/api/integrations/status").status_code == 200
    assert client.post("/api/integrations/samsung/disconnect").json() == {"connected": False}


def test_samsung_sign_in_encrypted_roundtrip_and_callback_replay(client):
    import httpx
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from samsung_health_cloud.constants import REDIRECT_URI
    from samsung_health_cloud.exceptions import AuthenticationError
    from app.integrations.samsung_account import AccountBootstrap
    from app.integrations.samsung_account import _trusted_auth_server_url
    from app.integrations.samsung_storage import SecretSlot, read_json
    assert _trusted_auth_server_url("eu-auth2.samsungosp.com") == "https://eu-auth2.samsungosp.com"
    for hostile in ("http://eu-auth2.samsungosp.com", "eu-auth2.samsungosp.com.evil.example", "https://user@eu-auth2.samsungosp.com", "https://eu-auth2.samsungosp.com/elsewhere"):
        with pytest.raises(AuthenticationError):
            _trusted_auth_server_url(hostile)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = base64.b64encode(key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)).decode()
    calls = []
    def handle(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"chkDoNum": 1000, "pkiPublicKey": public, "signInURI": "https://account.samsung.com/accounts/signInGate"})
        return httpx.Response(200, json={"userauth_token": "synthetic-master-only", "userId": "synthetic-user"})
    def enc(value, secret):
        pad = padding.PKCS7(128).padder()
        plaintext = pad.update(value.encode()) + pad.finalize()
        cipher = Cipher(algorithms.AES(secret.encode()[:16].ljust(16, b"\0")), modes.ECB()).encryptor()
        return (cipher.update(plaintext) + cipher.finalize()).hex()
    with engine.begin() as conn, httpx.Client(transport=httpx.MockTransport(handle)) as http:
        auth = AccountBootstrap(conn=conn, client=http)
        assert auth.start().startswith("https://account.samsung.com/accounts/signInGate?")
        pending = read_json(SecretSlot(conn, "samsung_pending"))
        response_key = "response-key-001"
        callback = REDIRECT_URI + "?" + str(httpx.QueryParams({
            "state": enc(response_key, pending["state"]),
            "auth_server_url": enc("synthetic.samsungosp.com", response_key),
            "code": enc("synthetic-code", response_key),
            "retValue": enc("synthetic@example.invalid", response_key),
        }))
        assert auth.complete(callback)["authenticated"] is True
        assert not SecretSlot(conn, "samsung_pending").exists()
        ciphertext = conn.execute(sa.select(s.secrets.c.ciphertext).where(s.secrets.c.name == "samsung_master")).scalar_one()
        assert "synthetic-master-only" not in ciphertext
        assert "synthetic-master-only" in get_secret(conn, "samsung_master")
        with pytest.raises((ValueError, AuthenticationError)):
            auth.complete(callback)
    assert len(calls) == 2
    assert str(calls[1].url) == "https://synthetic.samsungosp.com/auth/oauth2/authenticate"


def test_samsung_callback_recovery_is_encrypted_and_expires(client, monkeypatch):
    import time
    from samsung_health_cloud.constants import REDIRECT_URI
    from app.integrations.samsung_account import AccountBootstrap
    from app.integrations.samsung_storage import SecretSlot, write_json, read_json
    callback = REDIRECT_URI + "?code=private-recovery-code"
    with engine.begin() as conn:
        write_json(SecretSlot(conn, "samsung_pending"), {"created_at": time.time()})
    def fail(self, value):
        assert value == callback
        raise ValueError("Samsung returned an untrusted authentication server")
    monkeypatch.setattr(AccountBootstrap, "complete", fail)
    r = client.post("/api/integrations/samsung/auth/finish", json={"callback": callback})
    assert r.status_code == 400 and r.json()["detail"]["reason"] == "unexpected_provider"
    with engine.connect() as conn:
        assert read_json(SecretSlot(conn, "samsung_callback"))["callback"] == callback
        encrypted = conn.execute(sa.select(s.secrets.c.ciphertext).where(s.secrets.c.name == "samsung_callback")).scalar_one()
        assert "private-recovery-code" not in encrypted
    monkeypatch.setattr(AccountBootstrap, "complete", lambda self, value: {"authenticated": value == callback})
    assert client.post("/api/integrations/samsung/auth/retry").json()["authenticated"] is True
    assert client.post("/api/integrations/samsung/auth/retry").status_code == 409
    with engine.begin() as conn:
        write_json(SecretSlot(conn, "samsung_callback"), {"callback": callback, "created_at": time.time() - 901})
    assert client.post("/api/integrations/samsung/auth/retry").json()["detail"]["reason"] == "expired"
    with engine.connect() as conn:
        assert not SecretSlot(conn, "samsung_callback").exists()


def test_samsung_cloud_page_resumes_and_raw_stress_is_not_interpreted(client, monkeypatch):
    from app.services import setting
    from app.integrations.samsung_session import SamsungHealthService
    from samsung_health_cloud.data import CloudDataClient
    from samsung_health_cloud.state import HealthState
    with engine.begin() as conn:
        setting(conn, "samsung_cloud", {"enabled": True})
        put_secret(conn, "samsung_master", "test-master-present")
    monkeypatch.setattr(SamsungHealthService, "initialize", lambda self: HealthState(cloud_token="private-cloud-token"))
    calls = []
    def page(self, **kwargs):
        calls.append(kwargs.get("page_token"))
        return {"documents": [{"data": {"datauuid": "private-record-uuid", "start_time": 1789293600000, "stress_level": 12, "note": "private note", "latitude": 10}}], "nextPageToken": "private-next-token" if len(calls) == 1 else None}
    monkeypatch.setattr(CloudDataClient, "list_documents", page)
    first = client.post("/api/integrations/samsung/pull").json()
    assert first["accepted"] == 1 and first["state"] == "running"
    engine.dispose()
    second = client.post("/api/integrations/samsung/pull").json()
    assert second["duplicates"] == 1 and second["collections_finished"] == 1
    assert calls == [None, "private-next-token"]
    records = client.get("/api/data/health_records").json()
    assert len(records) == 1 and records[0]["unit"] == "raw"
    assert records[0]["metric"] == "samsung_raw/health.stress/stress_level"
    assert "private-record-uuid" not in json.dumps(records)
    with engine.connect() as conn:
        exported = json.dumps(export_data(conn), default=str)
        assert "private-next-token" not in exported
    def fail(self, **kwargs):
        raise RuntimeError("private-token-must-not-leak")
    monkeypatch.setattr(CloudDataClient, "list_documents", fail)
    response = client.post("/api/integrations/samsung/pull")
    assert response.status_code == 200 and response.json()["state"] == "failed"
    assert "private-token" not in response.text
    assert client.get("/api/dashboard").status_code == 200


def test_samsung_data_error_diagnostics_redact_credentials(client, monkeypatch):
    import httpx
    from app.services import setting
    from app.integrations.samsung_session import SamsungHealthService
    from samsung_health_cloud.state import HealthState
    with engine.begin() as conn:
        setting(conn, "samsung_cloud", {"enabled": True})
        put_secret(conn, "samsung_master", "test-master-present")
    state = HealthState(cloud_token="private-cloud-token", user_id="private-user", cdid="private-device")
    monkeypatch.setattr(SamsungHealthService, "initialize", lambda self: state)
    def response(request):
        assert "start_time" not in request.url.params
        return httpx.Response(400, json={"code": "BAD_REQUEST", "message": "Invalid schemaRevision for private-user private-device private-cloud-token person@example.com https://example.com/private"})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(response), **kwargs))
    result = client.post("/api/integrations/samsung/pull")
    assert result.status_code == 200 and result.json()["state"] == "failed"
    diagnostic = result.json()["diagnostic"]
    assert diagnostic["stage"] == "documents" and diagnostic["http_status"] == 400
    assert diagnostic["provider_code"] == "BAD_REQUEST"
    assert "schemarevision" in diagnostic["problem_fields"]
    assert diagnostic["provider_message"].startswith("Invalid schemaRevision")
    with engine.connect() as conn:
        saved = json.dumps(export_data(conn), default=str)
    for private in ("private-user", "private-device", "private-cloud-token", "person@example.com", "https://example.com/private"):
        assert private not in result.text and private not in saved


@pytest.mark.parametrize("server_revision", [15, 4])
def test_samsung_server_revision_retries_same_collection(client, monkeypatch, server_revision):
    import httpx
    from app.services import setting
    from app.integrations.samsung_session import SamsungHealthService
    from app.integrations.samsung_storage import SecretSlot, read_json, write_json
    from samsung_health_cloud.state import HealthState
    with engine.begin() as conn:
        setting(conn, "samsung_cloud", {"enabled": True})
        put_secret(conn, "samsung_master", "test-master-present")
        write_json(SecretSlot(conn, "samsung_cursor"), {"page": "old-schema-page"})
    monkeypatch.setattr(SamsungHealthService, "initialize", lambda self: HealthState(cloud_token="private-token"))
    requests = []
    def response(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(400, json={"rcode": 4001001, "rmsg": f"The schemaRevision is invalid, you should update to the latest schema information (server revision: {server_revision})"})
        return httpx.Response(200, json={"documents": []})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(response), **kwargs))
    first = client.post("/api/integrations/samsung/pull").json()
    engine.dispose()
    second = client.post("/api/integrations/samsung/pull").json()
    assert first["state"] == "running" and first["collections_finished"] == 0
    assert second["collection"] == first["collection"] and second["collections_finished"] == 1
    assert requests[0].url.params["schemaRevision"] == "13"
    assert requests[1].url.params["schemaRevision"] == str(server_revision) and "pageToken" not in requests[1].url.params
    with engine.connect() as conn:
        assert read_json(SecretSlot(conn, "samsung_cursor"))["revisions"]["com.samsung.health.stress"] == server_revision
    # A provider that keeps changing its requested revision cannot make the
    # browser retry forever. Preserve the collection after the bounded retries.
    requests.clear()
    with engine.begin() as conn:
        write_json(SecretSlot(conn, "samsung_cursor"), {"revision_retries": {"com.samsung.health.stress": 2}})
    assert client.post("/api/integrations/samsung/pull").json()["state"] == "failed"


@pytest.mark.parametrize("status", [400, 404])
def test_samsung_missing_collections_do_not_block_or_lose_history(client, monkeypatch, status):
    import httpx
    from app.services import setting
    from app.integrations.samsung_session import SamsungHealthService
    from app.integrations.samsung_storage import SecretSlot, read_json, write_json
    from samsung_health_cloud.state import HealthState
    with engine.begin() as conn:
        setting(conn, "samsung_cloud", {"enabled": True})
        put_secret(conn, "samsung_master", "test-master-present")
    monkeypatch.setattr(SamsungHealthService, "initialize", lambda self: HealthState(cloud_token="private-token"))
    requests = []
    def response(request):
        requests.append(request)
        manifest = request.url.path.split("/")[-2]
        return httpx.Response(status, json={"rcode": 40001, "rmsg": f"cid of {manifest} not exists"})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(response), **kwargs))
    first = client.post("/api/integrations/samsung/pull").json()
    assert first["state"] == "unavailable" and first["collections_finished"] == 1
    assert first["unavailable_collections"] == ["com.samsung.health.stress"]
    second = client.post("/api/integrations/samsung/pull").json()
    assert second["collection"] != first["collection"] and second["collections_finished"] == 2
    with engine.begin() as conn:
        slot = SecretSlot(conn, "samsung_cursor")
        cursor = read_json(slot)
        cursor.update(index=15)
        write_json(slot, cursor)
    last = client.post("/api/integrations/samsung/pull").json()
    assert last["state"] == "complete" and "3 collections unavailable" in last["message"]
    cached = client.post("/api/integrations/samsung/pull").json()
    assert cached["unavailable_collections"] == last["unavailable_collections"]
    with engine.begin() as conn:
        slot = SecretSlot(conn, "samsung_cursor")
        cursor = read_json(slot)
        cursor["finished_at"] -= 3_600_001
        write_json(slot, cursor)
    retry = client.post("/api/integrations/samsung/pull").json()
    assert retry["collection"] == "com.samsung.health.stress"
    assert "start_time" not in requests[-1].url.params


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
