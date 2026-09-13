"""Versioned lossless backups. CSV cells contain JSON values, preserving null/types."""

import io, json, zipfile, csv, uuid
from datetime import datetime, date
import sqlalchemy as sa
from .schema import metadata, TABLES


def encode(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(type(value).__name__)


def dumps(value):
    return json.dumps(value, default=encode, allow_nan=False)


def coerce(table, row):
    result = {}
    for key, val in row.items():
        if key not in table.c:
            raise ValueError("Unknown column: " + key)
        typ = table.c[key].type
        if val is not None:
            if isinstance(typ, sa.DateTime):
                val = (
                    datetime.fromisoformat(val.replace("Z", "+00:00"))
                    if isinstance(val, str)
                    else val
                )
                if val.tzinfo is None:
                    raise ValueError(key + " requires a timezone offset")
            elif isinstance(typ, sa.Date):
                val = date.fromisoformat(val) if isinstance(val, str) else val
            elif isinstance(typ, sa.Uuid):
                val = uuid.UUID(str(val))
        result[key] = val
    return result


def export_data(conn, set_isolation=True):
    if set_isolation:
        conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    data = {
        t.name: [dict(r) for r in conn.execute(sa.select(t)).mappings()]
        for t in metadata.sorted_tables
    }
    data["alembic_version"] = [
        {
            "version_num": conn.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()
        }
    ]
    return {"format": "life-os-backup", "version": 1, "schema": "0002", "tables": data}


def archive(data):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("life-os.json", dumps(data))
        for name, rows in data["tables"].items():
            z.writestr("json/" + name + ".json", dumps(rows))
            fields = list(TABLES[name].c.keys()) if name in TABLES else ["version_num"]
            out = io.StringIO()
            writer = csv.DictWriter(out, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: dumps(v) for k, v in row.items()})
            z.writestr("csv/" + name + ".csv", out.getvalue())
        z.writestr(
            "manifest.json", dumps({k: v for k, v in data.items() if k != "tables"})
        )
    return buf.getvalue()


def parse_backup(raw):
    if raw.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if sum(i.file_size for i in z.infolist()) > 100_000_000:
                raise ValueError("Backup exceeds 100 MB expanded size")
            if "life-os.json" in z.namelist():
                return json.loads(z.read("life-os.json"))
            manifest = json.loads(z.read("manifest.json"))
            manifest["tables"] = {}
            names = [*TABLES, "alembic_version"]
            if manifest.get("schema") == "0001":
                names.remove("backup_transfers")
            for name in names:
                reader = csv.DictReader(
                    io.StringIO(z.read("csv/" + name + ".csv").decode())
                )
                manifest["tables"][name] = [
                    {k: json.loads(v) for k, v in row.items()} for row in reader
                ]
            return manifest
    return json.loads(raw)


def restore(conn, data, replace=False):
    # Backups from before transport chunking remain restorable after migration.
    if isinstance(data, dict) and data.get("schema") == "0001":
        import copy

        data = copy.deepcopy(data)
        if data.get("tables", {}).get("alembic_version") != [{"version_num": "0001"}]:
            raise ValueError("Migration revision does not match")
        if set(data.get("tables", {})) != (set(TABLES) - {"backup_transfers"}) | {
            "alembic_version"
        }:
            raise ValueError("Backup must include every table")
        data["schema"] = "0002"
        data["tables"]["backup_transfers"] = []
        data["tables"]["alembic_version"] = [{"version_num": "0002"}]
    if (
        not isinstance(data, dict)
        or data.get("format") != "life-os-backup"
        or data.get("schema") != "0002"
        or data.get("version") != 1
    ):
        raise ValueError("Unsupported backup format or schema version")
    if not isinstance(data.get("tables"), dict):
        raise ValueError("Backup tables are missing")
    if set(data["tables"]) != {*TABLES, "alembic_version"}:
        raise ValueError("Backup must include every table")
    if data["tables"]["alembic_version"] != [{"version_num": "0002"}]:
        raise ValueError("Migration revision does not match")
    for t in metadata.sorted_tables:
        if not isinstance(data["tables"][t.name], list):
            raise ValueError("Table must contain a list of rows: " + t.name)
        for row in data["tables"][t.name]:
            if not isinstance(row, dict) or set(row) != set(t.c.keys()):
                raise ValueError("Incomplete row in " + t.name)
    if not replace and any(
        conn.execute(sa.select(sa.func.count()).select_from(t)).scalar()
        for t in metadata.sorted_tables
    ):
        raise ValueError("Restore requires an empty database or explicit replace")
    # TRUNCATE is transactional in PostgreSQL; all constraints remain enforced on insert.
    if replace:
        conn.exec_driver_sql(
            "TRUNCATE "
            + ", ".join('"' + t.name + '"' for t in metadata.sorted_tables)
            + " CASCADE"
        )
    for t in metadata.sorted_tables:
        rows = [coerce(t, r) for r in data["tables"][t.name]]
        # Self-references (task parents/previous instances, recurring exceptions) insert in dependency order.
        self_keys = [
            c.name
            for c in t.c
            if any(f.column.table.name == t.name for f in c.foreign_keys)
        ]
        inserted = set()
        while rows:
            ready = [
                r
                for r in rows
                if all(r[k] is None or r[k] in inserted for k in self_keys)
            ]
            if not ready:
                raise ValueError("Cyclic or missing self-reference in " + t.name)
            conn.execute(sa.insert(t), ready)
            inserted.update(r["id"] for r in ready)
            rows = [r for r in rows if r["id"] not in inserted]
