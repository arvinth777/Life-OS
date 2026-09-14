import React, { useEffect, useRef, useState } from "react";
import { Plus, X, Trash2, Pencil, Check, ArrowRight } from "lucide-react";
import { api, title, fmt, localInput } from "./api";
import { recordFeedback } from "./feedback";
export function Empty({
  text = "Nothing here yet.",
  action,
}: {
  text?: string;
  action?: any;
}) {
  return (
    <div className="empty">
      <p>{text}</p>
      {action}
    </div>
  );
}
export function Panel({
  title: heading,
  action,
  children,
  className = "",
}: any) {
  return (
    <section className={"panel " + className}>
      <div className="section-head">
        <h2>{heading}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Metric({ label, value, unit, children }: any) {
  return (
    <div className="metric">
      <span>{label}</span>
      <div>
        <strong>{value}</strong>
        <small>{unit}</small>
      </div>
      {children}
    </div>
  );
}
export function Modal({ title: heading, onClose, children }: any) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="modal-head">
        <h2>{heading}</h2>
        <button className="icon" onClick={onClose} aria-label="Close">
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
const hidden = new Set([
  "series_id",
  "previous_id",
  "completed_at",
  "recurrence_anchor",
  "google_event_id",
  "etag",
  "sync_state",
  "deleted_at",
  "ease_factor",
  "repetitions",
  "interval_days",
]);
const long = new Set([
  "body",
  "notes",
  "reflection",
  "description",
  "instructions",
  "explanation",
  "statement",
  "solution",
  "front",
  "back",
]);
export function Editor({
  table,
  schema,
  row,
  initial = {},
  onClose,
  onSaved,
}: any) {
  const fields = (schema[table]?.fields || []).filter(
    (f: any) => !hidden.has(f.name),
  );
  const [values, setValues] = useState<any>(() =>
    Object.fromEntries(
      fields.map((f: any) => {
        let v = row?.[f.name] ?? initial[f.name] ?? f.default;
        if (v == null) {
          v =
            f.type === "boolean"
              ? false
              : f.type === "json"
                ? f.name === "value"
                  ? {}
                  : f.name === "custom_fields" ||
                      f.name === "mapping" ||
                      f.name === "config"
                    ? {}
                    : []
                : f.type === "datetime" && f.required
                  ? localInput()
                  : f.type === "date" && f.required
                    ? new Date().toISOString().slice(0, 10)
                    : "";
        }
        if (f.type === "json") v = JSON.stringify(v, null, 2);
        if (f.type === "datetime" && v) v = localInput(v);
        return [f.name, v];
      }),
    ),
  );
  const [refs, setRefs] = useState<any>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [defs, setDefs] = useState<any[]>([]);
  useEffect(() => {
    Promise.all(
      [...new Set(fields.filter((f: any) => f.ref).map((f: any) => f.ref))].map(
        async (name: string) => [name, await api("/data/" + name)],
      ),
    )
      .then((x) => setRefs(Object.fromEntries(x)))
      .catch((e) => setError(e.message));
    if (fields.some((f: any) => f.name === "custom_fields"))
      api("/data/custom_field_definitions")
        .then((d) => setDefs(d.filter((x: any) => x.entity === table)))
        .catch((e) => setError(e.message));
  }, []);
  const change = (key: string, value: any) =>
    setValues((old: any) => ({ ...old, [key]: value }));
  async function submit(e: any) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const payload: any = {};
      for (const f of fields) {
        let v = values[f.name];
        if (v === "" && !f.required) {
          if (row) payload[f.name] = f.type === "text" && !f.ref ? "" : null;
          continue;
        }
        if (f.type === "json") v = JSON.parse(v);
        if (f.type === "number") v = Number(v);
        if (f.type === "datetime" && v) v = new Date(v).toISOString();
        payload[f.name] = v;
      }
      await api(
        "/data/" + table + (row ? "/" + row.id : ""),
        row ? "PATCH" : "POST",
        payload,
      );
      recordFeedback(table, !!row);
      onSaved();
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={(row ? "Edit " : "Add ") + title(table.replace(/s$/, ""))}
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <div className="form-grid">
          {fields.map((f: any) => (
            <label
              className={long.has(f.name) || f.type === "json" ? "wide" : ""}
              key={f.name}
            >
              {title(f.name.replace(/_id$/, ""))}
              {f.required ? " *" : ""}
              {f.ref ? (
                <select
                  value={values[f.name]}
                  onChange={(e) => change(f.name, e.target.value)}
                  required={f.required}
                >
                  <option value="">Choose {title(f.ref)}</option>
                  {(refs[f.ref] || [])
                    .filter((r: any) => r.id !== row?.id)
                    .map((r: any) => (
                      <option key={r.id} value={r.id}>
                        {r.title || r.name || r.key || r.id}
                      </option>
                    ))}
                </select>
              ) : f.type === "boolean" ? (
                <input
                  type="checkbox"
                  checked={values[f.name]}
                  onChange={(e) => change(f.name, e.target.checked)}
                />
              ) : f.name === "custom_fields" && defs.length ? (
                <div className="custom-fields">
                  {defs.map((d) => {
                    let obj: any = {};
                    try {
                      obj = JSON.parse(values.custom_fields);
                    } catch {}
                    return (
                      <label key={d.id}>
                        {d.name}
                        {d.field_type === "select" ? (
                          <select
                            value={obj[d.name] ?? ""}
                            onChange={(e) =>
                              change(
                                "custom_fields",
                                JSON.stringify({
                                  ...obj,
                                  [d.name]: e.target.value,
                                }),
                              )
                            }
                          >
                            <option value="">Choose</option>
                            {d.options.map((x: string) => (
                              <option key={x}>{x}</option>
                            ))}
                          </select>
                        ) : (
                          <input
                            type={
                              d.field_type === "number"
                                ? "number"
                                : d.field_type === "boolean"
                                  ? "checkbox"
                                  : "text"
                            }
                            checked={!!obj[d.name]}
                            value={
                              d.field_type === "boolean"
                                ? undefined
                                : (obj[d.name] ?? "")
                            }
                            onChange={(e) =>
                              change(
                                "custom_fields",
                                JSON.stringify({
                                  ...obj,
                                  [d.name]:
                                    d.field_type === "number"
                                      ? Number(e.target.value)
                                      : d.field_type === "boolean"
                                        ? e.target.checked
                                        : e.target.value,
                                }),
                              )
                            }
                          />
                        )}
                      </label>
                    );
                  })}
                </div>
              ) : long.has(f.name) || f.type === "json" ? (
                <textarea
                  className={
                    f.type === "json" || f.name === "solution" ? "mono" : ""
                  }
                  rows={f.name === "body" ? 8 : 4}
                  value={values[f.name]}
                  onChange={(e) => change(f.name, e.target.value)}
                  required={f.required}
                />
              ) : (
                <input
                  type={
                    f.type === "datetime"
                      ? "datetime-local"
                      : f.type === "number"
                        ? "number"
                        : f.type === "date"
                          ? "date"
                          : "text"
                  }
                  step="any"
                  value={values[f.name]}
                  onChange={(e) => change(f.name, e.target.value)}
                  required={f.required}
                />
              )}
              {f.type === "json" && f.name !== "custom_fields" && (
                <small>
                  Structured JSON; changes are validated when saved.
                </small>
              )}
              {f.type === "datetime" && (
                <small>Enter in your browser’s local timezone.</small>
              )}
              {f.name === "rrule" && (
                <small>Example: FREQ=WEEKLY;BYDAY=MO,WE,FR</small>
              )}
            </label>
          ))}
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
export function Records({
  table,
  schema,
  refresh,
  onRefresh,
  initial = {},
  filter,
  heading,
  columns,
  actions,
}: any) {
  const [records, setRecords] = useState<any[]>([]);
  const [edit, setEdit] = useState<any>(undefined);
  const [error, setError] = useState("");
  const [refs, setRefs] = useState<any>({});
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const paged = table === "health_records";
  useEffect(() => {
    let active = true;
    setLoading(true);
    api("/data/" + table + (paged ? `?limit=200&offset=${page * 200}` : ""))
      .then((r) => { if (active) { setRecords(r); setError(""); } })
      .catch((e) => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    const fs = schema[table]?.fields.filter((f: any) => f.ref) || [];
    Promise.all(
      [...new Set(fs.map((f: any) => f.ref))].map(async (n: string) => [
        n,
        await api("/data/" + n),
      ]),
    )
      .then((r) => setRefs(Object.fromEntries(r)))
      .catch((e) => setError(e.message));
    return () => { active = false; };
  }, [table, refresh, page]);
  const shown = filter ? records.filter(filter) : records;
  const names =
    columns ||
    schema[table]?.fields
      .filter(
        (f: any) =>
          !hidden.has(f.name) &&
          ![
            "body",
            "notes",
            "description",
            "custom_fields",
            "solution",
            "explanation",
            "statement",
            "mapping",
            "config",
          ].includes(f.name),
      )
      .slice(0, 4)
      .map((f: any) => f.name) ||
    [];
  const display = (r: any, k: string) => {
    const field = schema[table]?.fields.find((f: any) => f.name === k);
    if (field?.ref) {
      const target = refs[field.ref]?.find((x: any) => x.id === r[k]);
      return target?.name || target?.title || "—";
    }
    if (field?.type === "datetime") return fmt(r[k]);
    if (typeof r[k] === "boolean") return r[k] ? "Yes" : "No";
    if (typeof r[k] === "object") return JSON.stringify(r[k]);
    return String(r[k] ?? "—");
  };
  async function remove(row: any) {
    if (!confirm("Delete this " + title(table.replace(/s$/, "")) + "?")) return;
    setBusy(true);
    try {
      await api("/data/" + table + "/" + row.id, "DELETE");
      onRefresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel
      title={heading || title(table)}
      action={
        schema[table]?.editable && (
          <button onClick={() => setEdit(null)}>
            <Plus size={16} />
            Add
          </button>
        )
      }
    >
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {shown.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {names.map((k: string) => (
                  <th key={k}>{title(k.replace(/_id$/, ""))}</th>
                ))}
                <th>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id}>
                  {names.map((k: string) => (
                    <td key={k}>{display(r, k)}</td>
                  ))}
                  <td>
                    <div className="actions">
                      {actions?.(r)}
                      {schema[table]?.editable && (
                        <>
                          <button
                            className="icon"
                            aria-label={
                              "Edit " + (r.title || r.name || "record")
                            }
                            onClick={() => setEdit(r)}
                          >
                            <Pencil size={16} />
                          </button>
                          <button
                            className="icon"
                            disabled={busy}
                            aria-label={
                              "Delete " + (r.title || r.name || "record")
                            }
                            onClick={() => remove(r)}
                          >
                            <Trash2 size={16} />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty text={"No " + title(table).toLowerCase() + " yet."} />
      )}
      {paged && <div className="form-actions" aria-label="Health history pages">
        <button disabled={loading || page === 0} onClick={() => setPage((n) => n - 1)}>Newer readings</button>
        <span role="status">{loading ? "Loading…" : `Page ${page + 1}`}</span>
        <button disabled={loading || records.length < 200} onClick={() => setPage((n) => n + 1)}>Older readings</button>
      </div>}
      {edit !== undefined && (
        <Editor
          table={table}
          schema={schema}
          row={edit}
          initial={initial}
          onClose={() => setEdit(undefined)}
          onSaved={onRefresh}
        />
      )}
    </Panel>
  );
}
export function Tabs({ items, active, onChange }: any) {
  return (
    <div className="tabs" aria-label="Sections">
      {items.map((x: any) => (
        <button
          key={x[0]}
          className={active === x[0] ? "active" : ""}
          aria-pressed={active === x[0]}
          onClick={() => onChange(x[0])}
        >
          {x[1]}
        </button>
      ))}
    </div>
  );
}
export function Trend({ values, label, min = 0, max }: any) {
  const width = 600,
    height = 150;
  const top = max ?? Math.max(1, ...values);
  const points = values
    .map(
      (n: number, i: number) =>
        `${20 + (i * (width - 40)) / Math.max(1, values.length - 1)},${height - 20 - ((n - min) / (top - min)) * (height - 40)}`,
    )
    .join(" ");
  return (
    <div className="trend">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
        <path d="M20 10V130H580" className="chart-axis" />
        <polyline key={points} points={points} className="chart-line chart-reveal" />
        {values.map((n: number, i: number) => (
          <circle
            key={`${i}-${n}`}
            style={{ animationDelay: `${Math.min(i * 45, 300)}ms` }}
            cx={20 + (i * (width - 40)) / Math.max(1, values.length - 1)}
            cy={height - 20 - ((n - min) / (top - min)) * (height - 40)}
            r="4"
            className="chart-point"
          />
        ))}
      </svg>
      <small>
        {label}:{" "}
        {values.length ? values.join(" → ") : "Add a record to see your trend."}
      </small>
    </div>
  );
}
