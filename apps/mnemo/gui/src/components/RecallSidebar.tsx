import { useState } from "react";
import { Note } from "../api";

interface Props {
  pinnedNotes: Note[];
  selectedId: number | null;
  onSelect: (note: Note) => void;
  onReorder: (notes: Note[]) => void;
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

export function RecallSidebar({ pinnedNotes, selectedId, onSelect, onReorder, className = "" }: Props) {
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

  function reorder(from: number, to: number): Note[] {
    const arr = [...pinnedNotes];
    const [item] = arr.splice(from, 1);
    arr.splice(to, 0, item);
    return arr;
  }

  return (
    <div className={`recall-sidebar${className ? " " + className : ""}`}>
      <div className="recall-section-label">recall</div>
      {pinnedNotes.length === 0 && (
        <span className="recall-sidebar-empty">no pins yet.</span>
      )}
      <ul className="recall-list">
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
              onClick={() => onSelect(note)}
              draggable
              onDragStart={() => setDragIndex(i)}
              onDragOver={e => { e.preventDefault(); setDropIndex(i); }}
              onDragLeave={() => setDropIndex(null)}
              onDrop={() => {
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
      </ul>
    </div>
  );
}
