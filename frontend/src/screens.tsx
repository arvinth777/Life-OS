import React, { useEffect, useState } from "react";
import {
  Plus,
  Pencil,
  Trash2,
  Sparkles,
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  Upload,
} from "lucide-react";
import { api, base, fmt, title } from "./api";
import {
  Editor,
  Panel,
  Metric,
  Empty,
  Records,
  Tabs,
  Trend,
} from "./components";
import Preferences from "./preferences";
import { downloadBackup, restoreBackup } from "./backup";
export function Journal(p: any) {
  const [entries, setEntries] = useState<any[]>([]);
  const [feedback, setFeedback] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [edit, setEdit] = useState<any>(undefined);
  const [selected, setSelected] = useState("");
  const [status, setStatus] = useState<any>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => {
      Promise.all([
        api("/data/journal_entries?q=" + encodeURIComponent(query)),
        api("/data/ai_feedback"),
        api("/integrations/status"),
      ])
        .then(([a, b, c]) => {
          setEntries(a);
          setFeedback(b);
          setStatus(c);
        })
        .catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(timer);
  }, [query, p.refresh]);
  const current = entries.find((e) => e.id === selected) || entries[0];
  return (
    <>
      <div className="toolbar">
        <label className="search-label">
          Search entries
          <input
            value={query}
            placeholder="Words, phrases, or ideas…"
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <button className="primary" onClick={() => setEdit(null)}>
          <Plus size={16} />
          New entry
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="journal-layout">
        <div className="entry-list">
          {entries.map((e) => (
            <button
              key={e.id}
              className={e.id === current?.id ? "active" : ""}
              onClick={() => setSelected(e.id)}
            >
              <small>{fmt(e.created_at)}</small>
              <strong>{e.title}</strong>
              <p>{e.body.slice(0, 95)}</p>
              <span>{e.tags.join(" · ")}</span>
            </button>
          ))}
        </div>
        <article className="reading-surface">
          {current ? (
            <>
              <div className="section-head">
                <span className="eyebrow">{fmt(current.created_at)}</span>
                <div className="actions">
                  <button onClick={() => setEdit(current)}>
                    <Pencil size={15} />
                    Edit
                  </button>
                  <button
                    className="icon"
                    aria-label="Delete entry"
                    onClick={async () => {
                      if (confirm("Delete this entry and its feedback?")) {
                        await api(
                          "/data/journal_entries/" + current.id,
                          "DELETE",
                        )
                          .then(p.onRefresh)
                          .catch((e) => setError(e.message));
                      }
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              <h2>{current.title}</h2>
              <div className="prose">{current.body}</div>
              <div className="ai-section">
                <button
                  disabled={!status.llm_configured || busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await api("/ai/journal/" + current.id, "POST", {});
                      p.onRefresh();
                    } catch (e) {
                      setError(e.message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <Sparkles size={16} />
                  {busy ? "Thinking…" : "Get AI feedback"}
                </button>
                {!status.llm_configured && (
                  <small>
                    AI is not configured. Add a key in Settings when you want
                    feedback.
                  </small>
                )}
                {feedback
                  .filter((f) => f.entry_id === current.id)
                  .map((f) => (
                    <div className="feedback" key={f.id}>
                      <div className="section-head">
                        <small>{fmt(f.created_at)}</small>
                        <button
                          className="icon"
                          aria-label="Delete feedback"
                          onClick={() =>
                            api("/feedback/" + f.id, "DELETE")
                              .then(p.onRefresh)
                              .catch((e) => setError(e.message))
                          }
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                      <div className="prose">{f.body}</div>
                    </div>
                  ))}
              </div>
            </>
          ) : (
            <Empty text="Start with what’s on your mind. Your first entry belongs here." />
          )}
        </article>
      </div>
      {edit !== undefined && (
        <Editor
          table="journal_entries"
          schema={p.schema}
          row={edit}
          onClose={() => setEdit(undefined)}
          onSaved={p.onRefresh}
        />
      )}
    </>
  );
}
export function Personality(p: any) {
  const [tab, setTab] = useState("reflect");
  const [traits, setTraits] = useState<any[]>([]);
  const [ratings, setRatings] = useState<any[]>([]);
  const [prompts, setPrompts] = useState<any[]>([]);
  const [reflections, setReflections] = useState<any[]>([]);
  const [trait, setTrait] = useState("");
  const [edit, setEdit] = useState<any>();
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all(
      ["traits", "trait_ratings", "reflection_prompts", "reflections"].map(
        (x) => api("/data/" + x),
      ),
    )
      .then(([a, b, c, d]) => {
        setTraits(a);
        setRatings(b);
        setPrompts(c);
        setReflections(d);
      })
      .catch((e) => setError(e.message));
  }, [p.refresh]);
  const selected = trait || traits[0]?.id;
  return (
    <>
      {error && <p className="error">{error}</p>}
      <Tabs
        active={tab}
        onChange={setTab}
        items={[
          ["reflect", "Reflection"],
          ["ratings", "Trait ratings"],
          ["traits", "Your traits"],
          ["prompts", "Prompt schedule"],
        ]}
      />
      {tab === "reflect" ? (
        <>
          <div className="prompt-grid">
            {prompts
              .filter((pr) => pr.enabled)
              .map((pr) => {
                const last = reflections
                  .filter((r) => r.prompt_id === pr.id)
                  .sort((a, b) =>
                    b.recorded_at.localeCompare(a.recorded_at),
                  )[0];
                const due =
                  !last ||
                  Date.now() - new Date(last.recorded_at).getTime() >=
                    pr.interval_days * 86400000;
                return (
                  <section key={pr.id} className="prompt">
                    <span className="eyebrow">
                      Every {pr.interval_days} days ·{" "}
                      {due ? "Ready to reflect" : "Next reflection later"}
                    </span>
                    <h2>{pr.title}</h2>
                    <p>{pr.body}</p>
                    <button
                      onClick={() =>
                        setEdit({ prompt_id: pr.id, domain: "personality" })
                      }
                    >
                      Reflect
                      <ArrowRight size={16} />
                    </button>
                  </section>
                );
              })}
          </div>
          <Records
            {...p}
            table="reflections"
            filter={(r: any) => r.domain === "personality"}
            initial={{ domain: "personality" }}
            columns={["body", "recorded_at"]}
          />
        </>
      ) : tab === "ratings" ? (
        <>
          <Panel
            title="Traits over time"
            action={
              <select
                aria-label="Chart trait"
                value={selected || ""}
                onChange={(e) => setTrait(e.target.value)}
              >
                {traits.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                    {t.retired ? " (retired)" : ""}
                  </option>
                ))}
              </select>
            }
          >
            <Trend
              values={ratings
                .filter((r) => r.trait_id === selected)
                .sort((a, b) => a.recorded_at.localeCompare(b.recorded_at))
                .map((r) => r.score)}
              min={1}
              max={10}
              label="Self-rating, oldest to newest"
            />
          </Panel>
          <Records {...p} table="trait_ratings" />
        </>
      ) : (
        <Records
          {...p}
          table={tab === "traits" ? "traits" : "reflection_prompts"}
        />
      )}
      {edit && (
        <Editor
          table="reflections"
          schema={p.schema}
          initial={edit}
          onSaved={p.onRefresh}
          onClose={() => setEdit(undefined)}
        />
      )}
    </>
  );
}
export function Academic(p: any) {
  const [tab, setTab] = useState("overview");
  const [data, setData] = useState<any>({ courses: [], terms: [] });
  const [error, setError] = useState("");
  useEffect(() => {
    api("/academics/summary")
      .then(setData)
      .catch((e) => setError(e.message));
  }, [p.refresh]);
  return (
    <>
      {error && <p className="error">{error}</p>}
      <Tabs
        active={tab}
        onChange={setTab}
        items={[
          "overview",
          "terms",
          "courses",
          "assignments",
          "grade_components",
          "grades",
          "goals",
          "reflections",
        ].map((x) => [x, title(x)])}
      />
      {tab === "overview" ? (
        <>
          <div className="summary-grid">
            {data.terms.map((t: any) => (
              <Panel key={t.id} title={t.name}>
                <div className="stats-pair">
                  <Metric
                    label="Term average"
                    value={t.average?.toFixed(1) ?? "—"}
                    unit="%"
                  />
                  <Metric
                    label="Configured GPA"
                    value={t.gpa?.toFixed(2) ?? "—"}
                  />
                </div>
              </Panel>
            ))}
          </div>
          <Panel title="Course progress">
            {data.courses.length ? (
              data.courses.map((c: any) => (
                <div className="course-row" key={c.id}>
                  <div>
                    <strong>{c.name}</strong>
                    <small>
                      {c.credits} credits · {(c.coverage * 100).toFixed(0)}% of
                      component weight graded
                    </small>
                  </div>
                  <strong>
                    {c.average?.toFixed(1) ?? "—"}
                    <small>% {c.grade || ""}</small>
                  </strong>
                </div>
              ))
            ) : (
              <Empty text="Add a term, then your courses, to start tracking." />
            )}
          </Panel>
          <p className="muted">
            Averages normalize across graded components. Set your own grade
            bands and GPA weighting in Settings.
          </p>
        </>
      ) : (
        <Records
          key={tab}
          {...p}
          table={tab}
          filter={
            ["goals", "reflections"].includes(tab)
              ? (r: any) => r.domain === "academic"
              : undefined
          }
          initial={
            ["goals", "reflections"].includes(tab) ? { domain: "academic" } : {}
          }
        />
      )}
    </>
  );
}
export function Work(p: any) {
  const [tab, setTab] = useState("projects");
  return (
    <>
      <Tabs
        active={tab}
        onChange={setTab}
        items={[
          ["projects", "Projects"],
          ["tasks", "Project tasks"],
          ["work_notes", "Notes"],
          ["goals", "Career goals"],
          ["reflections", "Reflections"],
          ["custom_field_definitions", "Custom fields"],
        ]}
      />
      <Records
        key={tab}
        {...p}
        table={tab}
        filter={
          ["goals", "reflections"].includes(tab)
            ? (r: any) => r.domain === "career"
            : tab === "tasks"
              ? (r: any) => !!r.project_id
              : undefined
        }
        initial={
          ["goals", "reflections"].includes(tab) ? { domain: "career" } : {}
        }
        actions={
          tab === "tasks"
            ? (r: any) =>
                r.status !== "done" && (
                  <Complete task={r} onRefresh={p.onRefresh} />
                )
            : undefined
        }
      />
    </>
  );
}
function Complete({ task, onRefresh }: any) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <>
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await api("/tasks/" + task.id + "/complete", "POST");
            onRefresh();
          } catch (e) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Check size={16} />
        Complete
      </button>
      {error && <small className="error">{error}</small>}
    </>
  );
}
export function Tasks(p: any) {
  const [tab, setTab] = useState("open");
  return (
    <>
      <Tabs
        active={tab}
        onChange={setTab}
        items={[
          ["open", "Open tasks"],
          ["done", "Completed"],
          ["recurring", "Recurring"],
          ["custom", "Custom fields"],
        ]}
      />
      {tab === "custom" ? (
        <Records {...p} table="custom_field_definitions" />
      ) : (
        <Records
          {...p}
          table="tasks"
          columns={["title", "due_at", "priority", "parent_id", "rrule"]}
          filter={(r: any) =>
            tab === "recurring"
              ? !!r.rrule && r.status !== "done"
              : tab === "done"
                ? r.status === "done"
                : r.status !== "done"
          }
          actions={(r: any) =>
            r.status !== "done" && <Complete task={r} onRefresh={p.onRefresh} />
          }
        />
      )}
      <p className="muted">
        Recurring tasks create their next instance when completed. Finish
        subtasks before their parent.
      </p>
    </>
  );
}
export function Calendar(p: any) {
  const [tab, setTab] = useState("agenda");
  const [month, setMonth] = useState(
    () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const [agenda, setAgenda] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [edit, setEdit] = useState(false);
  useEffect(() => {
    const end = new Date(month.getFullYear(), month.getMonth() + 1, 1);
    api(
      "/calendar/agenda?start=" +
        encodeURIComponent(month.toISOString()) +
        "&end=" +
        encodeURIComponent(end.toISOString()),
    )
      .then(setAgenda)
      .catch((e) => setError(e.message));
  }, [month, p.refresh]);
  return (
    <>
      <Tabs
        active={tab}
        onChange={setTab}
        items={[
          ["agenda", "Month agenda"],
          ["events", "Events & recurrence"],
        ]}
      />
      {tab === "agenda" ? (
        <Panel
          title={month.toLocaleDateString(undefined, {
            month: "long",
            year: "numeric",
          })}
          action={
            <div className="actions">
              <button
                className="icon"
                aria-label="Previous month"
                onClick={() =>
                  setMonth(
                    new Date(month.getFullYear(), month.getMonth() - 1, 1),
                  )
                }
              >
                <ChevronLeft size={18} />
              </button>
              <button
                className="icon"
                aria-label="Next month"
                onClick={() =>
                  setMonth(
                    new Date(month.getFullYear(), month.getMonth() + 1, 1),
                  )
                }
              >
                <ChevronRight size={18} />
              </button>
              <button onClick={() => setEdit(true)}>
                <Plus size={16} />
                Event
              </button>
            </div>
          }
        >
          {error && <p className="error">{error}</p>}
          {agenda.length ? (
            agenda.map((e: any, i: number) => (
              <div className="agenda-row" key={e.id + i}>
                <span>{fmt(e.starts_at)}</span>
                <div>
                  <strong>{e.title}</strong>
                  <small>
                    {e.kind === "tasks"
                      ? "Task due"
                      : e.kind === "assignments"
                        ? "Assignment due"
                        : e.all_day
                          ? "All day"
                          : e.description || "Calendar event"}
                  </small>
                </div>
              </div>
            ))
          ) : (
            <Empty text="Nothing scheduled this month." />
          )}
        </Panel>
      ) : (
        <Records
          {...p}
          table="calendar_events"
          filter={(r: any) => !r.deleted_at}
          columns={["title", "starts_at", "ends_at", "recurrence"]}
        />
      )}
      <div className="notice">
        Local calendar is ready. Google two-way sync is Phase 2 scaffolding and
        is not connected.
      </div>
      {edit && (
        <Editor
          table="calendar_events"
          schema={p.schema}
          onSaved={p.onRefresh}
          onClose={() => setEdit(false)}
        />
      )}
    </>
  );
}
export function SettingsPage(p: any) {
  const [tab, setTab] = useState("preferences");
  const [status, setStatus] = useState<any>({});
  const [secret, setSecret] = useState("");
  const [name, setName] = useState("llm_api_key");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mapping, setMapping] = useState(
    '{"records_path":"records","fields":{"metric":"metric","value":"value","unit":"unit","recorded_at":"recorded_at","source":"source","device":"device","external_id":"external_id"}}',
  );
  const [sample, setSample] = useState('{"records":[]}');
  const [preview, setPreview] = useState("");
  useEffect(() => {
    api("/integrations/status")
      .then(setStatus)
      .catch((e) => setError(e.message));
  }, [p.refresh]);
  async function download() {
    setBusy(true);
    try {
      const u = URL.createObjectURL(await downloadBackup());
      const a = document.createElement("a");
      a.href = u;
      a.download = "life-os-backup.zip";
      a.click();
      setTimeout(() => URL.revokeObjectURL(u), 1000);
      setMessage("Backup downloaded: every table in JSON and CSV.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file: File) {
    if (
      !confirm(
        "Restore replaces all current data, including owner credentials, with this backup. Export your current data first. Continue?",
      )
    )
      return;
    setBusy(true);
    try {
      await restoreBackup(file);
      sessionStorage.removeItem("life-os-token");
      window.dispatchEvent(new Event("signed-out"));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Tabs
        active={tab}
        onChange={setTab}
        items={[
          ["preferences", "Preferences"],
          ["reminders", "Reminders"],
          ["integrations", "Connections & AI"],
          ["mapping", "Bridge mapping"],
          ["backup", "Backup & restore"],
        ]}
      />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      {tab === "preferences" ? (
        <>
          <Preferences {...p} />
          <details>
            <summary>Advanced configuration</summary>
            <Records
              {...p}
              table="settings"
              columns={["key", "value"]}
              heading="Configuration records"
            />
          </details>
          <div className="notice">
            Set timezone to an IANA name such as Asia/Kolkata. Body metrics
            remain yours to edit. Grade bands start empty so no country’s
            grading system is assumed.
          </div>
        </>
      ) : tab === "reminders" ? (
        <Records {...p} table="reminder_rules" />
      ) : tab === "integrations" ? (
        <>
          <div className="connection-grid">
            <Panel title="AI assistance">
              <p>
                {status.llm_configured
                  ? "Provider key saved. Feedback and tutor are available on request."
                  : "Not configured. Journal and learning work without AI."}
              </p>
              <p>
                Tokens used:{" "}
                <strong>
                  {(status.input_tokens || 0) + (status.output_tokens || 0)}
                </strong>
                <small>
                  {" "}
                  {status.input_tokens || 0} input · {status.output_tokens || 0}{" "}
                  output
                </small>
              </p>
            </Panel>
            <Panel title="Health Connect bridge">
              <p>
                {status.health_configured
                  ? "Receiver token saved. Point your phone bridge at the endpoint in the setup guide."
                  : "No connection required. Manual health entry is always available."}
              </p>
            </Panel>
            <Panel title="Google Calendar">
              <p>{status.google}</p>
            </Panel>
            <Panel title="Optional Samsung / Wearables">
              <p>
                {status.samsung}. {status.open_wearables}.
              </p>
            </Panel>
          </div>
          <Panel title="Encrypted credentials">
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                try {
                  await api("/secrets/" + name, "POST", { value: secret });
                  setSecret("");
                  setMessage("Credential saved encrypted.");
                  p.onRefresh();
                } catch (e) {
                  setError(e.message);
                }
              }}
            >
              <div className="form-grid">
                <label>
                  Credential
                  <select
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  >
                    <option value="llm_api_key">LLM provider API key</option>
                    <option value="health_webhook_token">
                      Health bridge bearer token
                    </option>
                    <option value="digest_token">
                      Digest trigger bearer token
                    </option>
                  </select>
                </label>
                <label>
                  Secret value
                  <input
                    type="password"
                    autoComplete="off"
                    value={secret}
                    onChange={(e) => setSecret(e.target.value)}
                    required
                    minLength={16}
                  />
                </label>
              </div>
              <div className="form-actions">
                <button
                  type="button"
                  onClick={async () => {
                    await api("/secrets/" + name, "POST", { value: "" })
                      .then(() => {
                        setMessage("Credential removed.");
                        p.onRefresh();
                      })
                      .catch((e) => setError(e.message));
                  }}
                >
                  Remove credential
                </button>
                <button className="primary">Save encrypted</button>
              </div>
            </form>
          </Panel>
          <Records {...p} table="ai_usage" />
        </>
      ) : tab === "mapping" ? (
        <>
          <Records {...p} table="ingestion_mappings" />
          <Panel title="Test a mapping">
            <div className="form-grid">
              <label>
                Mapping JSON
                <textarea
                  className="mono"
                  rows={9}
                  value={mapping}
                  onChange={(e) => setMapping(e.target.value)}
                />
              </label>
              <label>
                Sample bridge payload
                <textarea
                  className="mono"
                  rows={9}
                  value={sample}
                  onChange={(e) => setSample(e.target.value)}
                />
              </label>
            </div>
            <button
              onClick={async () => {
                try {
                  const v = await api("/integrations/mapping-preview", "POST", {
                    mapping: JSON.parse(mapping),
                    sample: JSON.parse(sample),
                  });
                  setPreview(JSON.stringify(v, null, 2));
                } catch (e) {
                  setError(e.message);
                }
              }}
            >
              Preview normalized records
            </button>
            {preview && <pre>{preview}</pre>}
          </Panel>
        </>
      ) : (
        <Panel title="A backup you can restore">
          <p>
            One download includes every table as JSON and CSV, plus a complete
            JSON backup. Encrypted credentials stay encrypted. Keep your API
            encryption key separately.
          </p>
          <div className="backup-actions">
            <button className="primary" disabled={busy} onClick={download}>
              <Download size={18} />
              {busy ? "Working…" : "Export all data"}
            </button>
            <label className="file-button">
              <Upload size={18} />
              Restore backup
              <input
                aria-label="Restore backup file"
                type="file"
                accept=".zip,.json"
                disabled={busy}
                onChange={(e) =>
                  e.target.files?.[0] && upload(e.target.files[0])
                }
              />
            </label>
          </div>
          <p className="muted">
            Restoring replaces existing data and may change your sign-in
            credentials to those in the backup. CSV-only restore accepts the CSV
            folder and manifest inside a ZIP. This is backup restoration, not a
            health-data upload.
          </p>
        </Panel>
      )}
    </>
  );
}
