import { Note } from "../api";

interface Props {
  notes: Note[];
  selectedId: number | null;
  query: string;
  onSelect: (note: Note) => void;
  onQueryChange: (q: string) => void;
  onAdd: () => void;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
    " " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function firstLine(body: string) {
  return body.split("\n").find(l => l.trim()) ?? "";
}

export function NoteList({ notes, selectedId, query, onSelect, onQueryChange, onAdd }: Props) {
  return (
    <div className="note-list-panel">
      <div className="note-list-toolbar">
        <input
          className="search-input"
          type="search"
          placeholder="Search…"
          value={query}
          onChange={e => onQueryChange(e.target.value)}
        />
        <button className="btn-icon" title="New note (N)" onClick={onAdd}>+</button>
      </div>
      <ul className="note-list">
        {notes.length === 0 && (
          <li className="note-list-empty">No notes. Press + to add one.</li>
        )}
        {notes.map(note => (
          <li
            key={note.id}
            className={`note-list-item${note.id === selectedId ? " selected" : ""}`}
            onClick={() => onSelect(note)}
          >
            <div className="note-list-item-title">{firstLine(note.body)}</div>
            <div className="note-list-item-meta">
              <span className="note-id">#{note.id}</span>
              <span className="note-date">{formatDate(note.created_at)}</span>
            </div>
            {note.tags.length > 0 && (
              <div className="note-list-item-tags">
                {note.tags.map(t => (
                  <span key={t} className="badge badge-tag">#{t}</span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
