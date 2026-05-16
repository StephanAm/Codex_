import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Note } from "./api";
import { ConfigPanel } from "./components/ConfigPanel";
import { NoteDetail } from "./components/NoteDetail";
import { NoteEditor } from "./components/NoteEditor";
import { NoteList } from "./components/NoteList";
import { SplashScreen } from "./components/SplashScreen";
import { SyncButton } from "./components/SyncButton";
import "./App.css";

type Mode = "view" | "add" | "edit" | "config";

function timePeriodCutoff(period: string): Date | null {
  const now = new Date();
  switch (period) {
    case "today": { const d = new Date(now); d.setHours(0, 0, 0, 0); return d; }
    case "7d":  return new Date(now.getTime() - 7  * 86400_000);
    case "30d": return new Date(now.getTime() - 30 * 86400_000);
    case "3m":  return new Date(now.getTime() - 90 * 86400_000);
    case "1y":  return new Date(now.getTime() - 365 * 86400_000);
    default:    return null;
  }
}

export default function App() {
  const [ready, setReady]       = useState(false);
  const [notes, setNotes]       = useState<Note[]>([]);
  const [selected, setSelected] = useState<Note | null>(null);
  const [mode, setMode]         = useState<Mode>("view");
  const [query, setQuery]       = useState("");
  const [error, setError]       = useState("");
  const [filterTags, setFilterTags]           = useState<string[]>([]);
  const [filterEntities, setFilterEntities]   = useState<string[]>([]);
  const [timePeriod, setTimePeriod]           = useState("all");
  const [dateFrom, setDateFrom]               = useState("");
  const [dateTo, setDateTo]                   = useState("");

  const allTags     = useMemo(() => [...new Set(notes.flatMap(n => n.tags))].sort(),     [notes]);
  const allEntities = useMemo(() => [...new Set(notes.flatMap(n => n.entities))].sort(), [notes]);

  const displayedNotes = useMemo(() => {
    let from: Date | null;
    let to: Date | null = null;
    if (timePeriod === "custom") {
      from = dateFrom ? new Date(dateFrom) : null;
      to   = dateTo   ? new Date(dateTo + "T23:59:59") : null;
    } else {
      from = timePeriodCutoff(timePeriod);
    }
    return notes
      .filter(n => !from || new Date(n.created_at) >= from)
      .filter(n => !to   || new Date(n.created_at) <= to)
      .filter(n => filterTags.length     === 0 || n.tags.some(t => filterTags.includes(t)))
      .filter(n => filterEntities.length === 0 || n.entities.some(e => filterEntities.includes(e)));
  }, [notes, filterTags, filterEntities, timePeriod, dateFrom, dateTo]);

  const loadNotes = useCallback(async (q?: string) => {
    try {
      const result = await api.notes.list(q ? { q } : {});
      setNotes(result);
      setError("");
    } catch {
      setError("Cannot reach the API server.");
    }
  }, []);

  useEffect(() => {
    if (ready) loadNotes(query);
  }, [query, loadNotes, ready]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (mode !== "view") return;
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "n" && !e.ctrlKey && !e.metaKey) { e.preventDefault(); setMode("add"); }
      if (e.key === "e" && selected) setMode("edit");
      if (e.key === "Escape") setMode("view");
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [mode, selected]);

  async function handleSave(body: string, tags: string[], entities: string[]) {
    if (!body && tags.length === 0 && entities.length === 0) return;
    if (mode === "add") {
      const note = await api.notes.create(body, tags, entities);
      await loadNotes(query);
      setSelected(note);
    } else if (mode === "edit" && selected) {
      const note = await api.notes.update(selected.id, body, tags, entities);
      await loadNotes(query);
      setSelected(note);
    }
    setMode("view");
  }

  async function handleDelete() {
    if (!selected) return;
    if (!confirm(`Delete note #${selected.id}?`)) return;
    await api.notes.delete(selected.id);
    setSelected(null);
    await loadNotes(query);
    setMode("view");
  }

  function handleSelect(note: Note) {
    setSelected(note);
    setMode("view");
  }

  const mainContent = () => {
    if (mode === "config") return <ConfigPanel onClose={() => setMode("view")} />;
    if (mode === "add") return <NoteEditor onSave={handleSave} onCancel={() => setMode("view")} />;
    if (mode === "edit" && selected) {
      return (
        <NoteEditor
          initialBody={selected.body}
          initialTags={selected.tags}
          initialEntities={selected.entities}
          onSave={handleSave}
          onCancel={() => setMode("view")}
        />
      );
    }
    if (selected) return <NoteDetail note={selected} onEdit={() => setMode("edit")} onDelete={handleDelete} />;
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
      <header className="app-header">
        <span className="app-title">Mnemo</span>
        <div className="app-header-actions">
          <SyncButton onSyncComplete={() => loadNotes(query)} />
          <button className="btn btn-secondary" onClick={() => setMode("config")}>
            Config
          </button>
        </div>
      </header>

      <div className="app-body">
        <NoteList
          notes={displayedNotes}
          selectedId={selected?.id ?? null}
          query={query}
          filterTags={filterTags}
          filterEntities={filterEntities}
          allTags={allTags}
          allEntities={allEntities}
          timePeriod={timePeriod}
          dateFrom={dateFrom}
          dateTo={dateTo}
          onSelect={handleSelect}
          onQueryChange={setQuery}
          onFilterTagsChange={setFilterTags}
          onFilterEntitiesChange={setFilterEntities}
          onTimePeriodChange={setTimePeriod}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
          onAdd={() => setMode("add")}
        />
        <main className="main-panel">
          {mainContent()}
        </main>
      </div>
    </div>
  );
}
