import { useRef, useState } from "react";
import { Note } from "../api";

interface Props {
  pinnedNotes: Note[];
  selectedId: number | null;
  onSelect: (note: Note) => void;
  onReorder: (notes: Note[]) => void;
  onAdd: () => void;
  className?: string;
}

function firstLine(body: string) {
  return body.split("\n")[0] || "";
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric", month: "short", year: "numeric",
  });
}

export function RecallSidebar({ pinnedNotes, selectedId, onSelect, onReorder, onAdd, className = "" }: Props) {
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);
  const didDragRef = useRef(false);

  function reorder(from: number, to: number): Note[] {
    const arr = [...pinnedNotes];
    const [item] = arr.splice(from, 1);
    arr.splice(to, 0, item);
    return arr;
  }

  return (
    <div className={`recall-sidebar${className ? " " + className : ""}`}>
      <div className="recall-sidebar-header">
        <div className="recall-section-label">recall</div>
        <button className="btn-icon recall-add-btn" title="New pinned note" onClick={onAdd}>+</button>
      </div>
      {pinnedNotes.length === 0 && (
        <span className="recall-sidebar-empty">no pins yet.</span>
      )}
      <ul
        className={`recall-list${dragIndex !== null ? " recall-list--dragging" : ""}`}
        onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDropIndex(null); }}
      >
        {pinnedNotes.map((note, i) => {
          const isActive = note.id === selectedId;
          const isDragging = dragIndex === i;
          const isDropTarget = dropIndex === i && dragIndex !== i;
          const cls = [
            "recall-item",
            isActive ? "recall-item--active" : "",
            isDragging ? "recall-item--dragging" : "",
            isDropTarget ? "recall-item--drop-target" : "",
          ].filter(Boolean).join(" ");

          return (
            <li
              key={note.uuid}
              className={cls}
              onClick={() => { if (didDragRef.current) { didDragRef.current = false; return; } onSelect(note); }}
              draggable
              onDragStart={e => { e.dataTransfer.setData("text/plain", String(i)); e.dataTransfer.effectAllowed = "move"; didDragRef.current = true; setDragIndex(i); }}
              onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setDropIndex(i); }}
              onDrop={e => {
                e.preventDefault();
                if (dragIndex !== null && dragIndex !== i) {
                  onReorder(reorder(dragIndex, i));
                }
                setDragIndex(null);
                setDropIndex(null);
              }}
              onDragEnd={() => { setDragIndex(null); setDropIndex(null); }}
            >
              <div className="recall-item-title">{firstLine(note.body)}</div>
              <div className="recall-item-meta">
                <span className="recall-item-date">{formatDate(note.created_at)}</span>
                {note.tags.map(t => (
                  <span key={t} className="recall-item-tag">#{t}</span>
                ))}
              </div>
              <span
                className="recall-item-handle"
                draggable={false}
                onMouseDown={e => e.stopPropagation()}
              >⠿</span>
            </li>
          );
        })}
        {dragIndex !== null && (
          <li
            className={`recall-item-sentinel${dropIndex === pinnedNotes.length ? " recall-item-sentinel--active" : ""}`}
            onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setDropIndex(pinnedNotes.length); }}
            onDrop={e => {
              e.preventDefault();
              if (dragIndex !== null) onReorder(reorder(dragIndex, pinnedNotes.length));
              setDragIndex(null);
              setDropIndex(null);
            }}
          />
        )}
      </ul>
    </div>
  );
}
