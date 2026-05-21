import { useEffect, useState } from "react";
import { api, Instance, InstanceKind } from "../api";

interface Props {
  className?: string;
}

export function InstanceSidebar({ className = "" }: Props) {
  const [types, setTypes] = useState<InstanceKind[]>([]);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

  useEffect(() => {
    Promise.all([api.instanceKinds.list(), api.instances.list()]).then(
      ([t, i]) => { setTypes(t); setInstances(i); }
    );
  }, []);

  function toggleGroup(id: number) {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className={`instance-sidebar${className ? " " + className : ""}`}>
      <div className="instance-section-label">kinds</div>
      {types.length === 0 && (
        <span className="instance-sidebar-empty">no kinds yet.</span>
      )}
      <div className="instance-group-list">
        {types.map(t => {
          const members = instances.filter(i => i.type.id === t.id);
          const isCollapsed = collapsed.has(t.id);
          return (
            <div key={t.id} className="instance-group">
              <button
                className="instance-group-header"
                onClick={() => toggleGroup(t.id)}
              >
                <span className="instance-group-toggle">{isCollapsed ? "▶" : "▼"}</span>
                <span className="instance-group-name">{t.plural || t.name}</span>
                <span className="instance-group-count">{members.length}</span>
              </button>
              {!isCollapsed && (
                <ul className="instance-list">
                  {members.length === 0 ? (
                    <li className="instance-list-empty">no {t.plural || t.name.toLowerCase()}.</li>
                  ) : (
                    members.map(i => (
                      <li key={i.id} className="instance-item">
                        <span className="instance-item-name">{i.name}</span>
                        {i.description && (
                          <span className="instance-item-desc">{i.description}</span>
                        )}
                      </li>
                    ))
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
