import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { TagEntityPicker } from "./TagEntityPicker";

interface Props {
  initialBody?: string;
  initialTags?: string[];
  initialEntities?: string[];
  onSave: (body: string, tags: string[], entities: string[]) => void;
  onCancel: () => void;
}

export function NoteEditor({
  initialBody = "",
  initialTags = [],
  initialEntities = [],
  onSave,
  onCancel,
}: Props) {
  const [body, setBody] = useState(() => {
    if (!initialBody) return initialBody;
    return initialBody.endsWith("\n") ? initialBody : initialBody + "\n";
  });
  const [selectedTags, setSelectedTags] = useState<string[]>(initialTags);
  const [selectedEntities, setSelectedEntities] = useState<string[]>(initialEntities);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [allEntities, setAllEntities] = useState<string[]>([]);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) {
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    }
    api.tags.list().then(setAllTags);
    api.entities.list().then(es => setAllEntities(es.map(e => e.name)));
  }, []);

  function handleKeyDown(e: React.KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      if (canSave) onSave(prepareBody(body), selectedTags, selectedEntities);
    }
    if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
    }
  }

  function prepareBody(raw: string): string {
    const trimmed = raw.trim();
    return trimmed ? trimmed + "\n" : trimmed;
  }

  const canSave = body.trim().length > 0 || selectedTags.length > 0 || selectedEntities.length > 0;

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
        <button className="btn btn-primary" onClick={() => onSave(prepareBody(body), selectedTags, selectedEntities)} disabled={!canSave}>
          Save
        </button>
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
