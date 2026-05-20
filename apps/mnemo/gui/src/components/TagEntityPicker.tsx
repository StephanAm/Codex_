import { useEffect, useRef, useState } from "react";

interface Props {
  label: string;
  prefix: "#" | "@";
  kind: "tag" | "reference";
  allItems: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  allowNew?: boolean;
  dropdownDir?: "up" | "down";
  compact?: boolean;
}

export function TagEntityPicker({ label, prefix, kind, allItems, selected, onChange, allowNew = true, dropdownDir = "up", compact = false }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

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

  const filtered = allItems.filter(item =>
    item.toLowerCase().includes(search.toLowerCase())
  );

  const isNew = search.trim() && !allItems.some(
    item => item.toLowerCase() === search.trim().toLowerCase()
  );

  function toggle(item: string) {
    onChange(
      selected.includes(item)
        ? selected.filter(s => s !== item)
        : [...selected, item]
    );
  }

  function addNew() {
    const name = search.trim().toLowerCase().replace(/^[#@]/, "");
    if (!name) return;
    if (!selected.includes(name)) onChange([...selected, name]);
    setSearch("");
  }

  const badgeClass = `badge badge-${kind}`;

  return (
    <div className="picker-container" ref={containerRef}>
      <button
        type="button"
        className={`picker-trigger picker-trigger-${kind}${compact ? " picker-compact" : ""}`}
        onClick={() => setOpen(o => !o)}
      >
        <span className="picker-label">{label}</span>
        {compact ? (
          selected.length === 0 ? (
            <span className="picker-placeholder">Any</span>
          ) : selected.length === 1 ? (
            <span className={badgeClass}>{prefix}{selected[0]}</span>
          ) : (
            <span className="picker-overflow">+{selected.length}</span>
          )
        ) : (
          selected.length === 0 ? (
            <span className="picker-placeholder">None selected</span>
          ) : (
            <span className="picker-chips">
              {selected.slice(0, 3).map(s => (
                <span key={s} className={badgeClass}>{prefix}{s}</span>
              ))}
              {selected.length > 3 && (
                <span className="picker-overflow">+{selected.length - 3}</span>
              )}
            </span>
          )
        )}
        <span className="picker-arrow">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div className={`picker-dropdown${dropdownDir === "down" ? " picker-dropdown-down" : ""}`}>
          <div className="picker-search-wrap">
            <input
              ref={searchRef}
              className="picker-search"
              placeholder={`Search ${label.toLowerCase()}…`}
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter" && isNew) { e.preventDefault(); addNew(); }
                if (e.key === "Escape") { setOpen(false); setSearch(""); }
              }}
            />
            {selected.length > 0 && (
              <button
                type="button"
                className="picker-clear"
                onClick={() => onChange([])}
              >
                clear
              </button>
            )}
          </div>

          <ul className="picker-list">
            {filtered.length === 0 && !isNew && (
              <li className="picker-empty">No {label.toLowerCase()} found</li>
            )}
            {filtered.map(item => (
              <li key={item} className="picker-item">
                <label className="picker-item-label">
                  <input
                    type="checkbox"
                    checked={selected.includes(item)}
                    onChange={() => toggle(item)}
                  />
                  <span className={badgeClass}>{prefix}{item}</span>
                </label>
              </li>
            ))}
          </ul>

          {isNew && allowNew && (
            <button type="button" className="picker-add-new" onClick={addNew}>
              + Add new: <span className={badgeClass}>{prefix}{search.trim().toLowerCase()}</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
