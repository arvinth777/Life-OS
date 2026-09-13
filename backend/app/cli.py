import argparse, getpass
from pathlib import Path
import sqlalchemy as sa
from .db import engine
from .schema import owners
from .security import hasher
from .backup import parse_backup, restore, archive, export_data


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    owner = sub.add_parser("owner")
    owner.add_argument("--username", default="owner")
    imp = sub.add_parser("restore")
    imp.add_argument("path")
    imp.add_argument("--replace", action="store_true")
    exp = sub.add_parser("export")
    exp.add_argument("path")
    args = parser.parse_args()
    if args.command == "owner":
        password = getpass.getpass("Choose owner password (12+ characters): ")
        if len(password) < 12:
            raise SystemExit("Use at least 12 characters")
        if password != getpass.getpass("Repeat password: "):
            raise SystemExit("Passwords differ")
        with engine.begin() as conn:
            if conn.execute(sa.select(sa.func.count()).select_from(owners)).scalar():
                raise SystemExit("Owner already exists; this command never replaces it")
            conn.execute(
                sa.insert(owners).values(
                    username=args.username, password_hash=hasher.hash(password)
                )
            )
        print("Owner created.")
    elif args.command == "restore":
        with engine.begin() as conn:
            restore(conn, parse_backup(Path(args.path).read_bytes()), args.replace)
        print("Backup restored.")
    else:
        with engine.begin() as conn:
            data = export_data(conn)
        Path(args.path).write_bytes(archive(data))
        print("Backup exported.")


if __name__ == "__main__":
    main()
