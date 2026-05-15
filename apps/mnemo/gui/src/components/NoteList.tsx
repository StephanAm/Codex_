import { Note } from "../api";
import { TagEntityPicker } from "./TagEntityPicker";

interface Props {
  notes: Note[];
  selectedId: number | null;
  query: string;
  filterTags: string[];
  filterEntities: string[];
  allTags: string[];
  allEntities: string[];
  timePeriod: string;
  dateFrom: string;
  dateTo: string;
  onSelect: (note: Note) => void;
  onQueryChange: (q: string) => void;
  onFilterTagsChange: (tags: string[]) => void;
  onFilterEntitiesChange: (entities: string[]) => void;
  onTimePeriodChange: (p: string) => void;
  onDateFromChange: (d: string) => void;
  onDateToChange: (d: string) => void;
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

export function NoteList({ notes, selectedId, query, filterTags, filterEntities, allTags, allEntities, timePeriod, dateFrom, dateTo, onSelect, onQueryChange, onFilterTagsChange, onFilterEntitiesChange, onTimePeriodChange, onDateFromChange, onDateToChange, onAdd }: Props) {
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
      <div className="note-list-filters">
        <div className="filter-select-wrap">
          <select
            className="filter-select"
            value={timePeriod}
            onChange={e => onTimePeriodChange(e.target.value)}
          >
            <option value="all">Any time</option>
            <option value="today">Today</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="3m">Last 3 months</option>
            <option value="1y">Last year</option>
            <option value="custom">Custom range…</option>
          </select>
          <span className="filter-select-arrow">▾</span>
        </div>
        {timePeriod === "custom" && (
          <div className="filter-date-range">
            <label className="filter-date-label">
              From
              <input
                type="date"
                className="filter-date-input"
                value={dateFrom}
                onChange={e => onDateFromChange(e.target.value)}
              />
            </label>
            <label className="filter-date-label">
              To
              <input
                type="date"
                className="filter-date-input"
                value={dateTo}
                onChange={e => onDateToChange(e.target.value)}
              />
            </label>
          </div>
        )}
        <TagEntityPicker
          label="Tags"
          prefix="#"
          kind="tag"
          allItems={allTags}
          selected={filterTags}
          onChange={onFilterTagsChange}
          allowNew={false}
          dropdownDir="down"
          compact
        />
        <TagEntityPicker
          label="Refs"
          prefix="@"
          kind="entity"
          allItems={allEntities}
          selected={filterEntities}
          onChange={onFilterEntitiesChange}
          allowNew={false}
          dropdownDir="down"
          compact
        />
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
            {(note.tags.length > 0 || note.entities.length > 0) && (
              <div className="note-list-item-tags">
                {note.tags.map(t => (
                  <span key={t} className="badge badge-tag">#{t}</span>
                ))}
                {note.entities.map(e => (
                  <span key={e} className="badge badge-entity">@{e}</span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
