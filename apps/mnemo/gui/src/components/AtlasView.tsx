import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { TagBadge, TagReferencePicker } from "@codex/ui";
import { api, AtlasNode, AtlasPage } from "../api";

interface Props {
  selectedNode: AtlasNode | null;
  onPageChange?: (nodeId: number, hasPage: boolean) => void;
}

type ViewMode = "view" | "edit";
type DateGranularity = "day" | "week" | "month" | "year";

function inferGranularity(val: string): DateGranularity | null {
  if (!val) return null;
  if (/^\d{4}-W\d{2}$/.test(val)) return "week";
  if (/^\d{4}-\d{2}-\d{2}$/.test(val)) return "day";
  if (/^\d{4}-\d{2}$/.test(val)) return "month";
  if (/^\d{4}$/.test(val)) return "year";
  return null;
}


export function AtlasView({ selectedNode, onPageChange }: Props) {
  const [page, setPage] = useState<AtlasPage | null | undefined>(undefined);
  const [viewMode, setViewMode] = useState<ViewMode>("view");
  const [editTitle, setEditTitle] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editReferences, setEditReferences] = useState<string[]>([]);
  const [editDateGranularity, setEditDateGranularity] = useState<DateGranularity | null>(null);
  const [editDateValue, setEditDateValue] = useState("");
  const [allTags, setAllTags] = useState<string[]>([]);
  const [allReferences, setAllReferences] = useState<string[]>([]);
  const titleInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (selectedNode === null) {
      setPage(undefined);
      setViewMode("view");
      return;
    }
    setPage(undefined);
    setViewMode("view");
    api.atlas.pages.get(selectedNode.id)
      .then(p => setPage(p))
      .catch(() => setPage(null));
  }, [selectedNode?.id]);

  useEffect(() => {
    if (viewMode === "edit") titleInputRef.current?.focus();
  }, [viewMode]);

  function enterEdit() {
    const storedDate = page?.dates?.[0] ?? "";
    setEditTitle(page?.title ?? "");
    setEditBody(page?.body ?? "");
    setEditTags(page?.tags ?? []);
    setEditReferences(page?.references ?? []);
    setEditDateGranularity(inferGranularity(storedDate));
    setEditDateValue(storedDate);
    api.tags.list().then(setAllTags);
    api.references.list().then(rs => setAllReferences(rs.map(r => r.name)));
    setViewMode("edit");
  }

  async function save() {
    if (!selectedNode) return;
    const title = editTitle.trim();
    const body = editBody;
    const date_annotation = editDateValue || null;
    const date_granularity = editDateGranularity;
    if (page) {
      const updated = await api.atlas.pages.update(selectedNode.id, title, body, editTags, editReferences, date_annotation, date_granularity);
      setPage(updated);
    } else {
      const created = await api.atlas.pages.create(selectedNode.id, title, body, editTags, editReferences, date_annotation, date_granularity);
      setPage(created);
      onPageChange?.(selectedNode.id, true);
    }
    setViewMode("view");
  }

  function cancelEdit() {
    setViewMode("view");
  }

  function selectGranularity(g: DateGranularity) {
    if (editDateGranularity === g) {
      setEditDateGranularity(null);
      setEditDateValue("");
    } else {
      setEditDateGranularity(g);
      setEditDateValue("");
    }
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (viewMode === "edit") {
        if ((e.metaKey || e.ctrlKey) && (e.key === "s" || e.key === "Enter")) {
          e.preventDefault();
          save();
        }
        if (e.key === "Escape") cancelEdit();
      } else if (selectedNode && page !== undefined) {
        const tag = (e.target as HTMLElement).tagName;
        if (e.key === "Enter" && tag !== "INPUT" && tag !== "TEXTAREA") {
          e.preventDefault();
          enterEdit();
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [viewMode, selectedNode, page, editTitle, editBody, editTags, editReferences, editDateValue]);

  // ── state 1: no node selected ─────────────────────────────────────────────
  if (selectedNode === null) {
    return <div className="atlas-view" />;
  }

  // ── loading ────────────────────────────────────────────────────────────────
  if (page === undefined) {
    return <div className="atlas-view" />;
  }

  // ── edit form (shared by new-page and existing-page edit) ──────────────────
  if (viewMode === "edit") {

    return (
      <div className="atlas-view">
        <div className="atlas-page">
          <div className="atlas-page-header">
            <input
              ref={titleInputRef}
              className="atlas-page-title-input"
              value={editTitle}
              onChange={e => setEditTitle(e.target.value)}
              placeholder="title"
              onKeyDown={e => {
                if (e.key === "Tab") { e.preventDefault(); (document.querySelector(".atlas-page-textarea") as HTMLElement)?.focus(); }
              }}
            />
            <div className="atlas-page-actions">
              <button className="btn btn-primary" onClick={save}>save</button>
              <button className="btn btn-secondary" onClick={cancelEdit}>cancel</button>
            </div>
          </div>
          <hr className="atlas-page-divider" />
          <textarea
            className="atlas-page-textarea"
            value={editBody}
            onChange={e => setEditBody(e.target.value)}
            placeholder="markdown body"
            onKeyDown={e => {
              if (e.key === "Tab") { e.preventDefault(); titleInputRef.current?.focus(); }
            }}
          />
          <div className="atlas-page-pickers">
            <TagReferencePicker label="Tags" prefix="#" kind="tag" allItems={allTags} selected={editTags} onChange={setEditTags} dropdownDir="up" />
            <TagReferencePicker label="References" prefix="@" kind="reference" allItems={allReferences} selected={editReferences} onChange={setEditReferences} dropdownDir="up" />
          </div>
          <div className="atlas-page-date-picker">
            <span className="atlas-page-date-label">date</span>
            <div className="atlas-page-date-granularity">
              {(["day", "week", "month", "year"] as DateGranularity[]).map(g => (
                <button
                  key={g}
                  className={`atlas-page-date-gran-btn${editDateGranularity === g ? " atlas-page-date-gran-btn--active" : ""}`}
                  onClick={() => selectGranularity(g)}
                  type="button"
                >{g}</button>
              ))}
            </div>
            {(editDateGranularity || editDateValue) && (
              <input
                type="text"
                className="atlas-page-date-input"
                value={editDateValue}
                onChange={e => setEditDateValue(e.target.value)}
                placeholder={
                  editDateGranularity === "month" ? "YYYY-MM" :
                  editDateGranularity === "year" ? "YYYY" :
                  "YYYY-MM-DD"
                }
                spellCheck={false}
              />
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── state 2: node selected, no page ───────────────────────────────────────
  if (page === null) {
    return (
      <div className="atlas-view atlas-view--no-page">
        <div className="atlas-no-page">
          <div className="atlas-no-page__name">{selectedNode.name}</div>
          <div className="atlas-no-page__hint">no page yet.</div>
          <button className="atlas-no-page__create" onClick={enterEdit}>
            <kbd>Enter</kbd> create page
          </button>
        </div>
      </div>
    );
  }

  // ── state 3: page exists, view mode ───────────────────────────────────────
  return (
    <div className="atlas-view">
      <div className="atlas-page">
        <div className="atlas-page-header">
          <div className="atlas-page-title-view">{page.title}</div>
          <div className="atlas-page-actions">
            <button className="btn-icon" title="edit" onClick={enterEdit}>✎</button>
          </div>
        </div>
        <hr className="atlas-page-divider" />
        <div className="atlas-page-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{page.body}</ReactMarkdown>
        </div>
        {((page.tags?.length ?? 0) > 0 || (page.references?.length ?? 0) > 0 || (page.dates?.length ?? 0) > 0) && (
          <div className="atlas-page-meta">
            {(page.tags ?? []).map(t => <TagBadge key={t} text={t} kind="tag" />)}
            {(page.references ?? []).map(r => <TagBadge key={r} text={r} kind="reference" />)}
            {(page.dates ?? []).map(d => (
              <span key={d} className="badge badge-date">~{d}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
