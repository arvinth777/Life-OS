"""Private Samsung credentials use the app's encrypted Postgres secret store."""

import json
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import sqlalchemy as sa
from .. import schema as s
from ..security import get_secret, put_secret


@dataclass
class SecretSlot:
    conn: object
    name: str

    def exists(self):
        return get_secret(self.conn, self.name) is not None


def read_json(slot):
    raw = get_secret(slot.conn, slot.name)
    if raw is None:
        raise ValueError("Samsung sign-in state is missing. Start sign-in again.")
    return json.loads(raw)


def write_json(slot, value):
    put_secret(slot.conn, slot.name, json.dumps(value))


def secure_unlink(slot):
    slot.conn.execute(sa.delete(s.secrets).where(s.secrets.c.name == slot.name))


def load_master_credentials(slot):
    from samsung_health_cloud.credentials import _validate_master_state_v1
    return _validate_master_state_v1(read_json(slot))


class EncryptedStateStore:
    def __init__(self, conn):
        self.slot = SecretSlot(conn, "samsung_session")

    @contextmanager
    def locked(self):
        # Caller holds a transaction-level Postgres advisory lock across hosts.
        yield

    def load(self):
        from samsung_health_cloud.state import HealthState
        return HealthState(**read_json(self.slot)) if self.slot.exists() else HealthState()

    def save(self, value):
        write_json(self.slot, asdict(value))
