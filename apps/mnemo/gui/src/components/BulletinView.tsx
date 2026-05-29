import { Instance, Note } from "../api";
import { BulletinGroupBy } from "./BulletinSidebar";

interface Props {
  notes: Note[];
  groupBy: BulletinGroupBy;
  instances: Instance[];
}

function formatDay(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: "short", year: "numeric", month: "short", day: "numeric",
  });
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function BulletinNote({ note }: { note: Note }) {
  return (
    <div className="bulletin-note">
      <div className="bulletin-note-body">{note.body}</div>
      <div className="bulletin-note-meta">
        <span className="bulletin-note-time">{formatTime(note.created_at)}</span>
        {note.tags.map(t => (
          <span key={t} className="badge badge-tag">#{t}</span>
        ))}
        {note.references.map(r => (
          <span key={r} className="badge badge-reference">@{r}</span>
        ))}
      </div>
    </div>
  );
}

function GroupHeading({ label }: { label: string }) {
  return <div className="bulletin-group-heading">{label}</div>;
}

function buildDateGroups(notes: Note[]) {
  const map = new Map<string, Note[]>();
  for (const n of notes) {
    const key = formatDay(n.created_at);
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(n);
  }
  return [...map.entries()].map(([day, notes]) => ({ heading: day, notes }));
}

function buildTagGroups(notes: Note[]) {
  const byTag = new Map<string, Note[]>();
  const untagged: Note[] = [];
  for (const n of notes) {
    if (n.tags.length === 0) { untagged.push(n); continue; }
    for (const t of n.tags) {
      if (!byTag.has(t)) byTag.set(t, []);
      byTag.get(t)!.push(n);
    }
  }
  const groups = [...byTag.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([tag, notes]) => ({ heading: `#${tag}`, notes }));
  if (untagged.length > 0) groups.push({ heading: "untagged", notes: untagged });
  return groups;
}

function buildReferenceGroups(notes: Note[]) {
  const byRef = new Map<string, Note[]>();
  const unreferenced: Note[] = [];
  for (const n of notes) {
    if (n.references.length === 0) { unreferenced.push(n); continue; }
    for (const r of n.references) {
      if (!byRef.has(r)) byRef.set(r, []);
      byRef.get(r)!.push(n);
    }
  }
  const groups = [...byRef.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([ref, notes]) => ({ heading: `@${ref}`, notes }));
  if (unreferenced.length > 0) groups.push({ heading: "unreferenced", notes: unreferenced });
  return groups;
}

function buildKindGroups(notes: Note[], instances: Instance[]) {
  const kindOrder = new Map<number, { kindName: string; kindId: number }>();
  const instanceGroups: { kindId: number; instanceName: string; notes: Note[] }[] = [];

  for (const inst of instances) {
    const kindNotes = notes.filter(n =>
      inst.references.some(r => n.references.includes(r.toLowerCase()))
    );
    if (kindNotes.length === 0) continue;
    if (!kindOrder.has(inst.type.id)) {
      kindOrder.set(inst.type.id, {
        kindId: inst.type.id,
        kindName: inst.type.plural || inst.type.name,
      });
    }
    instanceGroups.push({ kindId: inst.type.id, instanceName: inst.name, notes: kindNotes });
  }

  return [...kindOrder.values()].map(({ kindId, kindName }) => ({
    kindName,
    instances: instanceGroups.filter(g => g.kindId === kindId),
  }));
}

export function BulletinView({ notes, groupBy, instances }: Props) {
  if (notes.length === 0) {
    return (
      <div className="empty-state">
        <p>No notes match the current filters.</p>
      </div>
    );
  }

  if (groupBy === "kind") {
    const kindGroups = buildKindGroups(notes, instances);
    const matchedNoteIds = new Set(
      kindGroups.flatMap(k => k.instances.flatMap(i => i.notes.map(n => n.id)))
    );
    const other = notes.filter(n => !matchedNoteIds.has(n.id));
    return (
      <div className="bulletin-view">
        {kindGroups.map(({ kindName, instances: instGroups }) => (
          <div key={kindName} className="bulletin-kind-block">
            <div className="bulletin-kind-heading">{kindName}</div>
            {instGroups.map(({ instanceName, notes: instNotes }) => (
              <div key={instanceName} className="bulletin-instance-block">
                <div className="bulletin-instance-heading">{instanceName}</div>
                {instNotes.map(n => <BulletinNote key={n.id} note={n} />)}
              </div>
            ))}
          </div>
        ))}
        {other.length > 0 && (
          <div className="bulletin-kind-block">
            <div className="bulletin-kind-heading bulletin-kind-heading--other">other</div>
            {other.map(n => <BulletinNote key={n.id} note={n} />)}
          </div>
        )}
      </div>
    );
  }

  const groups =
    groupBy === "date"      ? buildDateGroups(notes) :
    groupBy === "tag"       ? buildTagGroups(notes)  :
    groupBy === "reference" ? buildReferenceGroups(notes) :
    [{ heading: "", notes }];

  return (
    <div className="bulletin-view">
      {groups.map(({ heading, notes: groupNotes }, i) => (
        <div key={heading || i} className="bulletin-group">
          {heading && <GroupHeading label={heading} />}
          {groupNotes.map(n => <BulletinNote key={n.id} note={n} />)}
        </div>
      ))}
    </div>
  );
}
