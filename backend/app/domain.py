"""Pure calculations; timestamps are instants and streak dates use the configured zone."""

import math
import hashlib
import json
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from dateutil.rrule import rrulestr


def sm2(state, grade, today):
    if not isinstance(grade, int) or not 0 <= grade <= 5:
        raise ValueError("Review grade must be 0–5")
    ef = float(state["ease_factor"])
    reps = state["repetitions"]
    interval = state["interval_days"]
    # SM-2: failure q<3 restarts at repetition 0 with a one-day interval.
    # Success intervals: 1, 6, then round(previous interval * PREVIOUS EF).
    # EF' = max(1.3, EF + 0.1 - (5-q)*(0.08 + (5-q)*0.02)).
    # Positive half values round upward, independent of Python's bankers rounding.
    if grade < 3:
        reps, interval = 0, 1
    else:
        interval = (
            1 if reps == 0 else 6 if reps == 1 else math.floor(interval * ef + 0.5)
        )
        reps += 1
    ef = max(1.3, ef + 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    return dict(
        ease_factor=round(ef, 8),
        repetitions=reps,
        interval_days=interval,
        due_on=today + timedelta(days=interval),
    )


def streak(instants, zone, at=None):
    tz = ZoneInfo(zone)
    today = (at or datetime.now(timezone.utc)).astimezone(tz).date()
    days = {t.astimezone(tz).date() for t in instants if t}
    cursor = today if today in days else today - timedelta(days=1)
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def next_task_date(rule, anchor, completed, zone):
    tz = ZoneInfo(zone)
    parsed = rrulestr(rule, dtstart=anchor.astimezone(tz))
    return parsed.after(completed.astimezone(tz), inc=False)


def nutrition(body):
    keys = [
        "weight_kg",
        "height_cm",
        "age",
        "sex",
        "activity_multiplier",
        "goal",
        "protein_g_per_kg",
    ]
    if any(body.get(k) in (None, "") for k in keys):
        return {"configured": False}
    mass = float(body["weight_kg"])
    height = float(body["height_cm"])
    age = float(body["age"])
    bmr = 10 * mass + 6.25 * height - 5 * age + (5 if body["sex"] == "male" else -161)
    factor = float(body["protein_g_per_kg"][body["goal"]])
    return dict(
        configured=True,
        bmr=round(bmr),
        maintenance=round(bmr * float(body["activity_multiplier"])),
        protein_g=round(mass * factor),
    )


def normalize_body(payload, mapping, diagnostics=None):
    if "streams" in mapping:
        if not isinstance(mapping["streams"], list):
            raise ValueError("Mapping streams must be a list")
        result = []
        for stream in mapping["streams"]:
            try:
                result.extend(normalize_body(payload, stream, diagnostics))
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                spec = stream.get("fields", {}).get("metric", {})
                metric = spec.get("constant", "unknown") if isinstance(spec, dict) else "unknown"
                metric = metric[:80] if isinstance(metric, str) else "unknown"
                detail = {"stage": "mapping", "metric": metric, "error_type": type(exc).__name__}
                if isinstance(exc, KeyError) and exc.args and isinstance(exc.args[0], str):
                    detail["missing_field"] = exc.args[0][:80]
                error = ValueError(f"The {metric} mapping could not read a field in the bridge payload")
                error.bridge_detail = detail
                raise error from None
        return result

    def get(obj, path):
        if path in ("", None, "$"):
            return obj
        for part in path.removeprefix("$.").split("."):
            obj = obj[int(part)] if isinstance(obj, list) else obj[part]
        return obj

    try:
        records = get(payload, mapping.get("records_path", ""))
    except KeyError:
        # An optional stream may be absent in an incremental phone payload.
        # Malformed present rows must still fail the entire batch below.
        if mapping.get("optional", False):
            return []
        raise
    if not isinstance(records, list):
        records = [records]
    if "children_path" in mapping:
        expanded = []
        for parent in records:
            children = get(parent, mapping["children_path"])
            if not isinstance(children, list):
                raise ValueError("Child records must be an array")
            expanded.extend({**parent, **child} for child in children)
        records = expanded
    result = []
    for row in records:
        conditions = mapping.get("where_all", []) + ([mapping["where"]] if mapping.get("where") else [])
        matches = True
        for condition in conditions:
            try:
                actual = get(row, condition["path"])
            except KeyError:
                # Missing provenance cannot satisfy an origin filter. Exclude
                # it without rejecting verified records in the same request.
                if diagnostics is not None:
                    spec = mapping.get("fields", {}).get("metric", {})
                    metric = spec.get("constant", "unknown") if isinstance(spec, dict) else "unknown"
                    key = (metric, condition["path"])
                    diagnostics[key] = diagnostics.get(key, 0) + 1
                matches = False
                break
            if actual != condition["equals"]:
                matches = False
                break
        if not matches:
            continue
        if mapping.get("optional_value"):
            try:
                get(row, mapping["fields"]["value"]["path"])
            except KeyError:
                continue
        record = {}
        for key, spec in mapping["fields"].items():
            if isinstance(spec, dict) and "first_present" in spec:
                for path in spec["first_present"]:
                    try:
                        record[key] = get(row, path)
                        break
                    except KeyError:
                        pass
                else:
                    raise ValueError("None of the configured reading fields is present")
                continue
            if isinstance(spec, dict) and "hash_paths" in spec:
                paths = spec["hash_paths"]
                if key != "external_id" or not isinstance(paths, list) or not paths:
                    raise ValueError("hash_paths requires a nonempty external_id path list")
                parts = [get(row, path) for path in paths]
                if any(v is None or v == "" for v in parts):
                    raise ValueError("Record identity fields cannot be empty")
                # Legacy bridges omit native IDs. Hash only the configured stable
                # identity fields, never the send time, value, or array position.
                # Same-identity corrections remain duplicates under the ingestion
                # contract; a changed identity cannot be recognized as an update.
                identity = json.dumps(parts, sort_keys=True, separators=(",", ":"))
                record[key] = "sha256:" + hashlib.sha256(identity.encode()).hexdigest()
                continue
            record[key] = (
                spec["constant"]
                if isinstance(spec, dict) and "constant" in spec
                else get(row, spec["path"] if isinstance(spec, dict) else spec)
            )
        record["value"] = float(record["value"]) * float(
            mapping.get("value_multiplier", 1)
        )
        if mapping.get("timestamp_format") in ("unix_seconds", "unix_milliseconds"):
            divisor = 1000 if mapping["timestamp_format"] == "unix_milliseconds" else 1
            record["recorded_at"] = datetime.fromtimestamp(
                float(record["recorded_at"]) / divisor, timezone.utc
            ).isoformat()
        result.append(record)
    return result


def calendar_occurrences(events, start, end):
    """Expand only in memory; persisted rows are masters plus explicit exceptions."""
    out = []
    active_masters = {
        str(e["id"]) for e in events if not e["master_id"] and not e["deleted_at"]
    }
    exceptions = {
        (str(e["master_id"]), e["original_start"]): e
        for e in events
        if e["master_id"] and str(e["master_id"]) in active_masters
    }
    for event in events:
        if event["master_id"] or event["deleted_at"]:
            continue
        duration = event["ends_at"] - event["starts_at"]
        if event["recurrence"]:
            rule = rrulestr(
                "\n".join(event["recurrence"]),
                dtstart=event["starts_at"].astimezone(ZoneInfo(event["timezone"])),
                forceset=True,
            )
            # xafter is lazy and bounded, avoiding a list explosion from dense rules.
            dates = []
            for occurrence in rule.xafter(start - duration, count=2000, inc=True):
                if occurrence >= end:
                    break
                dates.append(occurrence)
        else:
            dates = [event["starts_at"]]
        for occurrence in dates:
            if (str(event["id"]), occurrence) in exceptions:
                continue
            finish = occurrence + duration
            if occurrence < end and finish > start:
                out.append(
                    {
                        **event,
                        "starts_at": occurrence,
                        "ends_at": finish,
                        "occurrence_start": occurrence,
                        "kind": "event",
                    }
                )
    for e in exceptions.values():
        if not e["deleted_at"] and e["starts_at"] < end and e["ends_at"] > start:
            out.append({**e, "kind": "event"})
    return out
