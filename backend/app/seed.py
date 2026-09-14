import uuid
import json
from pathlib import Path
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from .db import engine
from . import schema as s
from .curriculum import PRIMER, FOUNDATIONS, PATTERNS, STUBS


def ident(key):
    return uuid.uuid5(uuid.NAMESPACE_URL, "life-os/" + key)


def add(conn, table, seed_key, **values):
    uid = ident(seed_key)
    conn.execute(insert(table).values(id=uid, **values).on_conflict_do_nothing())
    return uid


def seed():
    with engine.begin() as conn:
        defaults = {
            "timezone": "UTC",
            "water_goal_ml": 2000,
            "water_source": "manual",
            "samsung_cloud": {"enabled": False, "interval_minutes": 60},
            "steps_goal": 8000,
            "accuracy_threshold": 0.6,
            "streaks": {
                "Journal": ["journal"],
                "DSA": ["attempt", "review"],
                "Workout": ["workout"],
            },
            "body": {
                "weight_kg": None,
                "height_cm": None,
                "age": None,
                "sex": None,
                "activity_multiplier": 1.2,
                "goal": "maintain",
                "protein_g_per_kg": {"maintain": 1.6, "build": 1.8, "reduce": 2.0},
            },
            "grading": {"bands": [], "aggregation": "credit_weighted"},
            "llm": {"provider": "openai", "model": "gpt-4.1-mini"},
            "google": {"calendar_id": "", "transport": "poll", "poll_minutes": 15},
            "reflection_schedule": {"interval_days": 7},
        }
        for key, value in defaults.items():
            add(conn, s.settings, "setting/" + key, key=key, value=value)
        primer = add(
            conn,
            s.curriculum_modules,
            "python",
            title="Python, from zero",
            position=0,
            description="The small set of Python tools these patterns need.",
        )
        for i, (title, body) in enumerate(PRIMER):
            add(
                conn,
                s.lessons,
                "primer/" + str(i),
                module_id=primer,
                title=title,
                body=body,
                position=i,
            )
        foundations = add(
            conn,
            s.curriculum_modules,
            "foundations",
            title="Arrays & strings",
            position=1,
            description="Positions, boundaries, complexity and correctness.",
        )
        add(
            conn,
            s.lessons,
            "foundations/lesson",
            module_id=foundations,
            title="Think in sequences",
            body=FOUNDATIONS,
            position=0,
        )
        patterns = add(
            conn,
            s.curriculum_modules,
            "patterns",
            title="Five essential patterns",
            position=2,
            description="Learn a move, trace it, then practice it.",
        )
        for i, p in enumerate(PATTERNS):
            lesson = add(
                conn,
                s.lessons,
                "patternlesson/" + str(i),
                module_id=patterns,
                title=p["title"],
                body=p["explanation"],
                position=i,
            )
            pattern = add(
                conn,
                s.patterns,
                "pattern/" + str(i),
                lesson_id=lesson,
                title=p["title"],
                position=i,
                explanation=p["explanation"],
                walkthrough=p["walkthrough"],
            )
            for j, problem in enumerate(p["problems"]):
                add(
                    conn,
                    s.problems,
                    "problem/" + str(i) + "/" + str(j),
                    pattern_id=pattern,
                    position=j,
                    difficulty=["Start here", "Build confidence", "Stretch"][j],
                    **problem
                )
        later = add(
            conn,
            s.curriculum_modules,
            "later",
            title="Beyond the foundations",
            position=3,
            description="An editable outline. These lessons are visibly incomplete.",
        )
        for i, title in enumerate(STUBS):
            add(
                conn,
                s.lessons,
                "stub/" + str(i),
                module_id=later,
                title=title,
                position=i,
                body="",
                incomplete=True,
            )
        muscle_names = [
            ("Chest", "chest", "front"),
            ("Shoulders", "shoulders", "both"),
            ("Biceps", "biceps", "front"),
            ("Abdominals", "abs", "front"),
            ("Quadriceps", "quads", "front"),
            ("Calves", "calves", "both"),
            ("Upper back", "upper_back", "back"),
            ("Lats", "lats", "back"),
            ("Triceps", "triceps", "back"),
            ("Lower back", "lower_back", "back"),
            ("Glutes", "glutes", "back"),
            ("Hamstrings", "hamstrings", "back"),
        ]
        muscle_ids = {
            key: add(
                conn,
                s.muscle_groups,
                "muscle/" + key,
                name=name,
                map_key=key,
                view=view,
            )
            for name, key, view in muscle_names
        }
        exercises = [
            (
                "Push-up",
                "Keep your trunk steady; lower with control and press away from the floor.",
                {"chest": 1, "triceps": 0.5, "shoulders": 0.5},
            ),
            (
                "Squat",
                "Use a comfortable stance, brace, bend hips and knees, then stand with control.",
                {"quads": 1, "glutes": 0.5},
            ),
            (
                "Romanian deadlift",
                "Soften knees, move hips back with a steady spine, then extend hips.",
                {"hamstrings": 1, "glutes": 0.5, "lower_back": 0.25},
            ),
            (
                "Row",
                "Pull toward your torso without jerking; lower under control.",
                {"upper_back": 1, "lats": 0.5, "biceps": 0.5},
            ),
            (
                "Overhead press",
                "Brace your trunk and press upward through a comfortable range.",
                {"shoulders": 1, "triceps": 0.5},
            ),
            (
                "Lat pulldown",
                "Pull elbows down beside your body; return slowly.",
                {"lats": 1, "biceps": 0.5},
            ),
            (
                "Biceps curl",
                "Keep upper arms still while bending and extending elbows.",
                {"biceps": 1},
            ),
            (
                "Triceps extension",
                "Extend elbows through a comfortable range without swinging.",
                {"triceps": 1},
            ),
            ("Calf raise", "Lift heels, pause, then lower slowly.", {"calves": 1}),
            (
                "Crunch",
                "Lift shoulders using the abdomen without pulling on the neck.",
                {"abs": 1},
            ),
        ]
        for name, instructions, mapping in exercises:
            ex = add(
                conn,
                s.exercises,
                "exercise/" + name,
                name=name,
                instructions=instructions,
            )
            for muscle, value in mapping.items():
                add(
                    conn,
                    s.exercise_muscles,
                    "mapping/" + name + "/" + muscle,
                    exercise_id=ex,
                    muscle_id=muscle_ids[muscle],
                    contribution=value,
                )
        for kind, title, cfg in [
            ("water", "Pause for water", {"target_ml": 2000}),
            ("task_due", "Review today’s tasks", {}),
            ("journal", "Make a little space to reflect", {"hour": 18}),
        ]:
            add(
                conn,
                s.reminder_rules,
                "reminder/" + kind,
                kind=kind,
                title=title,
                config=cfg,
            )
        for i, (title, body) in enumerate(
            [
                (
                    "Notice a pattern",
                    "What repeated this week? Describe one moment, your response, and a smaller response you could try next time.",
                ),
                (
                    "Keep what works",
                    "Which action helped you feel capable this week? What made it possible, and when will you repeat it?",
                ),
                (
                    "Practice a trait",
                    "Choose a trait you care about. What would one observable act of that trait look like this week?",
                ),
            ]
        ):
            add(
                conn,
                s.reflection_prompts,
                "prompt/" + str(i),
                title=title,
                body=body,
                interval_days=7,
            )
        mapping = {
            "records_path": "records",
            "fields": {
                key: {"path": key}
                for key in (
                    "metric",
                    "value",
                    "unit",
                    "recorded_at",
                    "source",
                    "device",
                    "external_id",
                )
            },
        }
        add(
            conn,
            s.ingestion_mappings,
            "mapping/default",
            name="default",
            mapping=mapping,
        )
        add(
            conn,
            s.ingestion_mappings,
            "mapping/hc-webhook-samsung",
            name="hc-webhook-samsung",
            mapping=json.loads(
                (Path(__file__).parent / "data/hc_webhook_v1_9_20.json").read_text()
            ),
        )


if __name__ == "__main__":
    seed()
    print("Reference data seeded; existing rows were preserved.")
