import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { TagEntityPicker } from "./TagEntityPicker";

interface Props {
  initialBody?: string;
  initialTags?: string[];
  initialEntities?: string[];
  onSave: (body: string) => void;
  onCancel: () => void;
}

export function NoteEditor({
  initialBody = "",
  initialTags = [],
  initialEntities = [],
  onSave,
  onCancel,
}: Props) {
  const [body, setBody] = useState(initialBody);
  const [selectedTags, setSelectedTags] = useState<string[]>(initialTags);
  const [selectedEntities, setSelectedEntities] = useState<string[]>(initialEntities);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [allEntities, setAllEntities] = useState<string[]>([]);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    ref.current?.focus();
    api.tags.list().then(setAllTags);
    api.entities.list().then(es => setAllEntities(es.map(e => e.name)));
  }, []);

  function buildBody() {
    const tagTokens = selectedTags
      .filter(t => !body.includes(`#${t}`))
      .map(t => `#${t}`);
    const entityTokens = selectedEntities
      .filter(e => !body.includes(`@${e}`))
      .map(e => `@${e}`);
    const suffix = [...tagTokens, ...entityTokens].join(" ");
    return suffix ? `${body.trim()} ${suffix}` : body.trim();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      const built = buildBody();
      if (built) onSave(built);
    }
    if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
    }
  }

  const canSave = body.trim() || selectedTags.length > 0 || selectedEntities.length > 0;

  return (
    <div className="note-editor">
      <div className="note-editor-hint">Ctrl+Enter to save · Esc to cancel</div>
      <textarea
        ref={ref}
        className="note-editor-textarea"
        value={body}
        onChange={e => setBody(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Write your note…"
        spellCheck
      />
      <div className="note-editor-pickers">
        <TagEntityPicker
          label="Tags"
          prefix="#"
          kind="tag"
          allItems={allTags}
          selected={selectedTags}
          onChange={setSelectedTags}
        />
        <TagEntityPicker
          label="References"
          prefix="@"
          kind="entity"
          allItems={allEntities}
          selected={selectedEntities}
          onChange={setSelectedEntities}
        />
      </div>
      <div className="note-editor-actions">
        <button className="btn btn-primary" onClick={() => { const b = buildBody(); if (b) onSave(b); }} disabled={!canSave}>
          Save
        </button>
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
