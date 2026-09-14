import React, { useEffect, useRef, useState } from "react";
import { Plus, Droplets, Check, X } from "lucide-react";
import { api, fmt, title, localInput } from "./api";
import {
  Panel,
  Metric,
  Records,
  Tabs,
  Editor,
  Empty,
  Modal,
} from "./components";
import { WaterTracker } from "./WaterTracker";
import { ValueBar } from "./feedback";
export function Physical(p: any) {
  const [tab, setTab] = useState("overview");
  const [data, setData] = useState<any>();
  const [workouts, setWorkouts] = useState<any[]>([]);
  const [selection, setSelection] = useState("week");
  const [volume, setVolume] = useState<any[]>([]);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [edit, setEdit] = useState<any>();
  const [health, setHealth] = useState(false);
  const [reminders, setReminders] = useState<any[]>([]);
  const [error, setError] = useState("");
  const samsungWater = p.settings?.water_source === "samsung_health";
  useEffect(() => {
    Promise.all([
      api("/dashboard"),
      api("/data/workouts"),
      api("/data/metric_suggestions"),
      api("/reminders").catch(() => []),
    ])
      .then(([a, b, c, d]) => {
        setData(a);
        setWorkouts(b);
        setSuggestions(c);
        setReminders(d.filter((r: any) => r.kind === "water"));
      })
      .catch((e) => setError(e.message));
  }, [p.refresh]);
  useEffect(() => {
    api(
      "/physical/volume?" +
        (selection === "week" ? "week=true" : "workout_id=" + selection),
    )
      .then(setVolume)
      .catch((e) => setError(e.message));
  }, [selection, p.refresh]);
  return (
    <>
      {error && <p className="error">{error}</p>}
      <Tabs
        active={tab}
        onChange={setTab}
        items={[
          ["overview", "Today & training"],
          ["watch", "Watch data"],
          ["workouts", "Workouts"],
          ["sets", "Sets"],
          ["health", "Health records"],
          ["library", "Exercise library"],
          ["mapping", "Muscle mappings"],
        ]}
      />
      {tab === "overview" ? (
        <>
          <div className="daily-health">
            <div>
              <WaterTracker
                samsungOnly={samsungWater}
                receivedAt={data?.water_received_at}
                total={data ? (data.metrics.water || 0) : undefined}
                goal={Number(p.settings?.water_goal_ml) || 2000}
                refresh={async () => { setData(await api("/dashboard")); }}
                onCustom={() => setHealth(true)}
                onGoal={() => p.navigate("settings")}
              />
              {data && (data.metrics.water || 0) < (Number(p.settings?.water_goal_ml) || 2000) && reminders.map((r) => (
                <div className="water-reminder" key={r.id}>
                  <span>{r.title}</span>
                  <button className="text-button" onClick={async () => {
                    try {
                      await api("/data/reminder_dismissals", "POST", { rule_id: r.id, occurrence_key: r.occurrence_key });
                      setReminders((items) => items.filter((item) => item.id !== r.id));
                    } catch (e) { setError(e.message); }
                  }}>Dismiss</button>
                </div>
              ))}
            </div>
            <section className="daily-readings" aria-labelledby="readings-heading">
              <div className="section-head">
                <h2 id="readings-heading">Daily readings</h2>
                <button onClick={() => setHealth(true)}><Plus size={16} />Health reading</button>
              </div>
              <div className="physical-stats">
                <Metric label="Steps" value={data?.metrics.steps ?? "—"} />
                <Metric label="Sleep" value={data?.metrics.sleep ?? "—"} unit="hours" />
                <Metric label="Activity" value={data?.metrics.activity ?? "—"} unit="min" />
              </div>
              <p className="muted">Today’s recorded totals. Add a reading whenever you need to.</p>
            </section>
          </div>
          <div className="training-heading">
            <h2>Training</h2>
            <button className="primary" onClick={() => setEdit({ table: "workouts" })}>
              <Plus size={16} />Log workout
            </button>
          </div>
          <div className="physical-layout">
            <Panel
              title="Muscles trained"
              action={
                <select
                  aria-label="Training period"
                  value={selection}
                  onChange={(e) => setSelection(e.target.value)}
                >
                  <option value="week">This week</option>
                  {workouts.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.title} · {fmt(w.performed_at)}
                    </option>
                  ))}
                </select>
              }
            >
              <BodyMap volume={volume} />
              <p className="muted">
                Intensity shows weighted sets, using each exercise’s muscle
                contribution. It is a training-volume view, not an injury or
                recovery estimate.
              </p>
            </Panel>
            <div>
              <Panel title="Your daily targets">
                {data?.nutrition.configured ? (
                  <>
                    <Metric
                      label="Protein goal"
                      value={data.nutrition.protein_g}
                      unit="g / day"
                    />
                    <div className="target-row">
                      <span>Estimated BMR</span>
                      <strong>{data.nutrition.bmr} kcal</strong>
                    </div>
                    <div className="target-row">
                      <span>Estimated maintenance</span>
                      <strong>{data.nutrition.maintenance} kcal</strong>
                    </div>
                    <p className="muted">
                      Mifflin–St Jeor, your activity multiplier, and your goal’s
                      protein grams per kilogram.
                    </p>
                  </>
                ) : (
                  <Empty
                    text="Add your body metrics in Settings to calculate your targets."
                    action={
                      <button onClick={() => p.navigate("settings")}>
                        Set body metrics
                      </button>
                    }
                  />
                )}
              </Panel>
              <Panel title="Muscle volume">
                {volume.some((g) => g.volume > 0) ? (
                  volume
                    .filter((g) => g.volume > 0)
                    .map((g) => (
                      <div key={g.id} className="volume-row">
                        <div className="target-row"><span>{g.name}</span><strong>{g.volume.toFixed(1)} sets</strong></div>
                        <ValueBar ratio={g.volume / Math.max(1, ...volume.map((m) => m.volume))} />
                      </div>
                    ))
                ) : (
                  <p className="muted">Log sets to light up the map.</p>
                )}
              </Panel>
            </div>
          </div>
          {suggestions
            .filter((x) => x.status === "pending")
            .map((x) => (
              <div className="notice" key={x.id}>
                A synced reading suggests {title(x.setting_key)} ={" "}
                {JSON.stringify(x.proposed_value)}. Your saved metric has not
                changed.
                <div className="actions">
                  {["accept", "reject"].map((action) => (
                    <button
                      key={action}
                      onClick={() =>
                        api("/suggestions/" + x.id + "/" + action, "POST")
                          .then(p.onRefresh)
                          .catch((e) => setError(e.message))
                      }
                    >
                      {title(action)}
                    </button>
                  ))}
                </div>
              </div>
            ))}
        </>
      ) : tab === "watch" ? (
        <WatchReadings refresh={p.refresh} />
      ) : tab === "health" ? (
        <>
          <button className="primary" onClick={() => setHealth(true)}>
            <Plus size={16} />
            Manual reading
          </button>
          <Records
            {...p}
            table="health_records"
            columns={["metric", "value", "unit", "recorded_at", "source"]}
          />
        </>
      ) : tab === "library" ? (
        <>
          <Records {...p} table="exercises" />
          <Records {...p} table="muscle_groups" />
        </>
      ) : (
        <Records
          {...p}
          table={
            tab === "workouts"
              ? "workouts"
              : tab === "sets"
                ? "workout_sets"
                : "exercise_muscles"
          }
          actions={
            tab === "workouts"
              ? (w: any) => (
                  <button
                    onClick={() =>
                      setEdit({
                        table: "workout_sets",
                        initial: { workout_id: w.id },
                      })
                    }
                  >
                    <Plus size={15} />
                    Set
                  </button>
                )
              : undefined
          }
        />
      )}
      {edit && (
        <Editor
          table={edit.table}
          schema={p.schema}
          initial={edit.initial}
          onSaved={p.onRefresh}
          onClose={() => setEdit(undefined)}
        />
      )}
      {health && (
        <HealthEntry samsungWater={samsungWater} onClose={() => setHealth(false)} onSaved={p.onRefresh} />
      )}
    </>
  );
}
function WatchReadings({ refresh }: any) {
  const [data, setData] = useState<any>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const [progress, setProgress] = useState("");
  const stop = useRef(false);
  async function load() {
    setBusy(true); setError("");
    try { setData(await api("/physical/readings")); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); return () => { stop.current = true; }; }, [refresh]);
  async function importCloud() {
    stop.current = false; setImporting(true); setError("");
    let received = 0;
    try {
      while (!stop.current) {
        const result = await api("/integrations/samsung/pull", "POST");
        received += result.accepted || 0;
        setProgress(`${received.toLocaleString()} readings received. ${result.message}`);
        await load();
        if (!["running", "unavailable"].includes(result.state)) break;
      }
    } catch (e) { setError(e.message); }
    finally { setImporting(false); }
  }
  const readings = Object.fromEntries((data?.readings || []).map((r: any) => [r.metric, r]));
  return <Panel title="Samsung Health readings" action={<button onClick={load} disabled={busy}>{busy ? "Refreshing…" : "Refresh readings"}</button>}>
    <p className="muted">Latest received readings. Availability depends on what Samsung Health shares with your phone bridge. Record history is in Health records.</p>
    {data?.samsung_connected && <div className="form-actions">
      <button onClick={importing ? () => { stop.current = true; } : importCloud}>{importing ? "Pause after this batch" : "Import / resume Samsung history"}</button>
    </div>}
    {progress && <p role="status">{progress}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {!data ? <p>Loading readings…</p> : <div className="table-wrap"><table>
      <thead><tr><th>Reading</th><th>Latest value</th><th>Recorded</th></tr></thead>
      <tbody>{data.supported.map((item: any) => {
        const r: any = readings[item.metric];
        return <tr key={item.metric}><td>{title(item.metric)}</td><td>{r ? `${Number(r.value).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${r.unit}` : "No data received"}</td><td>{r ? fmt(r.recorded_at) : "—"}</td></tr>;
      })}<tr><td>Stress</td><td colSpan={2}>{data.samsung_connected ? "See Samsung raw fields below when available; scale not yet verified" : "Samsung cloud connection needed · Not connected"}</td></tr></tbody>
    </table></div>}
    {data?.readings.some((r: any) => r.metric.startsWith("samsung_raw/")) && <details open>
      <summary>Samsung cloud · Raw fields</summary>
      <p className="muted">These are Samsung’s numeric source fields. Their scales and meanings have not been verified. They do not change your daily totals or body settings.</p>
      <div className="table-wrap"><table><thead><tr><th>Source field</th><th>Raw value</th><th>Recorded</th></tr></thead><tbody>
        {data.readings.filter((r: any) => r.metric.startsWith("samsung_raw/")).map((r: any) => <tr key={r.metric}><td>{r.metric.replace("samsung_raw/", "").replaceAll("/", " · ")}</td><td>{r.value}</td><td>{fmt(r.recorded_at)}</td></tr>)}
      </tbody></table></div>
    </details>}
  </Panel>;
}

function HealthEntry({ onClose, onSaved, samsungWater }: any) {
  const [metric, setMetric] = useState(samsungWater ? "steps" : "water");
  const [value, setValue] = useState(samsungWater ? "" : "250");
  const [unit, setUnit] = useState(samsungWater ? "count" : "ml");
  const [recorded, setRecorded] = useState(localInput());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const units: any = {
    water: "ml",
    steps: "count",
    sleep: "hours",
    activity: "minutes",
    weight: "kg",
    height: "cm",
    heart_rate: "bpm",
    hrv: "ms",
    stress: "score",
    body_fat: "percent",
  };
  return (
    <Modal title="Record a health reading" onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await api("/ingest", "POST", [
              {
                metric,
                value: Number(value),
                unit,
                recorded_at: new Date(recorded).toISOString(),
                source: "manual",
                device: "owner",
                external_id: crypto.randomUUID(),
              },
            ]);
            onSaved();
            onClose();
          } catch (e) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="form-grid">
          <label>
            Metric
            <select
              value={metric}
              onChange={(e) => {
                setMetric(e.target.value);
                setUnit(units[e.target.value]);
              }}
            >
              {Object.keys(units).filter((k) => !samsungWater || k !== "water").map((k) => (
                <option key={k} value={k}>
                  {title(k)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Value ({unit})
            <input
              type="number"
              min="0"
              step="any"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              required
            />
          </label>
          <label className="wide">
            Recorded at
            <input
              type="datetime-local"
              value={recorded}
              onChange={(e) => setRecorded(e.target.value)}
              required
            />
            <small>
              Enter in your browser’s local timezone. Record increments, not
              repeatedly overlapping daily totals.
            </small>
          </label>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="form-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button disabled={busy} className="primary">
            {busy ? "Saving…" : "Save reading"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
const paths: any = {
  chest: [
    "M71 65 Q85 57 98 64 L98 90 Q82 94 72 84Z",
    "M102 64 Q116 57 129 65 L128 84 Q115 94 102 90Z",
  ],
  shoulders: [
    "M69 61 Q49 65 48 85 L65 88 73 69Z",
    "M131 61 Q151 65 152 85 L135 88 127 69Z",
  ],
  biceps: ["M49 90 L64 92 61 125 46 127Z", "M136 92 L151 90 154 127 139 125Z"],
  abs: ["M80 96 L98 98 98 142 84 143Z", "M102 98 L120 96 116 143 102 142Z"],
  quads: [
    "M76 161 L98 161 96 225 75 224 69 192Z",
    "M102 161 L124 161 131 192 125 224 104 225Z",
  ],
  calves: [
    "M76 239 L95 239 92 280 79 291 73 265Z",
    "M105 239 L124 239 127 265 121 291 108 280Z",
  ],
  upper_back: ["M72 64 L100 58 128 64 120 92 80 92Z"],
  lats: ["M73 91 L96 97 96 130 81 143Z", "M104 97 L127 91 119 143 104 130Z"],
  triceps: ["M49 91 L64 92 61 125 46 127Z", "M136 92 L151 91 154 127 139 125Z"],
  lower_back: ["M88 132 L112 132 117 156 83 156Z"],
  glutes: [
    "M77 157 Q88 151 98 159 L97 184 Q82 191 74 179Z",
    "M102 159 Q112 151 123 157 L126 179 Q118 191 103 184Z",
  ],
  hamstrings: [
    "M74 189 L97 190 94 228 76 228Z",
    "M103 190 L126 189 124 228 106 228Z",
  ],
};
function BodyMap({ volume }: any) {
  const max = Math.max(1, ...volume.map((g: any) => g.volume));
  return (
    <div className="body-maps">
      {["front", "back"].map((view) => (
        <figure key={view}>
          <svg
            viewBox="0 0 200 330"
            role="img"
            aria-label={view + " muscle volume map"}
          >
            <g className="body-base">
              <ellipse cx="100" cy="31" rx="20" ry="25" />
              <path d="M87 52L113 52 128 60 149 74 162 137 157 166 145 165 130 115 126 154 134 186 128 236 130 283 126 311 107 311 100 235 93 311 74 311 70 283 72 236 66 186 74 154 70 115 55 165 43 166 38 137 51 74 72 60Z" />
            </g>
            {volume
              .filter((g) => g.view === view || g.view === "both")
              .map((g) => (
                <g
                  key={`${g.map_key}-${g.volume}`}
                  data-muscle={g.map_key}
                  data-volume={g.volume}
                  className={g.volume > 0 ? "muscle active" : "muscle"}
                  style={{
                    opacity: g.volume > 0 ? 0.35 + (0.65 * g.volume) / max : 1,
                  }}
                >
                  <title>
                    {g.name}: {g.volume.toFixed(1)} weighted sets
                  </title>
                  {(paths[g.map_key] || []).map((d: string, i: number) => (
                    <path d={d} key={i} />
                  ))}
                </g>
              ))}
          </svg>
          <figcaption>{title(view)}</figcaption>
        </figure>
      ))}
    </div>
  );
}
