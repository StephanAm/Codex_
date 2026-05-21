import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, Instance, InstanceKind, Note } from "./api";
import { ConfigPanel } from "./components/ConfigPanel";
import { InstanceDetail } from "./components/InstanceDetail";
import { InstanceSidebar } from "./components/InstanceSidebar";
import { KindDetail } from "./components/KindDetail";
import { NoteDetail } from "./components/NoteDetail";
import { NoteEditor } from "./components/NoteEditor";
import { NoteList } from "./components/NoteList";
import { RecallSidebar } from "./components/RecallSidebar";
import { SplashScreen } from "./components/SplashScreen";
import { SyncButton, SyncState } from "./components/SyncButton";
import "./App.css";

type Mode = "view" | "add" | "edit" | "config";

function timePeriodRange(period: string): [Date | null, Date | null] {
  const now = new Date();
  const startOfDay = (d: Date) => { d.setHours(0, 0, 0, 0); return d; };
  const endOfDay   = (d: Date) => { d.setHours(23, 59, 59, 999); return d; };
  switch (period) {
    case "today": return [startOfDay(new Date(now)), null];
    case "yesterday": {
      const d = new Date(now);
      d.setDate(d.getDate() - 1);
      return [startOfDay(new Date(d)), endOfDay(new Date(d))];
    }
    case "thisweek": {
      const d = new Date(now);
      d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); // Monday
      return [startOfDay(d), null];
    }
    case "thismonth": {
      return [new Date(now.getFullYear(), now.getMonth(), 1), null];
    }
    case "7d":  return [new Date(now.getTime() - 7   * 86400_000), null];
    case "30d": return [new Date(now.getTime() - 30  * 86400_000), null];
    case "3m":  return [new Date(now.getTime() - 90  * 86400_000), null];
    case "1y":  return [new Date(now.getTime() - 365 * 86400_000), null];
    default:    return [null, null];
  }
}

export default function App() {
  const [ready, setReady]       = useState(false);
  const [notes, setNotes]       = useState<Note[]>([]);
  const [selected, setSelected] = useState<Note | null>(null);
  const [mode, setMode]         = useState<Mode>("view");
  const [query, setQuery]       = useState("");
  const [error, setError]       = useState("");
  const [filterTags, setFilterTags]               = useState<string[]>([]);
  const [filterReferences, setFilterReferences]   = useState<string[]>([]);
  const [timePeriod, setTimePeriod]           = useState("all");
  const [dateFrom, setDateFrom]               = useState("");
  const [dateTo, setDateTo]                   = useState("");
  const [pinnedNotes, setPinnedNotes]         = useState<Note[]>([]);
  const [selectedInstance, setSelectedInstance] = useState<Instance | null>(null);
  const [selectedKind, setSelectedKind] = useState<InstanceKind | null>(null);
  const [kindsVersion, setKindsVersion] = useState(0);

  // ── responsive layout ───────────────────────────────────────────────────────
  const SIDEBAR_BREAKPOINT = 640;
  const [narrow, setNarrow]           = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeSidebar, setActiveSidebar] = useState<"log" | "recall" | "instances">("log");

  useEffect(() => {
    const ro = new ResizeObserver(entries => {
      setNarrow(entries[0].contentRect.width < SIDEBAR_BREAKPOINT);
    });
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, []);

  useEffect(() => { if (narrow) setSidebarOpen(false); }, [narrow]);

  // ── sync state ──────────────────────────────────────────────────────────────
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [syncMsg,   setSyncMsg]   = useState("");
  const [debounceMs, setDebounceMs] = useState(600_000);
  const autopushTimer   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startupPullDone = useRef(false);

  const allTags        = useMemo(() => [...new Set(notes.flatMap(n => n.tags))].sort(),       [notes]);
  const allReferences  = useMemo(() => [...new Set(notes.flatMap(n => n.references))].sort(), [notes]);

  const displayedNotes = useMemo(() => {
    let from: Date | null;
    let to: Date | null;
    if (timePeriod === "custom") {
      from = dateFrom ? new Date(dateFrom) : null;
      to   = dateTo   ? new Date(dateTo + "T23:59:59") : null;
    } else {
      [from, to] = timePeriodRange(timePeriod);
    }
    return notes
      .filter(n => !from || new Date(n.created_at) >= from)
      .filter(n => !to   || new Date(n.created_at) <= to)
      .filter(n => filterTags.length     === 0 || n.tags.some(t => filterTags.includes(t)))
      .filter(n => filterReferences.length === 0 || n.references.some(r => filterReferences.includes(r)));
  }, [notes, filterTags, filterReferences, timePeriod, dateFrom, dateTo]);

  const loadNotes = useCallback(async (q?: string) => {
    try {
      const result = await api.notes.list(q ? { q } : {});
      setNotes(result);
      setError("");
    } catch {
      setError("Cannot reach the API server.");
    }
  }, []);

  const loadPins = useCallback(async () => {
    try {
      const result = await api.pins.list();
      setPinnedNotes(result.notes);
    } catch { /* server not up yet */ }
  }, []);

  useEffect(() => {
    if (ready) loadNotes(query);
  }, [query, loadNotes, ready]);

  useEffect(() => {
    if (ready) loadPins();
  }, [ready, loadPins]);

  const handlePin = useCallback(async (note: Note) => {
    const next = [...pinnedNotes, note];
    await api.pins.save(next.map(n => n.uuid));
    setPinnedNotes(next);
  }, [pinnedNotes]);

  const handleUnpin = useCallback(async (note: Note) => {
    const next = pinnedNotes.filter(n => n.uuid !== note.uuid);
    await api.pins.save(next.map(n => n.uuid));
    setPinnedNotes(next);
  }, [pinnedNotes]);

  const handlePinReorder = useCallback(async (reordered: Note[]) => {
    await api.pins.save(reordered.map(n => n.uuid));
    setPinnedNotes(reordered);
  }, []);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (mode !== "view") return;
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "n" && !e.ctrlKey && !e.metaKey) { e.preventDefault(); setMode("add"); }
      if (e.key === "e" && selected) { e.preventDefault(); setMode("edit"); }
      if (e.key === "Escape") setMode("view");
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const list = activeSidebar === "recall" ? pinnedNotes : displayedNotes;
        const idx = list.findIndex(n => n.id === selected?.id);
        const next = e.key === "ArrowDown"
          ? list[idx + 1] ?? list[0]
          : list[idx - 1] ?? list[list.length - 1];
        if (next) setSelected(next);
      }
      if (e.key === "Enter" && selected) { e.preventDefault(); setMode("edit"); }
      if (e.key === "p" && e.ctrlKey && selected) {
        e.preventDefault();
        const isPinned = pinnedNotes.some(n => n.uuid === selected.uuid);
        isPinned ? handleUnpin(selected) : handlePin(selected);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [mode, selected, displayedNotes, activeSidebar, pinnedNotes, handlePin, handleUnpin]);

  useEffect(() => {
    function handleSidebarKey(e: KeyboardEvent) {
      if (!e.metaKey && !e.ctrlKey) return;
      if (e.key === "1") { e.preventDefault(); setActiveSidebar("log");      if (narrow) setSidebarOpen(true); }
      if (e.key === "2") { e.preventDefault(); setActiveSidebar("recall");   if (narrow) setSidebarOpen(true); }
      if (e.key === "3") { e.preventDefault(); setActiveSidebar("instances"); if (narrow) setSidebarOpen(true); }
    }
    window.addEventListener("keydown", handleSidebarKey);
    return () => window.removeEventListener("keydown", handleSidebarKey);
  }, [narrow]);

  // ── sync logic ──────────────────────────────────────────────────────────────

  const runSync = useCallback(async (mode: "push" | "pull" | "full" = "full") => {
    if (syncState === "syncing" || syncState === "connecting") return;
    setSyncState("syncing");
    setSyncMsg("");
    try {
      const fn = mode === "push" ? api.sync.push
               : mode === "pull" ? api.sync.pull
               : api.sync.run;
      const res = await fn();
      if (res.needs_auth) {
        setSyncState("needs_auth");
        setSyncMsg("Google Drive is not authorized.");
      } else {
        setSyncState("idle");
        setSyncMsg(res.message);
        if (mode !== "push") await loadNotes(query);
      }
    } catch (err) {
      setSyncState("idle");
      setSyncMsg(String(err));
    }
  }, [syncState, loadNotes, query]);

  const handleConnect = useCallback(async () => {
    setSyncState("connecting");
    setSyncMsg("A browser window has been opened. Complete authorization to continue.");
    try {
      await api.auth.googleConnect();
      setSyncMsg("");
      await runSync("full");
    } catch (err) {
      setSyncState("idle");
      setSyncMsg(String(err));
    }
  }, [runSync]);

  const scheduleAutopush = useCallback(() => {
    if (autopushTimer.current !== null) clearTimeout(autopushTimer.current);
    autopushTimer.current = setTimeout(() => {
      autopushTimer.current = null;
      runSync("push");
    }, debounceMs);
  }, [runSync, debounceMs]);

  // Load debounce value from config once ready
  useEffect(() => {
    if (!ready) return;
    api.config.get().then(c => setDebounceMs(c.autosync_debounce_ms));
  }, [ready]);

  // Startup pull — once, after backend is ready
  useEffect(() => {
    if (!ready || startupPullDone.current) return;
    startupPullDone.current = true;
    runSync("pull");
  }, [ready, runSync]);


  // ── note mutations ──────────────────────────────────────────────────────────

  async function handleSave(body: string, tags: string[], references: string[]) {
    if (!body && tags.length === 0 && references.length === 0) return;
    if (mode === "add") {
      const note = await api.notes.create(body, tags, references);
      await loadNotes(query);
      setSelected(note);
    } else if (mode === "edit" && selected) {
      const note = await api.notes.update(selected.id, body, tags, references);
      await loadNotes(query);
      setSelected(note);
    }
    setMode("view");
    scheduleAutopush();
  }

  async function handleDelete() {
    if (!selected) return;
    if (!confirm(`Delete note #${selected.id}?`)) return;
    await api.notes.delete(selected.id);
    setSelected(null);
    await loadNotes(query);
    setMode("view");
    scheduleAutopush();
  }

  function handleSelect(note: Note) {
    setSelected(note);
    setMode("view");
    if (narrow) setSidebarOpen(false);
  }

  function handleSelectKind(kind: InstanceKind) {
    setSelectedKind(kind);
    setSelectedInstance(null);
    if (narrow) setSidebarOpen(false);
  }

  function handleSelectInstance(instance: Instance) {
    setSelectedInstance(instance);
    if (narrow) setSidebarOpen(false);
  }

  function handleKindUpdated(kind: InstanceKind) {
    setSelectedKind(kind);
    setKindsVersion(v => v + 1);
  }

  function handleKindDeleted(id: number) {
    if (selectedKind?.id === id) setSelectedKind(null);
    setKindsVersion(v => v + 1);
  }

  const mainContent = () => {
    if (activeSidebar === "instances" && selectedInstance) {
      return (
        <InstanceDetail
          instance={selectedInstance}
          onUpdated={instance => { setSelectedInstance(instance); setKindsVersion(v => v + 1); }}
          onDeleted={() => { setSelectedInstance(null); setKindsVersion(v => v + 1); }}
        />
      );
    }
    if (activeSidebar === "instances" && selectedKind) {
      return (
        <KindDetail
          kind={selectedKind}
          onUpdated={handleKindUpdated}
          onDeleted={handleKindDeleted}
          onSelectInstance={handleSelectInstance}
        />
      );
    }
    if (mode === "config") return <ConfigPanel onClose={() => setMode("view")} />;
    if (mode === "add") return <NoteEditor onSave={handleSave} onCancel={() => setMode("view")} />;
    if (mode === "edit" && selected) {
      return (
        <NoteEditor
          initialBody={selected.body}
          initialTags={selected.tags}
          initialReferences={selected.references}
          onSave={handleSave}
          onCancel={() => setMode("view")}
        />
      );
    }
    if (selected) {
      const isPinned = pinnedNotes.some(n => n.uuid === selected.uuid);
      return (
        <NoteDetail
          note={selected}
          onEdit={() => setMode("edit")}
          onDelete={handleDelete}
          isPinned={isPinned}
          onPin={() => handlePin(selected)}
          onUnpin={() => handleUnpin(selected)}
        />
      );
    }
    return (
      <div className="empty-state">
        {error
          ? <p className="error-msg">{error}</p>
          : <p>Select a note, or press <kbd>N</kbd> to create one.</p>
        }
      </div>
    );
  };

  if (!ready) return <SplashScreen onReady={() => setReady(true)} />;

  return (
    <div className="app">
      <span className="app-version">v{__APP_VERSION__}</span>
      <header className="app-header">
        {narrow && (
          <button
            className="btn-icon"
            title="Toggle note list"
            onClick={() => setSidebarOpen(o => !o)}
          >≡</button>
        )}
        <span className="app-title">MNEMO<span className="app-title-cursor">_</span></span>
        <span className="app-header-status">{syncMsg}</span>
        <div className="app-header-actions">
          <SyncButton
            syncState={syncState}
            onSync={() => runSync("full")}
            onConnect={handleConnect}
          />
          <button className="btn btn-secondary" onClick={() => setMode("config")}>
            Config
          </button>
        </div>
      </header>

      <div className="app-body">
        <div className="rail">
          <span
            className={`rail-glyph rail-glyph--log${activeSidebar === "log" ? " rail-glyph--active" : ""}`}
            data-label="log"
            onClick={() => { setActiveSidebar("log"); if (narrow) setSidebarOpen(true); }}
          >≡</span>
          <span
            className={`rail-glyph rail-glyph--recall${activeSidebar === "recall" ? " rail-glyph--active" : ""}`}
            data-label="recall"
            onClick={() => { setActiveSidebar("recall"); if (narrow) setSidebarOpen(true); }}
          >◎</span>
          <span
            className={`rail-glyph rail-glyph--instances${activeSidebar === "instances" ? " rail-glyph--active" : ""}`}
            data-label="instances"
            onClick={() => { setActiveSidebar("instances"); if (narrow) setSidebarOpen(true); }}
          >◈</span>
        </div>
        {activeSidebar === "log" && (
          <NoteList
            notes={displayedNotes}
            selectedId={selected?.id ?? null}
            query={query}
            filterTags={filterTags}
            filterReferences={filterReferences}
            allTags={allTags}
            allReferences={allReferences}
            timePeriod={timePeriod}
            dateFrom={dateFrom}
            dateTo={dateTo}
            onSelect={handleSelect}
            onQueryChange={setQuery}
            onFilterTagsChange={setFilterTags}
            onFilterReferencesChange={setFilterReferences}
            onTimePeriodChange={setTimePeriod}
            onDateFromChange={setDateFrom}
            onDateToChange={setDateTo}
            onAdd={() => setMode("add")}
            className={narrow ? (sidebarOpen ? "note-list-panel--overlay" : "note-list-panel--hidden") : ""}
          />
        )}
        {activeSidebar === "instances" && (
          <InstanceSidebar
            selectedId={selectedInstance?.id ?? null}
            selectedKindId={selectedKind?.id ?? null}
            onSelect={handleSelectInstance}
            onSelectKind={handleSelectKind}
            reloadKey={kindsVersion}
            className={narrow ? (sidebarOpen ? "note-list-panel--overlay" : "note-list-panel--hidden") : ""}
          />
        )}
        {activeSidebar === "recall" && (
          <RecallSidebar
            pinnedNotes={pinnedNotes}
            selectedId={selected?.id ?? null}
            onSelect={handleSelect}
            onReorder={handlePinReorder}
            className={narrow ? (sidebarOpen ? "note-list-panel--overlay" : "note-list-panel--hidden") : ""}
          />
        )}
        <main className="main-panel">
          <div className="mnemo-watermark" aria-hidden="true">
            <div className="mnemo-watermark__inner">
              <div className="mnemo-watermark__logo">
                <span className="mnemo-watermark__text">MNEMO</span><span className="mnemo-watermark__underscore">_</span>
              </div>
              <div className="mnemo-watermark__tagline">Remember everything</div>
            </div>
          </div>
          {mainContent()}
        </main>
      </div>
    </div>
  );
}
