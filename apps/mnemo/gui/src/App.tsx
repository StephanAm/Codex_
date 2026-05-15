import { useCallback, useEffect, useState } from "react";
import { api, Note } from "./api";
import { ConfigPanel } from "./components/ConfigPanel";
import { NoteDetail } from "./components/NoteDetail";
import { NoteEditor } from "./components/NoteEditor";
import { NoteList } from "./components/NoteList";
import { SyncButton } from "./components/SyncButton";
import "./App.css";

type Mode = "view" | "add" | "edit" | "config";

export default function App() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [selected, setSelected] = useState<Note | null>(null);
  const [mode, setMode] = useState<Mode>("view");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  const loadNotes = useCallback(async (q?: string) => {
    try {
      const result = await api.notes.list(q ? { q } : {});
      setNotes(result);
      setError("");
    } catch {
      setError("Cannot reach the API server. Run: uv run note-api");
    }
  }, []);

  useEffect(() => {
    loadNotes(query);
  }, [query, loadNotes]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (mode !== "view") return;
      if (e.key === "n" && !e.ctrlKey && !e.metaKey) setMode("add");
      if (e.key === "e" && selected) setMode("edit");
      if (e.key === "Escape") setMode("view");
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [mode, selected]);

  async function handleSave(body: string) {
    if (!body) return;
    if (mode === "add") {
      const note = await api.notes.create(body);
      await loadNotes(query);
      setSelected(note);
    } else if (mode === "edit" && selected) {
      const note = await api.notes.update(selected.id, body);
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
    if (mode === "config") {
      return <ConfigPanel onClose={() => setMode("view")} />;
    }
    if (mode === "add") {
      return (
        <NoteEditor
          onSave={handleSave}
          onCancel={() => setMode("view")}
        />
      );
    }
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
    if (selected) {
      return (
        <NoteDetail
          note={selected}
          onEdit={() => setMode("edit")}
          onDelete={handleDelete}
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

  return (
    <div className="app">
      <header className="app-header">
        <span className="app-title">note-taker</span>
        <div className="app-header-actions">
          <SyncButton onSyncComplete={() => loadNotes(query)} />
          <button className="btn btn-secondary" onClick={() => setMode("config")}>
            Config
          </button>
        </div>
      </header>

      <div className="app-body">
        <NoteList
          notes={notes}
          selectedId={selected?.id ?? null}
          query={query}
          onSelect={handleSelect}
          onQueryChange={setQuery}
          onAdd={() => setMode("add")}
        />
        <main className="main-panel">
          {mainContent()}
        </main>
      </div>
    </div>
  );
}
