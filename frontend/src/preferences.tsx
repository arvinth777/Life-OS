import React, { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, title } from "./api";
import { Panel } from "./components";
import { savedFeedback } from "./feedback";
export default function Preferences({ refresh, onRefresh }: any) {
  const [records, setRecords] = useState<any[]>([]);
  const [cfg, setCfg] = useState<any>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    api("/data/settings")
      .then((rows) => {
        setRecords(rows);
        setCfg(Object.fromEntries(rows.map((r: any) => [r.key, r.value])));
      })
      .catch((e) => setError(e.message));
  }, [refresh]);
  const set = (key: string, v: any) => {
    setCfg((x: any) => ({ ...x, [key]: v }));
    setSaved(false);
  };
  const body = cfg.body || {};
  const grading = cfg.grading || { bands: [], aggregation: "credit_weighted" };
  async function save(e: any) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      for (const [key, value] of Object.entries(cfg)) {
        const row = records.find((r) => r.key === key);
        if (!row || JSON.stringify(value) !== JSON.stringify(row.value))
          await api("/data/settings" + (row ? "/" + row.id : ""), row ? "PATCH" : "POST", { key, value });
      }
      setSaved(true);
      savedFeedback("Preferences saved");
      onRefresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save}>
      <Panel title="Your day">
        <div className="form-grid">
          <label>
            Timezone
            <input
              value={cfg.timezone || ""}
              onChange={(e) => set("timezone", e.target.value)}
              placeholder="Asia/Kolkata"
              required
            />
            <small>
              IANA timezone. Streaks recalculate using local midnight.
            </small>
          </label>
          <label>
            Weak-pattern accuracy threshold (%)
            <input
              type="number"
              min="0"
              max="100"
              value={(cfg.accuracy_threshold ?? 0.6) * 100}
              onChange={(e) =>
                set("accuracy_threshold", Number(e.target.value) / 100)
              }
            />
          </label>
          <label>
            Water source
            <select value={cfg.water_source || "manual"} onChange={(e) => set("water_source", e.target.value)}>
              <option value="manual">Life OS manual entry</option>
              <option value="samsung_health">Samsung Health only</option>
            </select>
          </label>
          <label>
            Daily water goal (ml)
            <input
              type="number"
              min="1"
              value={cfg.water_goal_ml || 2000}
              onChange={(e) => set("water_goal_ml", Number(e.target.value))}
            />
          </label>
          <label>
            Daily step goal
            <input
              type="number"
              min="1"
              value={cfg.steps_goal || 8000}
              onChange={(e) => set("steps_goal", Number(e.target.value))}
            />
          </label>
        </div>
      </Panel>
      <Panel title="Body metrics & protein goal">
        <p className="muted">
          These values belong to you. Synced differences need your approval.
          Leave unknown measurements blank.
        </p>
        <div className="form-grid">
          {[
            ["weight_kg", "Body weight (kg)"],
            ["height_cm", "Height (cm)"],
            ["age", "Age (years)"],
          ].map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                type="number"
                min="1"
                step="any"
                value={body[key] ?? ""}
                onChange={(e) =>
                  set("body", {
                    ...body,
                    [key]:
                      e.target.value === "" ? null : Number(e.target.value),
                  })
                }
              />
            </label>
          ))}
          <label>
            Sex used by the BMR equation
            <select
              value={body.sex || ""}
              onChange={(e) =>
                set("body", { ...body, sex: e.target.value || null })
              }
            >
              <option value="">Not set</option>
              <option value="male">Male (+5 constant)</option>
              <option value="female">Female (−161 constant)</option>
            </select>
          </label>
          <label>
            Activity multiplier
            <input
              type="number"
              min="1"
              max="3"
              step="0.025"
              value={body.activity_multiplier ?? 1.2}
              onChange={(e) =>
                set("body", {
                  ...body,
                  activity_multiplier: Number(e.target.value),
                })
              }
            />
            <small>Editable estimate; 1.2 is the starting value.</small>
          </label>
          <label>
            Goal
            <select
              value={body.goal || "maintain"}
              onChange={(e) => set("body", { ...body, goal: e.target.value })}
            >
              <option value="maintain">Maintain</option>
              <option value="build">Build muscle</option>
              <option value="reduce">Reduce body weight</option>
            </select>
          </label>
          {["maintain", "build", "reduce"].map((goal) => (
            <label key={goal}>
              {title(goal)}: protein (g/kg)
              <input
                type="number"
                min="0.1"
                max="5"
                step="0.1"
                value={body.protein_g_per_kg?.[goal] ?? 1.6}
                onChange={(e) =>
                  set("body", {
                    ...body,
                    protein_g_per_kg: {
                      ...body.protein_g_per_kg,
                      [goal]: Number(e.target.value),
                    },
                  })
                }
              />
            </label>
          ))}
        </div>
      </Panel>
      <Panel title="What counts as showing up">
        <p className="muted">
          A day qualifies when at least one selected action happens. Each streak
          is calculated from records.
        </p>
        <div className="streak-config">
          {Object.entries(cfg.streaks || {}).map(([name, kinds]: any) => (
            <fieldset key={name}>
              <legend>{name}</legend>
              {[
                ["journal", "Journal entry saved"],
                ["attempt", "Problem attempted"],
                ["review", "Concept review completed"],
                ["workout", "Workout logged"],
              ].map(([key, label]) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={kinds.includes(key)}
                    onChange={(e) =>
                      set("streaks", {
                        ...cfg.streaks,
                        [name]: e.target.checked
                          ? [...kinds, key]
                          : kinds.filter((x: string) => x !== key),
                      })
                    }
                  />
                  {label}
                </label>
              ))}
            </fieldset>
          ))}
        </div>
      </Panel>
      <Panel title="Your grading scale">
        <label className="inline-label">
          GPA aggregation
          <select
            value={grading.aggregation}
            onChange={(e) =>
              set("grading", { ...grading, aggregation: e.target.value })
            }
          >
            <option value="credit_weighted">
              Weight each course by credits
            </option>
            <option value="equal_course">Weight every course equally</option>
          </select>
        </label>
        <p className="muted">
          Add grade bands from your institution. A percentage receives the
          highest matching minimum. Course and term percentages work even
          without GPA bands.
        </p>
        {grading.bands.map((b: any, i: number) => (
          <div className="grade-band" key={i}>
            <label>
              Minimum %
              <input
                type="number"
                min="0"
                max="100"
                value={b.minimum}
                onChange={(e) =>
                  set("grading", {
                    ...grading,
                    bands: grading.bands.map((x: any, j: number) =>
                      j === i ? { ...x, minimum: Number(e.target.value) } : x,
                    ),
                  })
                }
              />
            </label>
            <label>
              Label
              <input
                value={b.label}
                onChange={(e) =>
                  set("grading", {
                    ...grading,
                    bands: grading.bands.map((x: any, j: number) =>
                      j === i ? { ...x, label: e.target.value } : x,
                    ),
                  })
                }
                required
              />
            </label>
            <label>
              GPA points
              <input
                type="number"
                step="any"
                value={b.points}
                onChange={(e) =>
                  set("grading", {
                    ...grading,
                    bands: grading.bands.map((x: any, j: number) =>
                      j === i ? { ...x, points: Number(e.target.value) } : x,
                    ),
                  })
                }
              />
            </label>
            <button
              type="button"
              className="icon"
              aria-label="Remove grade band"
              onClick={() =>
                set("grading", {
                  ...grading,
                  bands: grading.bands.filter((_: any, j: number) => j !== i),
                })
              }
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            set("grading", {
              ...grading,
              bands: [...grading.bands, { minimum: 0, label: "", points: 0 }],
            })
          }
        >
          <Plus size={16} />
          Grade band
        </button>
      </Panel>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {saved && (
        <p className="notice" role="status">
          Preferences saved.
        </p>
      )}
      <div className="form-actions">
        <button className="primary" disabled={busy}>
          {busy ? "Saving…" : "Save preferences"}
        </button>
      </div>
    </form>
  );
}
