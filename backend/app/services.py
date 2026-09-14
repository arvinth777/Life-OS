import uuid, math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import HTTPException
from . import schema as s
from .domain import streak, nutrition, calendar_occurrences
from .backup import coerce


def rows(conn, name):
    return [dict(r) for r in conn.execute(sa.select(s.TABLES[name])).mappings()]


def config(conn):
    return {r["key"]: r["value"] for r in rows(conn, "settings")}


def setting(conn, key, value):
    conn.execute(
        pg_insert(s.settings)
        .values(key=key, value=value)
        .on_conflict_do_update(
            index_elements=[s.settings.c.key],
            set_={"value": value, "updated_at": s.now()},
        )
    )


UNITS = {
    "water": "ml",
    "steps": "count",
    "sleep": "hours",
    "activity": "minutes",
    "weight": "kg",
    "height": "cm",
    "heart_rate": "bpm",
    "hrv": "ms",
    "stress": "score",
    "body_fat": "percent",
    "resting_heart_rate": "bpm",
    "oxygen_saturation": "percent",
    "respiratory_rate": "breaths/min",
    "distance": "m",
    "active_calories": "kcal",
    "total_calories": "kcal",
    "body_temperature": "C",
    "skin_temperature_delta": "C",
    "lean_body_mass": "kg",
    "body_water_mass": "kg",
    "bone_mass": "kg",
    "vo2_max": "ml/kg/min",
    "basal_metabolic_rate": "W",
    "blood_pressure_systolic": "mmHg",
    "blood_pressure_diastolic": "mmHg",
    "blood_glucose": "mmol/L",
}


def ingest(conn, records, manual=False):
    if not isinstance(records, list) or not 1 <= len(records) <= 25000:
        raise ValueError("Supply 1–25000 health records; shorten the phone sync range for larger imports")
    normalized = []
    cfg = config(conn)
    for record in records:
        required = {
            "metric",
            "value",
            "unit",
            "recorded_at",
            "source",
            "device",
            "external_id",
        }
        if set(record) != required:
            raise ValueError(
                "Health records require exactly: " + ", ".join(sorted(required))
            )
        r = coerce(s.health_records, record)
        if not all(
            isinstance(r[k], str) and r[k].strip()
            for k in required - {"value", "recorded_at"}
        ):
            raise ValueError("Health text fields cannot be empty")
        r["value"] = float(r["value"])
        if not math.isfinite(r["value"]) or (r["value"] < 0 and r["metric"] not in {"skin_temperature_delta", "body_temperature"} and not (r["source"] == "samsung-cloud" and r["metric"].startswith("samsung_raw/") and r["unit"] == "raw")):
            raise ValueError("Health value must be finite and nonnegative")
        if r["metric"] in UNITS and r["unit"] != UNITS[r["metric"]]:
            raise ValueError(
                "Expected unit " + UNITS[r["metric"]] + " for " + r["metric"]
            )
        if manual and r["source"] != "manual":
            raise ValueError("Manual entries must use source=manual")
        if manual and r["metric"] == "water" and cfg.get("water_source") == "samsung_health":
            raise ValueError("Water is tracked in Samsung Health. Change the water source in Settings to enter it here.")
        normalized.append(r)
    accepted = 0
    body = cfg.get("body", {})
    for start in range(0, len(normalized), 500):
        inserted = conn.execute(
            pg_insert(s.health_records)
            .values(normalized[start:start + 500])
            .on_conflict_do_nothing(
                index_elements=[
                    s.health_records.c.source,
                    s.health_records.c.external_id,
                ]
            )
            .returning(s.health_records.c.id, s.health_records.c.metric, s.health_records.c.value, s.health_records.c.source)
        ).mappings()
        for r in inserted:
            accepted += 1
            key = {"weight": "weight_kg", "height": "height_cm"}.get(r["metric"])
            if r["source"] != "manual" and key and body.get(key) != r["value"]:
                conn.execute(
                    sa.insert(s.metric_suggestions).values(
                        record_id=r["id"], setting_key=key, proposed_value=r["value"]
                    )
                )
    return {"accepted": accepted, "duplicates": len(records) - accepted}


def dashboard(conn, at=None):
    cfg = config(conn)
    zone = cfg.get("timezone", "UTC")
    tz = ZoneInfo(zone)
    at = at or s.now()
    today = at.astimezone(tz).date()
    local = lambda t: t.astimezone(tz).date()
    journal = rows(conn, "journal_entries")
    attempts = rows(conn, "problem_attempts")
    reviews = rows(conn, "reviews")
    workouts = rows(conn, "workouts")
    source = {
        "journal": [r["created_at"] for r in journal],
        "attempt": [r["attempted_at"] for r in attempts],
        "review": [r["reviewed_at"] for r in reviews],
        "workout": [r["performed_at"] for r in workouts],
    }
    definitions = cfg.get(
        "streaks",
        {"Journal": ["journal"], "DSA": ["attempt", "review"], "Workout": ["workout"]},
    )
    streaks = {
        name: streak([d for kind in kinds for d in source[kind]], zone, at)
        for name, kinds in definitions.items()
    }
    start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
    end = start + timedelta(days=1)
    health = s.health_records
    source_filter = sa.true() if cfg.get("water_source") != "samsung_health" else sa.or_(health.c.metric != "water", health.c.source == "hc-webhook-samsung-water")
    # Watch history can be large. Fetch only daily additive totals, never the
    # complete sensor history or a nonsensical sum of heart-rate samples.
    metrics = dict(conn.execute(sa.select(health.c.metric, sa.func.sum(health.c.value)).where(
        health.c.metric.in_(["water", "steps", "sleep", "activity"]),
        health.c.recorded_at >= start, health.c.recorded_at < end, source_filter,
    ).group_by(health.c.metric)).all())
    water_received_at = conn.execute(sa.select(sa.func.max(health.c.created_at)).where(health.c.metric == "water", source_filter)).scalar()
    tasks = [
        r
        for r in rows(conn, "tasks")
        if r["status"] != "done" and r["due_at"] and local(r["due_at"]) <= today
    ]
    start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
    end = start + timedelta(days=1)
    agenda = calendar_occurrences(rows(conn, "calendar_events"), start, end)
    return {
        "today": today,
        "timezone": zone,
        "streaks": streaks,
        "metrics": metrics,
        "water_source": cfg.get("water_source", "manual"),
        "water_received_at": water_received_at,
        "tasks": sorted(tasks, key=lambda r: (-r["priority"], r["due_at"])),
        "agenda": sorted(agenda, key=lambda r: r["starts_at"]),
        "nutrition": nutrition(cfg.get("body", {})),
        "reviews_due": sum(r["due_on"] <= today for r in rows(conn, "concept_notes")),
    }


def academic_summary(conn):
    cfg = config(conn).get("grading", {})
    components = rows(conn, "grade_components")
    grades = rows(conn, "grades")
    result = []
    bands = sorted(cfg.get("bands", []), key=lambda x: x["minimum"], reverse=True)
    for course in rows(conn, "courses"):
        cs = [c for c in components if c["course_id"] == course["id"]]
        weighted = weight = 0
        for c in cs:
            gs = [g for g in grades if g["component_id"] == c["id"]]
            if gs:
                percentage = (
                    sum(g["earned"] for g in gs) / sum(g["possible"] for g in gs) * 100
                )
                weighted += percentage * c["weight"]
                weight += c["weight"]
        score = weighted / weight if weight else None
        band = next(
            (b for b in bands if score is not None and score >= b["minimum"]), None
        )
        result.append(
            {
                **course,
                "average": score,
                "coverage": weight / sum(c["weight"] for c in cs) if cs else 0,
                "gpa": band.get("points") if band else None,
                "grade": band.get("label") if band else None,
            }
        )
    terms = []
    for term in rows(conn, "terms"):
        cs = [
            c for c in result if c["term_id"] == term["id"] and c["average"] is not None
        ]
        avg = (
            sum(c["average"] * c["credits"] for c in cs) / sum(c["credits"] for c in cs)
            if cs
            else None
        )
        gp = [c for c in cs if c["gpa"] is not None]
        weight = lambda c: (
            c["credits"]
            if cfg.get("aggregation", "credit_weighted") == "credit_weighted"
            else 1
        )
        gpa = (
            sum(c["gpa"] * weight(c) for c in gp) / sum(weight(c) for c in gp)
            if gp
            else None
        )
        terms.append({**term, "average": avg, "gpa": gpa})
    return {"courses": result, "terms": terms}


def progress(conn):
    attempts = rows(conn, "problem_attempts")
    problems = rows(conn, "problems")
    patterns = rows(conn, "patterns")
    threshold = float(config(conn).get("accuracy_threshold", 0.6))
    result = []
    for p in patterns:
        ids = {r["id"] for r in problems if r["pattern_id"] == p["id"]}
        aa = [a for a in attempts if a["problem_id"] in ids]
        accuracy = sum(a["solved"] for a in aa) / len(aa) if aa else None
        result.append(
            {
                "id": p["id"],
                "title": p["title"],
                "attempts": len(aa),
                "solved": len({a["problem_id"] for a in aa if a["solved"]}),
                "accuracy": accuracy,
                "weak": accuracy is not None and accuracy < threshold,
            }
        )
    return {
        "patterns": result,
        "trend": sorted(attempts, key=lambda r: r["attempted_at"]),
    }


def muscle_volume(conn, workout_id=None, week=False):
    workouts = rows(conn, "workouts")
    cfg = config(conn)
    tz = ZoneInfo(cfg.get("timezone", "UTC"))
    today = s.now().astimezone(tz).date()
    monday = today - timedelta(days=today.weekday())
    ids = {
        w["id"]
        for w in workouts
        if (
            str(w["id"]) == str(workout_id)
            if workout_id
            else week
            and monday
            <= w["performed_at"].astimezone(tz).date()
            < monday + timedelta(days=7)
        )
    }
    sets = [r for r in rows(conn, "workout_sets") if r["workout_id"] in ids]
    maps = rows(conn, "exercise_muscles")
    result = []
    for group in rows(conn, "muscle_groups"):
        volume = sum(
            m["contribution"]
            for st in sets
            for m in maps
            if m["exercise_id"] == st["exercise_id"] and m["muscle_id"] == group["id"]
        )
        result.append({**group, "volume": volume})
    return result


def reminders(conn):
    data = dashboard(conn)
    today = str(data["today"])
    local = s.now().astimezone(ZoneInfo(data["timezone"]))
    dismissed = {
        (str(d["rule_id"]), d["occurrence_key"])
        for d in rows(conn, "reminder_dismissals")
    }
    result = []
    for rule in rows(conn, "reminder_rules"):
        if not rule["enabled"] or (str(rule["id"]), today) in dismissed:
            continue
        cfg = rule["config"]
        kind = rule["kind"]
        active = (
            (
                kind == "water"
                and data["metrics"].get("water", 0) < float(cfg.get("target_ml", 2000))
            )
            or (kind == "task_due" and bool(data["tasks"]))
            or (
                kind == "journal"
                and local.hour >= int(cfg.get("hour", 18))
                and not any(
                    r["created_at"].astimezone(local.tzinfo).date() == local.date()
                    for r in rows(conn, "journal_entries")
                )
            )
        )
        if active:
            result.append({**rule, "occurrence_key": today})
    return result
