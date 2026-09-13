"""Host startup helper: run after migrations; never overwrite the existing owner."""

import os
import sqlalchemy as sa
from .db import engine
from .schema import owners
from .seed import seed
from .security import hasher


def bootstrap():
    seed()
    with engine.begin() as conn:
        conn.execute(sa.text("SELECT pg_advisory_xact_lock(7410391)"))
        if conn.execute(sa.select(sa.func.count()).select_from(owners)).scalar():
            return
        password_hash = os.getenv("OWNER_PASSWORD_HASH")
        if not password_hash:
            raise SystemExit(
                "No owner exists. Run python -m app.cli owner locally, or set OWNER_PASSWORD_HASH on the host."
            )
        try:
            hasher.check_needs_rehash(password_hash)
        except Exception:
            raise SystemExit(
                "OWNER_PASSWORD_HASH must be an Argon2 hash generated locally."
            )
        conn.execute(
            sa.insert(owners).values(
                username=os.getenv("OWNER_USERNAME", "owner"),
                password_hash=password_hash,
            )
        )


if __name__ == "__main__":
    bootstrap()
