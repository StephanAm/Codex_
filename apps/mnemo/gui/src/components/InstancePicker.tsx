// Copyright (C) 2026 Stephan Marais
// SPDX-License-Identifier: AGPL-3.0-or-later

import { useEffect, useRef, useState } from "react";
import { Instance } from "../api";

interface Props {
  instances: Instance[];
  selectedIds: number[];
  onChange: (ids: number[]) => void;
}

export function InstancePicker({ instances, selectedIds, onChange }: Props) {
  const [open, setOpen]     = useState(false);
  const [search, setSearch] = useState("");
  const containerRef        = useRef<HTMLDivElement>(null);
  const searchRef           = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) searchRef.current?.focus();
  }, [open]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function toggle(id: number) {
    onChange(
      selectedIds.includes(id)
        ? selectedIds.filter(s => s !== id)
        : [...selectedIds, id]
    );
  }

  const q = search.toLowerCase();
  const filtered = instances.filter(inst =>
    inst.name.toLowerCase().includes(q) || inst.type.name.toLowerCase().includes(q)
  );

  const byKind = new Map<number, { plural: string; items: Instance[] }>();
  for (const inst of filtered) {
    if (!byKind.has(inst.type.id)) {
      byKind.set(inst.type.id, { plural: inst.type.plural || inst.type.name, items: [] });
    }
    byKind.get(inst.type.id)!.items.push(inst);
  }

  const firstName = selectedIds.length === 1
    ? instances.find(i => i.id === selectedIds[0])?.name ?? "?"
    : null;

  return (
    <div className="picker-container" ref={containerRef}>
      <button
        type="button"
        className="picker-trigger picker-trigger-reference picker-compact"
        onClick={() => setOpen(o => !o)}
      >
        <span className="picker-label">Kinds</span>
        {selectedIds.length === 0 ? (
          <span className="picker-placeholder">Any</span>
        ) : firstName ? (
          <span className="badge badge-reference">{firstName}</span>
        ) : (
          <span className="picker-overflow">+{selectedIds.length}</span>
        )}
        <span className="picker-arrow">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div className="picker-dropdown picker-dropdown-down">
          <div className="picker-search-wrap">
            <input
              ref={searchRef}
              className="picker-search"
              placeholder="Search…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Escape") { setOpen(false); setSearch(""); }
              }}
            />
            {selectedIds.length > 0 && (
              <button type="button" className="picker-clear" onClick={() => onChange([])}>
                clear
              </button>
            )}
          </div>
          <ul className="picker-list">
            {byKind.size === 0 && (
              <li className="picker-empty">No instances found</li>
            )}
            {[...byKind.entries()].map(([kindId, { plural, items }]) => (
              <li key={kindId}>
                <div className="picker-group-heading">{plural}</div>
                <ul className="picker-group-list">
                  {items.map(inst => (
                    <li key={inst.id} className="picker-item">
                      <label className="picker-item-label">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(inst.id)}
                          onChange={() => toggle(inst.id)}
                        />
                        <span className="badge badge-reference">{inst.name}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
