import { useEffect, useRef, useState } from "react";
import { Check, X } from "lucide-react";
import { api } from "./api";

const eventName = "life-os:feedback";
export function savedFeedback(message: string, detail = "") {
  window.dispatchEvent(new CustomEvent(eventName, { detail: { message, detail } }));
}
export function recordFeedback(table: string, editing: boolean) {
  const names: Record<string, string> = {
    journal_entries: "Journal entry saved", workouts: "Workout logged",
    workout_sets: "Set logged", problem_attempts: "Attempt recorded",
    concept_notes: "Concept note saved", trait_ratings: "Rating recorded",
    reflections: "Reflection saved", calendar_events: "Event saved",
    tasks: editing ? "Task updated" : "Task added", projects: "Project saved",
    grades: "Grade saved", assignments: "Assignment saved", work_notes: "Note saved",
    goals: "Goal saved",
  };
  savedFeedback(names[table] || "Changes saved");
}
export function SuccessMark({ burst = false }: { burst?: boolean }) {
  return <span className={"success-mark" + (burst ? " burst" : "")} aria-hidden="true">
    <Check size={19} />
    {burst && <span className="success-pixels"><i /><i /><i /><i /></span>}
  </span>;
}
export function SuccessFeedback() {
  const [notice, setNotice] = useState<any>();
  useEffect(() => {
    const handler = (event: Event) => setNotice({ ...(event as CustomEvent).detail, id: crypto.randomUUID() });
    window.addEventListener(eventName, handler);
    return () => window.removeEventListener(eventName, handler);
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(undefined), 4500);
    return () => window.clearTimeout(timer);
  }, [notice]);
  return <div className="feedback-region" role="status" aria-live="polite" aria-atomic="true">
    {notice && <div className="save-receipt" key={notice.id}>
      <SuccessMark burst />
      <div><strong>{notice.message}</strong>{notice.detail && <small>{notice.detail}</small>}</div>
      <button className="icon" aria-label="Dismiss confirmation" onClick={() => setNotice(undefined)}><X size={17} /></button>
    </div>}
  </div>;
}
export const confirmationPause = () => new Promise<void>((resolve) => {
  window.setTimeout(resolve, window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 280);
});
export function CompleteTask({ task, onRefresh, compact = false }: any) {
  const [state, setState] = useState("idle");
  const [error, setError] = useState("");
  const locked = useRef(false);
  return <span className="task-completion">
    <button
      className={(compact ? "check-button " : "") + "complete-action " + state}
      aria-label={compact ? "Complete " + task.title : undefined}
      disabled={state !== "idle"}
      onClick={async () => {
        if (locked.current) return;
        locked.current = true;
        setState("saving"); setError("");
        try {
          await api("/tasks/" + task.id + "/complete", "POST");
          setState("done");
          savedFeedback("Task completed", task.title);
          await confirmationPause();
          onRefresh();
        } catch (e) {
          setState("idle"); locked.current = false;
          setError(e.message);
        }
      }}
    >
      {state === "done" ? <SuccessMark burst /> : <Check size={16} />}
      {!compact && (state === "done" ? "Done" : state === "saving" ? "Completing…" : "Complete")}
    </button>
    {error && <small className="error" role="alert">{error}</small>}
  </span>;
}
export function ValueBar({ ratio }: { ratio: number }) {
  const value = Number.isFinite(ratio) ? Math.max(0, Math.min(1, ratio)) : 0;
  return <span className="value-bar" aria-hidden="true"><i style={{ transform: `scaleX(${value})` }} /></span>;
}
