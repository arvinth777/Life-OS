import { useId, useRef, useState, type CSSProperties } from "react";
import { Plus, Droplets, Check } from "lucide-react";
import { api } from "./api";

type Props = {
  total?: number;
  goal: number;
  refresh: () => Promise<void>;
  onCustom: () => void;
  onGoal: () => void;
};
export function WaterTracker({ total, goal, refresh, onCustom, onGoal }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [pours, setPours] = useState(0);
  const locked = useRef(false);
  // A retry after a lost response must not create a second drink.
  const pending = useRef<any>(null);
  const saved = useRef(false);
  const id = useId();
  const target = Number.isFinite(goal) && goal > 0 ? goal : 2000;
  const amount = total ?? 0;
  const level = Math.max(0, Math.min(1, amount / target));
  async function drink() {
    if (locked.current || total === undefined) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      if (!saved.current) {
        pending.current ||= {
          metric: "water", value: 250, unit: "ml",
          recorded_at: new Date().toISOString(), source: "manual",
          device: "owner", external_id: crypto.randomUUID(),
        };
        await api("/ingest", "POST", [pending.current]);
        saved.current = true;
      }
      // Show the authoritative total; an uncertain read offers a read-only retry.
      await refresh();
      pending.current = null;
      saved.current = false;
      setNeedsRefresh(false);
      setPours((n) => n + 1);
    } catch (e) {
      setNeedsRefresh(saved.current);
      setError(saved.current
        ? "Your drink is saved. Refresh the total to see it."
        : "Could not confirm your drink. Try again; it won’t be counted twice.");
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="hydration" aria-labelledby={id + "-heading"}>
      <div className="section-head">
        <h2 id={id + "-heading"}>Water today</h2>
        <button className="text-button" onClick={onGoal}>Edit goal</button>
      </div>
      <button
        className="water-tank"
        onClick={drink}
        disabled={busy || total === undefined}
        aria-label={needsRefresh ? "Refresh water total" : "Add 250 ml of water"}
        aria-describedby={id + "-amount"}
        aria-busy={busy}
      >
        <div className="water-liquid" aria-hidden="true" style={{ "--water-offset": `${(1 - level) * 100}%`, opacity: level > 0 ? 1 : 0 } as CSSProperties}>
          <svg key={pours} className={pours ? "water-wave pouring" : "water-wave"} viewBox="0 0 600 24" preserveAspectRatio="none">
            <path d="M0 12 Q37.5 0 75 12 T150 12 T225 12 T300 12 T375 12 T450 12 T525 12 T600 12 V24 H0Z" />
          </svg>
          {pours > 0 && <span key={`bubbles-${pours}`} className="water-bubbles"><i /><i /><i /></span>}
        </div>
        <span className="water-scale" aria-hidden="true"><i /><i /><i /></span>
        <span className="water-content">
          <Droplets size={24} aria-hidden="true" />
          <span id={id + "-amount"} className="water-amount">
            <strong>{total === undefined ? "—" : amount.toLocaleString()}</strong> ml
            <small>of {target.toLocaleString()} ml daily goal</small>
          </span>
          <span className="water-add">
            {busy ? (needsRefresh ? "Refreshing…" : "Saving…") : needsRefresh ? "Refresh total" : <><Plus size={17} />250 ml</>}
          </span>
        </span>
      </button>
      <div className="water-footer">
        <span role="status" aria-live="polite">
          {pours > 0 ? <><Check size={15} />250 ml saved</> : total === undefined ? "Loading today’s water…" : amount >= target ? "Daily goal reached" : `${Math.ceil(target - amount).toLocaleString()} ml to your goal`}
        </span>
        <button className="text-button" onClick={onCustom} disabled={busy || needsRefresh}>Different amount</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
