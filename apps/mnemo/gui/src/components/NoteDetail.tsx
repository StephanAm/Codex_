import { Note } from "../api";
import { TagBadge } from "./TagBadge";

interface Props {
  note: Note;
  onEdit: () => void;
  onDelete: () => void;
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function renderBody(body: string) {
  return body.split("\n").map((line, li) => (
    <p key={li} className="note-body-line">
      {line.split(/(\s+)/).map((part, pi) => {
        if (/^#\w/.test(part)) return <span key={pi} className="highlight-tag">{part}</span>;
        if (/^@\w/.test(part)) return <span key={pi} className="highlight-entity">{part}</span>;
        return part;
      })}
    </p>
  ));
}

export function NoteDetail({ note, onEdit, onDelete }: Props) {
  return (
    <div className="note-detail">
      <div className="note-detail-header">
        <span className="note-detail-id">#{note.id}</span>
        <span className="note-detail-date">{formatDateTime(note.created_at)}</span>
        <div className="note-detail-actions">
          <button className="btn btn-secondary" onClick={onEdit}>Edit</button>
          <button className="btn btn-danger" onClick={onDelete}>Delete</button>
        </div>
      </div>
      <div className="note-detail-body">{renderBody(note.body)}</div>
      {(note.tags.length > 0 || note.entities.length > 0) && (
        <div className="note-detail-meta">
          {note.tags.map(t => <TagBadge key={t} text={t} kind="tag" />)}
          {note.entities.map(e => <TagBadge key={e} text={e} kind="entity" />)}
        </div>
      )}
      <div className="note-detail-updated">
        Updated {formatDateTime(note.updated_at)}
      </div>
    </div>
  );
}
