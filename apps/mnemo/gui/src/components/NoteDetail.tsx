import { openUrl } from "@tauri-apps/plugin-opener";
import { Note } from "../api";
import { TagBadge } from "./TagBadge";

interface Props {
  note: Note;
  onEdit: () => void;
  onDelete: () => void;
  isPinned: boolean;
  onPin: () => void;
  onUnpin: () => void;
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

const DATE_EXPR_RE = /~\{(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?)\}/g;

function formatDateToken(iso: string): string {
  const tIdx = iso.indexOf("T");
  const datePart = tIdx === -1 ? iso : iso.slice(0, tIdx);
  const timePart = tIdx === -1 ? null : iso.slice(tIdx + 1);
  const [year, month, day] = datePart.split("-").map(Number);
  const label = new Date(year, month - 1, day).toLocaleDateString(undefined, {
    day: "numeric", month: "short", year: "numeric",
  });
  return timePart ? `${label} at ${timePart}` : label;
}

const URL_RE = /^https?:\/\/\S+$/;

type Segment = { type: "date"; iso: string } | { type: "text"; value: string };

function renderLine(line: string, li: number) {
  const segments: Segment[] = [];
  let last = 0;
  for (const m of line.matchAll(DATE_EXPR_RE)) {
    if (m.index! > last) segments.push({ type: "text", value: line.slice(last, m.index) });
    segments.push({ type: "date", iso: m[1] });
    last = m.index! + m[0].length;
  }
  if (last < line.length) segments.push({ type: "text", value: line.slice(last) });

  return (
    <p key={li} className="note-body-line">
      {segments.map((seg, si) => {
        if (seg.type === "date")
          return <span key={si} className="highlight-date" title={seg.iso}>{formatDateToken(seg.iso)}</span>;
        return seg.value.split(/(\s+)/).map((part, pi) => {
          if (/^#\w/.test(part)) return <span key={`${si}-${pi}`} className="highlight-tag">{part}</span>;
          if (/^@\w/.test(part)) return <span key={`${si}-${pi}`} className="highlight-reference">{part}</span>;
          const trail = part.match(/[.,;:!?)]+$/)?.[0] ?? "";
          const url = trail ? part.slice(0, -trail.length) : part;
          if (URL_RE.test(url)) return (
            <span key={`${si}-${pi}`}>
              <a className="highlight-url" onClick={() => { void openUrl(url); }}>{url}</a>{trail}
            </span>
          );
          return part;
        });
      })}
    </p>
  );
}

function renderBody(body: string) {
  return body.split("\n").map((line, li) => renderLine(line, li));
}

export function NoteDetail({ note, onEdit, onDelete, isPinned, onPin, onUnpin }: Props) {
  return (
    <div className="note-detail">
      <div className="note-detail-header">
        <span className="note-detail-id">#{note.id}</span>
        <span className="note-detail-date">{formatDateTime(note.created_at)}</span>
        <div className="note-detail-actions">
          <button className="btn-icon btn-icon--flag" title={isPinned ? "unpin" : "pin"} onClick={isPinned ? onUnpin : onPin}>
            {isPinned ? "◉" : "◎"}
          </button>
          <button className="btn-icon" title="edit" onClick={onEdit}>✎</button>
          <button className="btn-icon btn-icon--danger" title="delete" onClick={onDelete}>✕</button>
        </div>
      </div>
      <div className="note-detail-body">{renderBody(note.body)}</div>
      {(note.tags.length > 0 || note.references.length > 0) && (
        <div className="note-detail-meta">
          {note.tags.map(t => <TagBadge key={t} text={t} kind="tag" />)}
          {note.references.map(r => <TagBadge key={r} text={r} kind="reference" />)}
        </div>
      )}
      <div className="note-detail-updated">
        Updated {formatDateTime(note.updated_at)}
      </div>
    </div>
  );
}
