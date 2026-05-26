import { useEffect, useState } from "react";
import { api, Instance } from "../api";
import { TagReferencePicker } from "@codex/ui";

interface Props {
  instance: Instance;
  onUpdated: (instance: Instance) => void;
  onDeleted: (id: number) => void;
}

export function InstanceDetail({ instance, onUpdated, onDeleted }: Props) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(instance.name);
  const [description, setDescription] = useState(instance.description);
  const [references, setReferences] = useState<string[]>(instance.references);
  const [allRefs, setAllRefs] = useState<string[]>([]);

  useEffect(() => {
    setName(instance.name);
    setDescription(instance.description);
    setReferences(instance.references);
    setEditing(false);
  }, [instance.id]);

  async function enterEdit() {
    const refs = await api.references.list();
    setAllRefs(refs.map(r => r.name));
    setEditing(true);
  }

  function cancelEdit() {
    setName(instance.name);
    setDescription(instance.description);
    setReferences(instance.references);
    setEditing(false);
  }

  async function handleSave() {
    const trimmedName = name.trim();
    if (!trimmedName) return;
    const updated = await api.instances.update(
      instance.id,
      trimmedName,
      instance.type.id,
      description.trim(),
      references,
    );
    setEditing(false);
    onUpdated(updated);
  }

  async function handleDelete() {
    if (!confirm(`Delete "${instance.name}"?`)) return;
    await api.instances.delete(instance.id);
    onDeleted(instance.id);
  }

  return (
    <div className="instance-detail">
      <div className="instance-detail-header">
        <div className="instance-detail-header-left">
          <span className="instance-detail-kind">{instance.type.name}</span>
          <span className="instance-detail-name">{instance.name}</span>
        </div>
        {!editing && (
          <div className="instance-detail-actions">
            <button className="btn-icon" title="edit" onClick={() => void enterEdit()}>✎</button>
            <button className="btn-icon btn-icon--danger" title="delete" onClick={() => void handleDelete()}>🗑</button>
          </div>
        )}
      </div>

      {editing ? (
        <div className="instance-edit-form">
          <label className="instance-edit-field">
            <span className="instance-edit-label">name</span>
            <input
              className="instance-edit-input"
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter") void handleSave();
                if (e.key === "Escape") cancelEdit();
              }}
              autoFocus
            />
          </label>
          <label className="instance-edit-field">
            <span className="instance-edit-label">description</span>
            <textarea
              className="instance-edit-textarea"
              value={description}
              onChange={e => setDescription(e.target.value)}
              onKeyDown={e => { if (e.key === "Escape") cancelEdit(); }}
            />
          </label>
          <div className="instance-edit-field">
            <span className="instance-edit-label">references</span>
            <TagReferencePicker
              label="References"
              prefix="@"
              kind="reference"
              allItems={allRefs}
              selected={references}
              onChange={setReferences}
              allowNew
              dropdownDir="down"
            />
          </div>
          <div className="instance-edit-actions">
            <button className="btn btn-primary" onClick={() => void handleSave()}>save</button>
            <button className="btn btn-secondary" onClick={cancelEdit}>cancel</button>
          </div>
        </div>
      ) : (
        <>
          {instance.description && (
            <p className="instance-detail-desc">{instance.description}</p>
          )}
          {instance.references.length > 0 && (
            <div className="instance-detail-refs">
              {instance.references.map(r => (
                <span key={r} className="badge badge-reference">@{r}</span>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
