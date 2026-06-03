// Copyright (C) 2026 Stephan Marais
// SPDX-License-Identifier: AGPL-3.0-or-later

import { useState } from "react";
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

// ── grouping helpers ──────────────────────────────────────────────────────────

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
      kindOrder.set(inst.type.id, { kindId: inst.type.id, kindName: inst.type.plural || inst.type.name });
    }
    instanceGroups.push({ kindId: inst.type.id, instanceName: inst.name, notes: kindNotes });
  }

  return [...kindOrder.values()].map(({ kindId, kindName }) => ({
    kindName,
    instances: instanceGroups.filter(g => g.kindId === kindId),
  }));
}

// ── markdown generation ───────────────────────────────────────────────────────

function noteToMd(note: Note): string {
  const meta: string[] = [formatTime(note.created_at)];
  if (note.tags.length > 0)       meta.push(note.tags.map(t => `#${t}`).join(" "));
  if (note.references.length > 0) meta.push(note.references.map(r => `@${r}`).join(" "));
  return `${note.body}\n\n*${meta.join(" · ")}*`;
}

const DIVIDER = "\n\n---\n\n";

function generateMarkdown(notes: Note[], groupBy: BulletinGroupBy, instances: Instance[]): string {
  if (groupBy === "kind") {
    const kindGroups = buildKindGroups(notes, instances);
    const matchedIds = new Set(kindGroups.flatMap(k => k.instances.flatMap(i => i.notes.map(n => n.id))));
    const other = notes.filter(n => !matchedIds.has(n.id));

    const sections: string[] = kindGroups.map(({ kindName, instances: instGroups }) => {
      const parts = instGroups.map(({ instanceName, notes: instNotes }) =>
        `### ${instanceName}\n\n${instNotes.map(noteToMd).join(DIVIDER)}`
      );
      return `## ${kindName}\n\n${parts.join("\n\n")}`;
    });
    if (other.length > 0) {
      sections.push(`## other\n\n${other.map(noteToMd).join(DIVIDER)}`);
    }
    return sections.join("\n\n");
  }

  const groups =
    groupBy === "date"      ? buildDateGroups(notes) :
    groupBy === "tag"       ? buildTagGroups(notes)  :
    groupBy === "reference" ? buildReferenceGroups(notes) :
    [{ heading: "", notes }];

  return groups.map(({ heading, notes: groupNotes }) => {
    const body = groupNotes.map(noteToMd).join(DIVIDER);
    return heading ? `## ${heading}\n\n${body}` : body;
  }).join("\n\n");
}

// ── render helpers ────────────────────────────────────────────────────────────

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

// ── component ─────────────────────────────────────────────────────────────────

export function BulletinView({ notes, groupBy, instances }: Props) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    const md = generateMarkdown(notes, groupBy, instances);
    navigator.clipboard.writeText(md).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  if (notes.length === 0) {
    return (
      <div className="empty-state">
        <p>No notes match the current filters.</p>
      </div>
    );
  }

  const toolbar = (
    <div className="bulletin-toolbar">
      <button className="btn btn-secondary bulletin-copy-btn" onClick={handleCopy}>
        {copied ? "copied" : "copy markdown"}
      </button>
    </div>
  );

  if (groupBy === "kind") {
    const kindGroups = buildKindGroups(notes, instances);
    const matchedNoteIds = new Set(
      kindGroups.flatMap(k => k.instances.flatMap(i => i.notes.map(n => n.id)))
    );
    const other = notes.filter(n => !matchedNoteIds.has(n.id));
    return (
      <div className="bulletin-view">
        {toolbar}
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
      {toolbar}
      {groups.map(({ heading, notes: groupNotes }, i) => (
        <div key={heading || i} className="bulletin-group">
          {heading && <GroupHeading label={heading} />}
          {groupNotes.map(n => <BulletinNote key={n.id} note={n} />)}
        </div>
      ))}
    </div>
  );
}
