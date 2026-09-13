import React, { useEffect, useRef, useState } from "react";
import {
  ChevronRight,
  ChevronLeft,
  Plus,
  Check,
  Code2,
  Sparkles,
  ArrowRight,
  BookOpen,
} from "lucide-react";
import { api, title, fmt, todayDate } from "./api";
import { Panel, Records, Tabs, Editor, Empty, Trend } from "./components";
import { SuccessMark, savedFeedback, confirmationPause, ValueBar } from "./feedback";
export function DSA(p: any) {
  const [tab, setTab] = useState("learn");
  const [data, setData] = useState<any>({});
  const [selected, setSelected] = useState("");
  const [edit, setEdit] = useState<any>();
  const [author, setAuthor] = useState("lessons");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<any>({ patterns: [], trend: [] });
  const [status, setStatus] = useState<any>({});
  useEffect(() => {
    Promise.all(
      [
        "curriculum_modules",
        "lessons",
        "patterns",
        "problems",
        "concept_notes",
      ].map(async (n) => [n, await api("/data/" + n)]),
    )
      .then((r) => setData(Object.fromEntries(r)))
      .catch((e) => setError(e.message));
    api("/dsa/progress")
      .then(setProgress)
      .catch((e) => setError(e.message));
    api("/integrations/status")
      .then(setStatus)
      .catch((e) => setError(e.message));
  }, [p.refresh]);
  const sorted = (name: string) =>
    (data[name] || [])
      .slice()
      .sort((a: any, b: any) => a.position - b.position);
  const lesson =
    data.lessons?.find((r: any) => r.id === selected) ||
    sorted("lessons").find(
      (l: any) => l.module_id === sorted("curriculum_modules")[0]?.id,
    );
  const patterns = (data.patterns || []).filter(
    (r: any) => r.lesson_id === lesson?.id,
  );
  const today = todayDate();
  return (
    <>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <Tabs
        active={tab}
        onChange={setTab}
        items={[
          ["learn", "Learning path"],
          ["review", "Concept reviews"],
          ["progress", "Your progress"],
          ["author", "Edit curriculum"],
        ]}
      />
      {tab === "learn" ? (
        <div className="learn-layout">
          <aside className="curriculum-outline">
            {sorted("curriculum_modules").map((m: any) => (
              <div key={m.id}>
                <span className="eyebrow">
                  {String(m.position + 1).padStart(2, "0")} / {m.title}
                </span>
                {sorted("lessons")
                  .filter((l: any) => l.module_id === m.id)
                  .map((l: any) => (
                    <button
                      className={l.id === lesson?.id ? "active" : ""}
                      key={l.id}
                      onClick={() => {
                        setSelected(l.id);
                      }}
                    >
                      <span>
                        {l.title}
                        {l.incomplete && (
                          <small className="incomplete">Incomplete</small>
                        )}
                      </span>
                      <ChevronRight size={15} />
                    </button>
                  ))}
              </div>
            ))}
          </aside>
          <article className="lesson reading-surface">
            {lesson ? (
              <>
                <div className="eyebrow">
                  {lesson.incomplete
                    ? "OUTLINE · INCOMPLETE"
                    : "YOUR NEXT SMALL STEP"}
                </div>
                <h2>{lesson.title}</h2>
                {lesson.incomplete ? (
                  <div className="notice">
                    This lesson is an incomplete outline. Write it in Edit
                    curriculum when you’re ready. The Python primer and five
                    essential patterns are fully written.
                  </div>
                ) : (
                  <>
                    <div className="prose">{lesson.body}</div>
                    {patterns.map((pattern: any) => (
                      <section key={pattern.id}>
                        {pattern.walkthrough.length > 0 && <Walkthrough key={pattern.id} steps={pattern.walkthrough} />}
                        <div className="section-head">
                          <h3>Try it yourself</h3>
                          <button
                            onClick={() =>
                              setEdit({
                                table: "concept_notes",
                                initial: {
                                  pattern_id: pattern.id,
                                  title: pattern.title,
                                  front:
                                    "When would I use " +
                                    pattern.title.toLowerCase() +
                                    "?",
                                  back: "",
                                },
                              })
                            }
                          >
                            <Plus size={15} />
                            Concept note
                          </button>
                        </div>
                        {sorted("problems")
                          .filter((pr: any) => pr.pattern_id === pattern.id)
                          .map((problem: any) => (
                            <Problem
                              key={problem.id}
                              problem={problem}
                              onAttempt={() =>
                                setEdit({
                                  table: "problem_attempts",
                                  initial: { problem_id: problem.id },
                                })
                              }
                            />
                          ))}
                      </section>
                    ))}
                    <Tutor
                      key={lesson.id}
                      lesson={lesson}
                      configured={status.llm_configured}
                    />
                  </>
                )}
              </>
            ) : (
              <Empty text="Loading your curriculum…" />
            )}
          </article>
        </div>
      ) : tab === "review" ? (
        <>
          <div className="section-head">
            <div>
              <h2>Make it stick</h2>
              <p className="muted">
                Recall first. Reveal the answer, then grade your recall from 0
                to 5.
              </p>
            </div>
            <button onClick={() => setEdit({ table: "concept_notes" })}>
              <Plus size={16} />
              Concept note
            </button>
          </div>
          {(data.concept_notes || [])
            .filter((n: any) => n.due_on <= today)
            .map((n: any) => (
              <ReviewCard
                key={n.id + n.due_on}
                note={n}
                onRefresh={p.onRefresh}
              />
            ))}
          <Records
            {...p}
            table="concept_notes"
            columns={["title", "due_on", "interval_days", "ease_factor"]}
          />
        </>
      ) : tab === "progress" ? (
        <>
          <Panel title="Time to solve">
            <Trend
              values={progress.trend
                .filter((a: any) => a.solved)
                .map((a: any) => a.minutes)}
              label="Minutes per solved attempt, oldest to newest"
            />
          </Panel>
          <Panel title="Pattern accuracy">
            {progress.patterns.map((r: any) => (
              <div className="course-row" key={r.id}>
                <div>
                  <strong>{r.title}</strong>
                  <small>
                    {r.attempts} attempts · {r.solved} distinct problems solved
                  </small>
                  {r.accuracy !== null && <ValueBar ratio={r.accuracy} />}
                </div>
                <span>
                  {r.accuracy === null
                    ? "Not attempted"
                    : Math.round(r.accuracy * 100) + "%"}{" "}
                  {r.weak && (
                    <small className="incomplete">Practice next</small>
                  )}
                </span>
              </div>
            ))}
          </Panel>
          <Records {...p} table="problem_attempts" />
        </>
      ) : (
        <>
          <p className="notice">
            Content lives in your database. Mark a lesson incomplete until its
            teaching content is ready.
          </p>
          <label className="inline-label">
            Content type
            <select value={author} onChange={(e) => setAuthor(e.target.value)}>
              {["curriculum_modules", "lessons", "patterns", "problems"].map(
                (n) => (
                  <option key={n} value={n}>
                    {title(n)}
                  </option>
                ),
              )}
            </select>
          </label>
          <Records key={author} {...p} table={author} />
        </>
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
    </>
  );
}
function Problem({ problem, onAttempt }: any) {
  const [hints, setHints] = useState(0);
  return (
    <details className="problem">
      <summary>
        <span>
          <small>{problem.difficulty}</small>
          {problem.title}
        </span>
        <ChevronRight size={18} />
      </summary>
      <p className="prose">{problem.statement}</p>
      <div className="hints">
        {problem.hints.slice(0, hints).map((hint: string, i: number) => (
          <p key={i}>
            <strong>Hint {i + 1}.</strong> {hint}
          </p>
        ))}
      </div>
      <div className="actions">
        <button
          disabled={hints >= problem.hints.length}
          onClick={() => setHints((x) => x + 1)}
        >
          Reveal hint {Math.min(hints + 1, problem.hints.length)}
        </button>
        <button onClick={onAttempt}>
          <Check size={16} />
          Log attempt
        </button>
      </div>
      <details className="solution">
        <summary>Worked Python solution</summary>
        <pre>
          <code>{problem.solution}</code>
        </pre>
        <p>{problem.explanation}</p>
      </details>
    </details>
  );
}
const reviewDate = (date: string) => new Intl.DateTimeFormat(undefined, {
  day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
}).format(new Date(date + "T12:00:00Z"));
function ReviewCard({ note, onRefresh }: any) {
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>();
  const locked = useRef(false);
  return (
    <Panel title={note.title} className={"review-card" + (result ? " review-complete" : "")}>
      {result ? (
        <div className="review-result" role="status">
          <SuccessMark burst />
          <div><strong>Review saved</strong><p>Next review: {reviewDate(result.due_on)}</p></div>
        </div>
      ) : <>
        <p className="prose">{note.front}</p>
        {show ? (
          <div className="review-answer">
            <div className="feedback prose">{note.back}</div>
            <p className="muted">0: no recall · 1: recognized · 2: incorrect · 3: difficult · 4: good · 5: effortless</p>
            <div className="review-grades">
              {[0, 1, 2, 3, 4, 5].map((grade) => (
                <button key={grade} disabled={busy} onClick={async () => {
                  if (locked.current) return;
                  locked.current = true; setBusy(true); setError("");
                  try {
                    const next = await api("/reviews/" + note.id, "POST", { grade });
                    setResult(next);
                    savedFeedback("Review saved", `Next review: ${reviewDate(next.due_on)}`);
                    await confirmationPause();
                    onRefresh();
                  } catch (e) {
                    setError(e.message); setBusy(false); locked.current = false;
                  }
                }}>{grade}</button>
              ))}
            </div>
          </div>
        ) : <button onClick={() => setShow(true)}>Reveal answer</button>}
      </>}
      {error && <p className="error" role="alert">{error}</p>}
    </Panel>
  );
}
function Walkthrough({ steps }: { steps: any[] }) {
  const [step, setStep] = useState(0);
  const current = steps[step];
  return <>
    <div className="section-head walkthrough-heading">
      <h3>Walk through it</h3>
      <span className="muted">{step + 1} / {steps.length}</span>
    </div>
    <div className="walkthrough">
      <div className="step-rail" role="progressbar" aria-label="Walkthrough position" aria-valuemin={1} aria-valuemax={steps.length} aria-valuenow={step + 1}>
        {steps.map((_, i) => <span key={i} className={i <= step ? "reached" : ""} aria-hidden="true" />)}
      </div>
      <div className="array-cells">
        {current.values.map((value: any, i: number) => <div key={i} className={current.active.includes(i) ? "cell-active" : ""}>
          <span className={current.active.includes(i) ? "highlight" : ""} aria-label={`Value ${value}, index ${i}${current.active.includes(i) ? ", active" : ""}`}>{value}</span>
          <small>{i}</small><i className="cell-marker" aria-hidden="true" />
        </div>)}
      </div>
      <p className="step-caption" key={step} aria-live="polite" aria-atomic="true">{current.caption}</p>
      <div className="actions">
        <button disabled={step === 0} onClick={() => setStep((n) => n - 1)}><ChevronLeft size={16} />Back</button>
        <button disabled={step === steps.length - 1} onClick={() => setStep((n) => n + 1)}>Next step<ChevronRight size={16} /></button>
      </div>
    </div>
  </>;
}
function Tutor({ lesson, configured }: any) {
  const [messages, setMessages] = useState<any[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <section className="ai-section">
      <h3>
        <Sparkles size={18} />A patient tutor
      </h3>
      {!configured ? (
        <p className="muted">
          AI tutor is not configured. Add a provider key in Settings. The
          lesson, walkthroughs, hints, and worked solutions remain available.
        </p>
      ) : (
        <>
          <div className="conversation">
            {messages.map((m, i) => (
              <div key={i} className={m.role}>
                <small>{m.role === "user" ? "You" : "Tutor"}</small>
                <p className="prose">{m.content}</p>
              </div>
            ))}
          </div>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const next = [...messages, { role: "user", content: text }];
              setBusy(true);
              setError("");
              try {
                const r = await api("/ai/tutor/" + lesson.id, "POST", {
                  messages: next,
                });
                setMessages([...next, { role: "assistant", content: r.text }]);
                setText("");
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Your question
              <textarea
                rows={3}
                value={text}
                onChange={(e) => setText(e.target.value)}
                required
              />
            </label>
            <button disabled={busy} className="primary">
              {busy ? "Thinking…" : "Ask tutor"}
              <ArrowRight size={16} />
            </button>
          </form>
          {error && <p className="error">{error}</p>}
        </>
      )}
    </section>
  );
}
