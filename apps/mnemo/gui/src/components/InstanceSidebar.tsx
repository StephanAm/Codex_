import { useEffect, useRef, useState } from "react";
import { api, Instance, InstanceKind } from "../api";

interface Props {
  selectedId: number | null;
  selectedKindId: number | null;
  onSelect: (instance: Instance) => void;
  onSelectKind: (kind: InstanceKind) => void;
  reloadKey?: number;
  className?: string;
}

export function InstanceSidebar({ selectedId, selectedKindId, onSelect, onSelectKind, reloadKey, className = "" }: Props) {
  const [types, setTypes] = useState<InstanceKind[]>([]);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

  const [addingKind, setAddingKind] = useState(false);
  const [newKindName, setNewKindName] = useState("");
  const [addingInstanceFor, setAddingInstanceFor] = useState<number | null>(null);
  const [newInstanceName, setNewInstanceName] = useState("");

  const kindInputRef = useRef<HTMLInputElement>(null);
  const instanceInputRef = useRef<HTMLInputElement>(null);
  const initializedRef = useRef(false);

  async function reload() {
    const [t, i] = await Promise.all([api.instanceKinds.list(), api.instances.list()]);
    setTypes(t);
    setInstances(i);
    if (!initializedRef.current) {
      setCollapsed(new Set(t.map(kind => kind.id)));
      initializedRef.current = true;
    }
  }

  useEffect(() => { reload(); }, [reloadKey]);

  useEffect(() => { if (addingKind) kindInputRef.current?.focus(); }, [addingKind]);
  useEffect(() => { if (addingInstanceFor !== null) instanceInputRef.current?.focus(); }, [addingInstanceFor]);

  function toggleGroup(id: number) {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submitKind() {
    const name = newKindName.trim();
    if (!name) return;
    await api.instanceKinds.create(name);
    setNewKindName("");
    setAddingKind(false);
    reload();
  }

  async function submitInstance(kindId: number) {
    const name = newInstanceName.trim();
    if (!name) return;
    await api.instances.create(name, kindId);
    setNewInstanceName("");
    setAddingInstanceFor(null);
    reload();
  }

  return (
    <div className={`instance-sidebar${className ? " " + className : ""}`}>
      <div className="instance-sidebar-header">
        <div className="instance-section-label">kinds</div>
        <button
          className="instance-add-kind-btn"
          onClick={() => { setAddingKind(true); setAddingInstanceFor(null); }}
          title="new kind"
        >+ new kind</button>
      </div>

      {addingKind && (
        <div className="instance-inline-form">
          <input
            ref={kindInputRef}
            className="instance-inline-input"
            value={newKindName}
            onChange={e => setNewKindName(e.target.value)}
            placeholder="kind name"
            onKeyDown={e => {
              if (e.key === "Enter") submitKind();
              if (e.key === "Escape") { setAddingKind(false); setNewKindName(""); }
            }}
            onBlur={() => { setAddingKind(false); setNewKindName(""); }}
          />
        </div>
      )}

      {types.length === 0 && !addingKind && (
        <span className="instance-sidebar-empty">no kinds yet.</span>
      )}

      <div className="instance-group-list">
        {types.map(t => {
          const members = instances.filter(i => i.type.id === t.id);
          const isCollapsed = collapsed.has(t.id);
          const kindLabel = t.plural || t.name;
          return (
            <div key={t.id} className="instance-group">
              <div
                className={`instance-group-header${selectedKindId === t.id ? " instance-group-header--active" : ""}`}
                onClick={() => onSelectKind(t)}
              >
                <button
                  className="instance-group-toggle-btn"
                  onClick={e => { e.stopPropagation(); toggleGroup(t.id); }}
                  title={isCollapsed ? "expand" : "collapse"}
                >
                  {isCollapsed ? "▶" : "▼"}
                </button>
                <span className="instance-group-name">{kindLabel}</span>
                <span className="instance-group-count">{members.length}</span>
              </div>
              {!isCollapsed && (
                <ul className="instance-list">
                  {members.length === 0 ? (
                    <li className="instance-list-empty">no {kindLabel.toLowerCase()}.</li>
                  ) : (
                    members.map(i => (
                      <li
                        key={i.id}
                        className={`instance-item${i.id === selectedId ? " instance-item--active" : ""}`}
                        onClick={() => onSelect(i)}
                      >
                        <span className="instance-item-name">{i.name}</span>
                        {i.description && (
                          <span className="instance-item-desc">{i.description}</span>
                        )}
                      </li>
                    ))
                  )}
                  {addingInstanceFor === t.id ? (
                    <li className="instance-inline-form">
                      <input
                        ref={instanceInputRef}
                        className="instance-inline-input"
                        value={newInstanceName}
                        onChange={e => setNewInstanceName(e.target.value)}
                        placeholder={`new ${t.name.toLowerCase()}`}
                        onKeyDown={e => {
                          if (e.key === "Enter") submitInstance(t.id);
                          if (e.key === "Escape") { setAddingInstanceFor(null); setNewInstanceName(""); }
                        }}
                        onBlur={() => { setAddingInstanceFor(null); setNewInstanceName(""); }}
                      />
                    </li>
                  ) : (
                    <li>
                      <button
                        className="instance-add-instance-btn"
                        onClick={() => { setAddingInstanceFor(t.id); setAddingKind(false); setNewInstanceName(""); }}
                      >+ new {t.name.toLowerCase()}</button>
                    </li>
                  )}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
