// Copyright (C) 2026 Stephan Marais
// SPDX-License-Identifier: AGPL-3.0-or-later

import { useEffect, useRef, useState } from "react";
import { api, AtlasNode } from "../api";

interface Props {
  selectedNodeId: number | null;
  onSelect: (node: AtlasNode) => void;
  onDelete?: (nodeId: number) => void;
  reloadKey?: number;
}

function getChildren(nodes: AtlasNode[], parentId: number | null): AtlasNode[] {
  return nodes
    .filter(n => n.parent_id === parentId)
    .sort((a, b) => a.position - b.position);
}

export function AtlasSidebar({ selectedNodeId, onSelect, onDelete, reloadKey }: Props) {
  const [nodes, setNodes] = useState<AtlasNode[]>([]);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [addingChildOf, setAddingChildOf] = useState<number | null | "root">(null);
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [dragNodeId, setDragNodeId] = useState<number | null>(null);
  const [dropBeforeId, setDropBeforeId] = useState<number | null | "end">(null);
  const [dropParentId, setDropParentId] = useState<number | null | undefined>(undefined);

  // Uncontrolled inputs — read directly from DOM so that onBlur state changes
  // can't race with onKeyDown and produce a stale empty value.
  const addInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const isSubmittingRef = useRef(false);

  async function reload() {
    const all = await api.atlas.nodes.list();
    setNodes(all);
    return all;
  }

  useEffect(() => { reload(); }, [reloadKey]);

  useEffect(() => {
    if (addingChildOf !== null) {
      // Small delay so the DOM element is mounted before we focus
      requestAnimationFrame(() => addInputRef.current?.focus());
    }
  }, [addingChildOf]);

  useEffect(() => {
    if (renamingId !== null) {
      requestAnimationFrame(() => {
        if (renameInputRef.current) {
          renameInputRef.current.focus();
          renameInputRef.current.select();
        }
      });
    }
  }, [renamingId]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "F2") return;
      if (selectedNodeId === null) return;
      const node = nodes.find(n => n.id === selectedNodeId);
      if (node) startRename(node);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedNodeId, nodes]);

  function toggleCollapse(id: number) {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function nextPosition(parentId: number | null): number {
    const siblings = getChildren(nodes, parentId);
    return siblings.length === 0 ? 0 : siblings[siblings.length - 1].position + 1000;
  }

  async function submitAdd(parentId: number | null) {
    const name = (addInputRef.current?.value ?? "").trim();
    if (!name) { cancelAdd(); return; }
    isSubmittingRef.current = true;
    try {
      const node = await api.atlas.nodes.create(name, parentId, nextPosition(parentId));
      isSubmittingRef.current = false;
      cancelAdd();
      await reload();
      onSelect(node);
    } catch (err) {
      isSubmittingRef.current = false;
      console.error("atlas create node failed:", err);
      if (addInputRef.current) {
        addInputRef.current.style.outline = "1px solid var(--color-danger, #f55)";
        setTimeout(() => { if (addInputRef.current) addInputRef.current.style.outline = ""; }, 1500);
      }
    }
  }

  function cancelAdd() {
    if (isSubmittingRef.current) return;
    setAddingChildOf(null);
  }

  async function submitRename(nodeId: number) {
    const name = (renameInputRef.current?.value ?? "").trim();
    if (name) await api.atlas.nodes.update(nodeId, name);
    setRenamingId(null);
    reload();
  }

  function cancelRename() {
    setRenamingId(null);
  }

  function startRename(node: AtlasNode) {
    setRenamingId(node.id);
    setAddingChildOf(null);
  }

  async function handleDelete(node: AtlasNode) {
    if (!confirm(`Delete "${node.name}"?`)) return;
    await api.atlas.nodes.delete(node.id);
    onDelete?.(node.id);
    reload();
  }

  // ── drag and drop ────────────────────────────────────────────────────────────

  function onDragStart(e: React.DragEvent, nodeId: number) {
    setDragNodeId(nodeId);
    e.dataTransfer.effectAllowed = "move";
  }

  function onDragOver(e: React.DragEvent, beforeId: number | null | "end", parentId: number | null) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDropBeforeId(beforeId);
    setDropParentId(parentId);
  }

  function onDragEnd() {
    setDragNodeId(null);
    setDropBeforeId(null);
    setDropParentId(undefined);
  }

  async function onDrop(e: React.DragEvent, beforeId: number | null | "end", parentId: number | null) {
    e.preventDefault();
    if (dragNodeId === null || dragNodeId === (beforeId === "end" ? null : beforeId)) {
      onDragEnd();
      return;
    }
    const siblings = getChildren(nodes, parentId).filter(n => n.id !== dragNodeId);
    const beforeIndex = beforeId === "end" ? siblings.length : siblings.findIndex(n => n.id === beforeId);
    siblings.splice(beforeIndex, 0, nodes.find(n => n.id === dragNodeId)!);
    const updates = siblings.map((n, i) => ({ node_id: n.id, parent_id: parentId, position: i * 1000 }));
    const draggedNode = nodes.find(n => n.id === dragNodeId);
    if (draggedNode && draggedNode.parent_id !== parentId) {
      await api.atlas.nodes.move(dragNodeId, parentId, beforeIndex * 1000);
    } else {
      await api.atlas.nodes.reorder(updates);
    }
    onDragEnd();
    reload();
  }

  // ── render ───────────────────────────────────────────────────────────────────

  function renderDropZone(beforeId: number | null | "end", parentId: number | null) {
    const active = dropParentId === parentId && dropBeforeId === beforeId && dragNodeId !== null;
    return (
      <div
        className={`atlas-drop-zone${active ? " atlas-drop-zone--active" : ""}`}
        onDragOver={e => onDragOver(e, beforeId, parentId)}
        onDrop={e => onDrop(e, beforeId, parentId)}
      />
    );
  }

  function renderNodes(parentId: number | null, depth: number): React.ReactNode {
    const children = getChildren(nodes, parentId);
    const isAddingHere = (parentId !== null && addingChildOf === parentId) || (parentId === null && addingChildOf === "root");
    if (children.length === 0 && !isAddingHere) return null;

    return (
      <div className="atlas-node-children">
        {children.map((node) => {
          const hasChildren = nodes.some(n => n.parent_id === node.id);
          const isCollapsed = collapsed.has(node.id);
          const isSelected = node.id === selectedNodeId;
          const hasPage = node.has_page;
          const isDragging = dragNodeId === node.id;

          return (
            <div key={node.id} className={`atlas-node-group${isDragging ? " atlas-node-group--dragging" : ""}`}>
              {renderDropZone(node.id, parentId)}
              <div
                className={`atlas-node-row${isSelected ? " atlas-node-row--active" : ""}${hasPage ? " atlas-node-row--has-page" : ""}`}
                style={{ paddingLeft: `${8 + depth * 12}px` }}
                onClick={() => onSelect(node)}
                onDoubleClick={() => startRename(node)}
                onMouseEnter={() => setHoveredId(node.id)}
                onMouseLeave={() => setHoveredId(null)}
                draggable
                onDragStart={e => onDragStart(e, node.id)}
                onDragEnd={onDragEnd}
              >
                <button
                  type="button"
                  className={`atlas-node-toggle${!hasChildren ? " atlas-node-toggle--hidden" : ""}`}
                  onClick={e => { e.stopPropagation(); toggleCollapse(node.id); }}
                  tabIndex={-1}
                >
                  {isCollapsed ? "▸" : "▾"}
                </button>

                {renamingId === node.id ? (
                  <input
                    ref={renameInputRef}
                    className="atlas-inline-input"
                    defaultValue={node.name}
                    onClick={e => e.stopPropagation()}
                    onKeyDown={e => {
                      if (e.key === "Enter") { e.stopPropagation(); submitRename(node.id); }
                      if (e.key === "Escape") { e.stopPropagation(); cancelRename(); }
                    }}
                    onBlur={() => cancelRename()}
                  />
                ) : (
                  <span className="atlas-node-name">{node.name}</span>
                )}

                {hoveredId === node.id && renamingId !== node.id && (
                  <>
                    <button
                      type="button"
                      className="atlas-node-add-child-btn"
                      title="add child"
                      onClick={e => {
                        e.stopPropagation();
                        setAddingChildOf(node.id);
                        if (isCollapsed && hasChildren) toggleCollapse(node.id);
                      }}
                    >+</button>
                    {!hasChildren && (
                      <button
                        type="button"
                        className="atlas-node-delete-btn"
                        title="delete"
                        onClick={e => { e.stopPropagation(); handleDelete(node); }}
                      >×</button>
                    )}
                  </>
                )}
              </div>

              {!isCollapsed && renderNodes(node.id, depth + 1)}
            </div>
          );
        })}

        {renderDropZone("end", parentId)}

        {isAddingHere && (
          <div className="atlas-inline-form" style={{ paddingLeft: `${8 + depth * 12}px` }}>
            <input
              ref={addInputRef}
              className="atlas-inline-input"
              placeholder="node name"
              onKeyDown={e => {
                if (e.key === "Enter") { e.stopPropagation(); e.preventDefault(); submitAdd(parentId); }
                if (e.key === "Escape") { e.stopPropagation(); cancelAdd(); }
              }}
              onBlur={() => cancelAdd()}
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="atlas-sidebar">
      <div className="atlas-sidebar-header">
        <span className="atlas-section-label">pages</span>
        <button
          type="button"
          className="atlas-add-root-btn"
          onClick={() => { setAddingChildOf("root"); setRenamingId(null); }}
          title="add page"
        >+</button>
      </div>

      <div className="atlas-tree">
        {nodes.length === 0 && addingChildOf === null ? (
          <span className="atlas-sidebar-empty">no pages yet.</span>
        ) : (
          renderNodes(null, 0)
        )}
      </div>
    </div>
  );
}
