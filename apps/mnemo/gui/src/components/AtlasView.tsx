import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, AtlasNode, AtlasPage } from "../api";

interface Props {
  selectedNode: AtlasNode | null;
  onPageChange?: (nodeId: number, hasPage: boolean) => void;
}

type ViewMode = "view" | "edit";

export function AtlasView({ selectedNode, onPageChange }: Props) {
  const [page, setPage] = useState<AtlasPage | null | undefined>(undefined);
  const [viewMode, setViewMode] = useState<ViewMode>("view");
  const [editTitle, setEditTitle] = useState("");
  const [editBody, setEditBody] = useState("");
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
    setEditTitle(page?.title ?? "");
    setEditBody(page?.body ?? "");
    setViewMode("edit");
  }

  async function save() {
    if (!selectedNode) return;
    const title = editTitle.trim();
    const body = editBody;
    if (page) {
      const updated = await api.atlas.pages.update(selectedNode.id, title, body);
      setPage(updated);
    } else {
      const created = await api.atlas.pages.create(selectedNode.id, title, body);
      setPage(created);
      onPageChange?.(selectedNode.id, true);
    }
    setViewMode("view");
  }

  function cancelEdit() {
    if (!page && viewMode === "edit") {
      setViewMode("view");
    } else {
      setViewMode("view");
    }
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (viewMode === "edit") {
        if ((e.metaKey || e.ctrlKey) && (e.key === "s" || e.key === "Enter")) {
          e.preventDefault();
          save();
        }
        if (e.key === "Escape") {
          cancelEdit();
        }
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
  }, [viewMode, selectedNode, page, editTitle, editBody]);

  // ── state 1: no node selected — let the shared MNEMO_ watermark show through
  if (selectedNode === null) {
    return <div className="atlas-view" />;
  }

  // ── state 2: node selected, no page ───────────────────────────────────────
  if (page === null) {
    return (
      <div className="atlas-view atlas-view--no-page">
        {viewMode === "edit" ? (
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
              <div className="atlas-mode-toggle">
                <button className="atlas-mode-btn" onClick={cancelEdit}>view</button>
                <button className="atlas-mode-btn atlas-mode-btn--active">edit</button>
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
          </div>
        ) : (
          <div className="atlas-no-page">
            <div className="atlas-no-page__name">{selectedNode.name}</div>
            <div className="atlas-no-page__hint">no page yet.</div>
            <button className="atlas-no-page__create" onClick={enterEdit}>
              <kbd>Enter</kbd> create page
            </button>
          </div>
        )}
      </div>
    );
  }

  // ── loading ────────────────────────────────────────────────────────────────
  if (page === undefined) {
    return <div className="atlas-view" />;
  }

  // ── state 3 & 4: page exists ───────────────────────────────────────────────
  return (
    <div className="atlas-view">
      <div className="atlas-page">
        <div className="atlas-page-header">
          {viewMode === "edit" ? (
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
          ) : (
            <div className="atlas-page-title-view">{page.title}</div>
          )}
          <div className="atlas-mode-toggle">
            <button
              className={`atlas-mode-btn${viewMode === "view" ? " atlas-mode-btn--active" : ""}`}
              onClick={() => { if (viewMode === "edit") cancelEdit(); }}
            >view</button>
            <button
              className={`atlas-mode-btn${viewMode === "edit" ? " atlas-mode-btn--active" : ""}`}
              onClick={() => { if (viewMode === "view") enterEdit(); }}
            >edit</button>
          </div>
        </div>

        <hr className="atlas-page-divider" />

        {viewMode === "view" ? (
          <div className="atlas-page-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{page.body}</ReactMarkdown>
          </div>
        ) : (
          <textarea
            className="atlas-page-textarea"
            value={editBody}
            onChange={e => setEditBody(e.target.value)}
            placeholder="markdown body"
            onKeyDown={e => {
              if (e.key === "Tab") { e.preventDefault(); titleInputRef.current?.focus(); }
            }}
          />
        )}
      </div>
    </div>
  );
}
