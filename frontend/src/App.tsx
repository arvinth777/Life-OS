import React, { useEffect, useRef, useState } from "react";
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
import { ContextHome } from "./ContextHome";
import { QuickCapture } from "./QuickCapture";
import { LifeMode, modes, modeNames, moduleMode } from "./contexts";
import { SuccessFeedback } from "./feedback";
const navigation = [
  ["home", "Overview", Home],
  ["journal", "Journal", BookOpen],
  ["personality", "Personal growth", Compass],
  ["academics", "Academics", GraduationCap],
  ["work", "Work", Briefcase],
  ["dsa", "DSA in Python", Code2],
  ["physical", "Physical goals", Activity],
  ["calendar", "All agenda", CalendarDays],
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
  const [mode, setMode] = useState<LifeMode>(() => moduleMode[location.hash.slice(1)] || (modes.includes(localStorage.getItem('life-os-mode') as LifeMode) ? localStorage.getItem('life-os-mode') as LifeMode : 'personal'));
  const [capture, setCapture] = useState(false);
  useEffect(() => { localStorage.setItem('life-os-mode', mode); document.documentElement.dataset.mode = mode; return () => {delete document.documentElement.dataset.mode}; }, [mode]);
  const [session, setSession] = useState(!!authToken());
  const [section, setSection] = useState("");
  const [page, setPage] = useState(location.hash.slice(1) || "home");
  const [schema, setSchema] = useState<any>({});
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const pendingNavigation = useRef<{page:string;tab:string}|null>(null);
  const reload = () => setRefresh((x) => x + 1);
  const navigate = (p: string, tab = "") => {
    if (moduleMode[p]) setMode(moduleMode[p]);
    setSection(tab);
    pendingNavigation.current = location.hash.slice(1) !== p ? {page:p,tab} : null;
    location.hash = p;
    setPage(p);
    window.scrollTo(0, 0);
  };
  useEffect(() => {
    const listener = () => { const next = location.hash.slice(1) || "home"; setPage(next); setSection(pendingNavigation.current?.page === next ? pendingNavigation.current.tab : ""); pendingNavigation.current = null; if (moduleMode[next]) setMode(moduleMode[next]); };
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
  const props = { schema, settings, refresh, onRefresh: reload, navigate, initialTab: section, mode };
  const visibleNav = navigation.filter(([key]) => !moduleMode[key] || moduleMode[key] === mode);
  return (
    <div className="app-shell" data-mode={mode}>
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
          {visibleNav.map(([key, label, Icon], i) => (
            <React.Fragment key={key}>
              {i === 0 && <span className="nav-group">{modeNames[mode]} workspace</span>}
              <button
                className={page === key ? "nav-item selected" : "nav-item"}
                aria-current={page === key ? "page" : undefined}
                onClick={() => navigate(key)}
              >
                <Icon size={18} />
                {key === "home" ? "Overview" : key === "journal" && mode !== "personal" ? "Notes & journal" : label}
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
          <div className="context-toolbar">
            <div className="mode-switch" role="group" aria-label="Workspace mode" style={{'--mode-index': modes.indexOf(mode)} as React.CSSProperties}>
              <span className="mode-slider" aria-hidden="true" />
              {modes.map((m,i) => {const Icon=[Briefcase,GraduationCap,Compass][i];return <button key={m} aria-pressed={mode===m} onClick={()=>{setMode(m);navigate('home')}}><Icon size={17}/><span>{modeNames[m]}</span></button>})}
            </div>
            <button className="primary quick-add-button" disabled={!loaded} onClick={()=>setCapture(true)}><Plus size={17}/>Quick add</button>
          </div>
          <header className="page-head" key={`header-${page}-${mode}`}>
            <div>
              {page === "home" && <div className="eyebrow">
                {new Date().toLocaleDateString(undefined, {
                  weekday: "long", month: "long", day: "numeric",
                  timeZone: settings.timezone || "UTC",
                })}
              </div>}
              <h1>
                {page === "home" ? modeNames[mode] : page === "journal" && mode !== "personal" ? "Notes & journal" : navigation.find((x) => x[0] === page)?.[1] || "Settings"}
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
            <div className="page-content" key={`content-${page}-${mode}`}>
              {page === "home" ? (
                <ContextHome {...props} onCapture={()=>setCapture(true)} />
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
          <QuickCapture open={capture} onClose={()=>setCapture(false)} mode={mode} zone={settings.timezone || "UTC"} onSaved={reload}/>

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
