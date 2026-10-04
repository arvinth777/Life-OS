import React, { useEffect, useState } from "react";
import {
  Home,
  BookOpen,
  Compass,
  GraduationCap,
  Briefcase,
  Code2,
  Activity,
  CalendarDays,
  ListTodo,
  Settings,
  LogOut,
  ArrowUpRight,
  Plus,
  ArrowRight,
  PanelLeft,
} from "lucide-react";
import { api, authToken, base, clearAuthToken, saveAuthToken, setBase, setZone, fmt } from "./api";
import {
  Editor,
  Panel,
  Empty,
  LoadingRows,
} from "./components";
import {
  Journal,
  Personality,
  Academic,
  Work,
  Tasks,
  Calendar,
  SettingsPage,
} from "./screens";
import { DSA } from "./dsa";
import { Physical } from "./physical";
import { NightScene } from "./NightScene";
import { Overview } from "./Overview";
import { SuccessFeedback, CompleteTask } from "./feedback";
const navigation = [
  ["home", "Overview", Home],
  ["journal", "Journal", BookOpen],
  ["personality", "Personal growth", Compass],
  ["academics", "Academics", GraduationCap],
  ["work", "Work", Briefcase],
  ["dsa", "DSA in Python", Code2],
  ["physical", "Physical goals", Activity],
  ["calendar", "Calendar", CalendarDays],
  ["tasks", "To-do list", ListTodo],
] as const;
const subtitles: any = {
  home: "A little structure. Room for everything else.",
  journal: "Write, find, and revisit your entries.",
  personality: "Reflect with prompts and track your own trait ratings.",
  academics: "Track coursework, deadlines, and weighted grades.",
  work: "Projects, their next tasks, and your career goals.",
  dsa: "Start from zero. Understand one thing at a time.",
  physical: "Daily readings, workouts, and your personal targets.",
  calendar: "Events and deadlines in one agenda.",
  tasks: "Prioritize tasks, finish subtasks, and manage recurrence.",
  settings: "Preferences, connections, reminders, and backups.",
};
export default function App() {
  const [session, setSession] = useState(!!authToken());
  const [section, setSection] = useState("");
  const [page, setPage] = useState(location.hash.slice(1) || "home");
  const [schema, setSchema] = useState<any>({});
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [quick, setQuick] = useState("");
  const reload = () => setRefresh((x) => x + 1);
  const navigate = (p: string, tab = "") => {
    setSection(tab);
    location.hash = p;
    setPage(p);
    window.scrollTo(0, 0);
  };
  useEffect(() => {
    const listener = () => setPage(location.hash.slice(1) || "home");
    const out = () => {
      clearAuthToken();
      setSession(false);
    };
    window.addEventListener("hashchange", listener);
    window.addEventListener("signed-out", out);
    return () => {
      window.removeEventListener("hashchange", listener);
      window.removeEventListener("signed-out", out);
    };
  }, []);
  useEffect(() => {
    if (!session) return;
    setError("");
    Promise.all([api("/schema"), api("/data/settings"), api("/auth/me")])
      .then(([schema, settings]) => {
        setSchema(schema);
        setSettings(Object.fromEntries(settings.map((r: any) => [r.key, r.value])));
        setZone(
          settings.find((x: any) => x.key === "timezone")?.value || "UTC",
        );
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
    api("/digest", "POST").catch(() => {});
  }, [session, refresh]);
  if (!session)
    return (
      <Login
        onLogin={() => {
          setSession(true);
          reload();
        }}
      />
    );
  const props = { schema, settings, refresh, onRefresh: reload, navigate, initialTab: section };
  return (
    <div className="app-shell">
      <a
        className="skip"
        href="#main"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main")?.focus();
          document.getElementById("main")?.scrollIntoView();
        }}
      >
        Skip to content
      </a>
      <SuccessFeedback />
      <aside className="sidebar">
        <a className="brand" href="#home" onClick={() => navigate("home")}>
          <span className="brand-mark">
            <PanelLeft size={23} />
          </span>
          <span>
            life<span className="brand-os">OS</span>
            <small>PERSONAL WORKSPACE</small>
          </span>
        </a>
        <nav aria-label="Main navigation">
          {navigation.map(([key, label, Icon], i) => (
            <React.Fragment key={key}>
              {[0, 1, 3, 6].includes(i) && (
                <span className="nav-group">
                  {i === 0
                    ? "Your day"
                    : i === 1
                      ? "Reflect"
                      : i === 3
                        ? "Learn & work"
                        : "Daily life"}
                </span>
              )}
              <button
                className={page === key ? "nav-item selected" : "nav-item"}
                aria-current={page === key ? "page" : undefined}
                onClick={() => navigate(key)}
              >
                <Icon size={18} />
                {label}
                {page === key && <span className="nav-indicator" />}
              </button>
            </React.Fragment>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button
            className={"nav-item " + (page === "settings" ? "selected" : "")}
            onClick={() => navigate("settings")}
          >
            <Settings size={18} />
            Settings
          </button>
          <button
            className="nav-item"
            onClick={async () => {
              await api("/auth/logout", "POST").catch(() => {});
              clearAuthToken();
              setSession(false);
            }}
          >
            <LogOut size={18} />
            Sign out
          </button>
          <div className="owner-label">
            <span className="owner-avatar">ME</span>
            <div>
              Your space<small>Single owner · private</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <main id="main" tabIndex={-1}>
          <header className="page-head" key={`header-${page}`}>
            <div>
              {page === "home" && <div className="eyebrow">
                {new Date().toLocaleDateString(undefined, {
                  weekday: "long", month: "long", day: "numeric",
                  timeZone: settings.timezone || "UTC",
                })}
              </div>}
              <h1>
                {navigation.find((x) => x[0] === page)?.[1] || "Settings"}
              </h1>
              {page !== "home" && <p>{subtitles[page]}</p>}
            </div>
          </header>
          {error ? (
            <div className="error" role="alert">
              {error}
              <button onClick={reload}>Try again</button>
            </div>
          ) : !loaded ? (
            <LoadingRows label="Opening your workspace…" />
          ) : (
            <div className="page-content" key={`content-${page}`}>
              {page === "home" ? (
                <Overview {...props} onQuick={setQuick} />
              ) : page === "journal" ? (
                <Journal {...props} />
              ) : page === "personality" ? (
                <Personality {...props} />
              ) : page === "academics" ? (
                <Academic {...props} />
              ) : page === "work" ? (
                <Work {...props} />
              ) : page === "dsa" ? (
                <DSA {...props} />
              ) : page === "physical" ? (
                <Physical {...props} />
              ) : page === "calendar" ? (
                <Calendar {...props} />
              ) : page === "tasks" ? (
                <Tasks {...props} />
              ) : (
                <SettingsPage {...props} />
              )}
            </div>
          )}
          {quick && (
            <Editor
              table={quick}
              schema={schema}
              onSaved={reload}
              onClose={() => setQuick("")}
            />
          )}
        </main>
      </div>
    </div>
  );
}
function Login({ onLogin }: any) {
  const [user, setUser] = useState("owner");
  const [pass, setPass] = useState("");
  const [endpoint, setEndpoint] = useState(base);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const missing =
    !base && !["localhost", "127.0.0.1"].includes(location.hostname);
  async function submit(e: any) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setBase(endpoint);
      const data = await api("/auth/login", "POST", {
        username: user,
        password: pass,
      });
      saveAuthToken(data.token);
      onLogin();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <div className="login-intro">
        <span className="eyebrow">YOUR PERSONAL WORKSPACE</span>
        <h1>
          life<span>OS</span>
        </h1>
        <p>
          Somewhere for the things
          <br />
          you’re working on.
        </p>
        <NightScene />
        <div className="login-index">
          Reflect <span>01</span>
          <br />
          Learn & work <span>02</span>
          <br />
          Daily life <span>03</span>
        </div>
      </div>
      <section className="login-form">
        <h2>Welcome back.</h2>
        <p>Sign in to your own space.</p>
        {missing && (
          <div className="notice">
            Connect your data server below to finish setting up this copy of Life OS.
          </div>
        )}
        <form onSubmit={submit}>
          <label>
            Username
            <input
              autoComplete="username"
              value={user}
              onChange={(e) => setUser(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={pass}
              onChange={(e) => setPass(e.target.value)}
              required
            />
          </label>
          {!import.meta.env.VITE_API_URL && <details open={missing}>
            <summary>API connection</summary>
            <label>
              API address
              <input
                type="url"
                placeholder="https://your-life-os-api.onrender.com"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
              />
            </label>
            <small>
              Local development connects automatically. For a hosted app, use
              the address from your setup guide.
            </small>
          </details>}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="primary" disabled={busy} aria-busy={busy}>
            {busy ? "Signing in…" : "Sign in"}
            <ArrowRight size={18} />
          </button>
        </form>
        <small>
          Your entries stay in your database. No account registration.
        </small>
      </section>
    </main>
  );
}
