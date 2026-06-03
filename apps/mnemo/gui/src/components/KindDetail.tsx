// Copyright (C) 2026 Stephan Marais
// SPDX-License-Identifier: AGPL-3.0-or-later

import { useEffect, useState } from "react";
import { api, Instance, InstanceKind } from "../api";

interface Props {
  kind: InstanceKind;
  onUpdated: (kind: InstanceKind) => void;
  onDeleted: (id: number) => void;
  onSelectInstance: (instance: Instance) => void;
}

export function KindDetail({ kind, onUpdated, onDeleted, onSelectInstance }: Props) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(kind.name);
  const [plural, setPlural] = useState(kind.plural);
  const [description, setDescription] = useState(kind.description);
  const [instances, setInstances] = useState<Instance[]>([]);

  useEffect(() => {
    setName(kind.name);
    setPlural(kind.plural);
    setDescription(kind.description);
    setEditing(false);
    api.instances.list(kind.id).then(setInstances);
  }, [kind.id]);

  function cancelEdit() {
    setName(kind.name);
    setPlural(kind.plural);
    setDescription(kind.description);
    setEditing(false);
  }

  async function handleSave() {
    const trimmedName = name.trim();
    if (!trimmedName) return;
    const updated = await api.instanceKinds.update(
      kind.id,
      trimmedName,
      plural.trim(),
      description.trim(),
    );
    setEditing(false);
    onUpdated(updated);
  }

  async function handleDelete() {
    if (instances.length > 0) {
      alert(
        `Cannot delete "${kind.name}" — it has ${instances.length} ${instances.length === 1 ? "instance" : "instances"}. Delete all instances first.`,
      );
      return;
    }
    if (!confirm(`Delete kind "${kind.name}"?`)) return;
    await api.instanceKinds.delete(kind.id);
    onDeleted(kind.id);
  }

  const pluralLabel = kind.plural || `${kind.name.toLowerCase()}s`;
  const count = instances.length;

  return (
    <div className="kind-detail">
      <div className="kind-detail-header">
        <div className="kind-detail-header-left">
          <span className="kind-detail-label">kind</span>
          <span className="kind-detail-name">{kind.name}</span>
        </div>
        {!editing && (
          <div className="kind-detail-actions">
            <button className="btn-icon" title="edit" onClick={() => setEditing(true)}>✎</button>
            <button className="btn-icon btn-icon--danger" title="delete" onClick={handleDelete}>🗑</button>
          </div>
        )}
      </div>

      {editing ? (
        <div className="kind-edit-form">
          <label className="kind-edit-field">
            <span className="kind-edit-label">name</span>
            <input
              className="kind-edit-input"
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter") void handleSave();
                if (e.key === "Escape") cancelEdit();
              }}
              autoFocus
            />
          </label>
          <label className="kind-edit-field">
            <span className="kind-edit-label">plural</span>
            <input
              className="kind-edit-input"
              value={plural}
              onChange={e => setPlural(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter") void handleSave();
                if (e.key === "Escape") cancelEdit();
              }}
            />
          </label>
          <label className="kind-edit-field">
            <span className="kind-edit-label">description</span>
            <textarea
              className="kind-edit-textarea"
              value={description}
              onChange={e => setDescription(e.target.value)}
              onKeyDown={e => { if (e.key === "Escape") cancelEdit(); }}
            />
          </label>
          <div className="kind-edit-actions">
            <button className="btn btn-primary" onClick={() => void handleSave()}>save</button>
            <button className="btn btn-secondary" onClick={cancelEdit}>cancel</button>
          </div>
        </div>
      ) : (
        <div className="kind-detail-body">
          <div className="kind-detail-row">
            <span className="kind-detail-row-label">plural</span>
            <span className="kind-detail-row-value">
              {kind.plural || <span className="kind-detail-muted">—</span>}
            </span>
          </div>
          {kind.description && (
            <p className="kind-detail-description">{kind.description}</p>
          )}
          <div className="kind-detail-count">
            {count} {count === 1 ? kind.name.toLowerCase() : pluralLabel.toLowerCase()}
          </div>
          {count > 0 && (
            <ul className="kind-detail-instance-list">
              {instances.map(i => (
                <li
                  key={i.id}
                  className="kind-detail-instance-item"
                  onClick={() => onSelectInstance(i)}
                >
                  {i.name}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
