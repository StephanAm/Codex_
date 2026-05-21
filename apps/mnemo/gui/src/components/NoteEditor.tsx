import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { TagReferencePicker } from "./TagReferencePicker";

interface Props {
  initialBody?: string;
  initialTags?: string[];
  initialReferences?: string[];
  onSave: (body: string, tags: string[], references: string[]) => void;
  onCancel: () => void;
  isPinned?: boolean;
  onPin?: () => void;
  onUnpin?: () => void;
}

export function NoteEditor({
  initialBody = "",
  initialTags = [],
  initialReferences = [],
  onSave,
  onCancel,
  isPinned,
  onPin,
  onUnpin,
}: Props) {
  const [body, setBody] = useState(() => {
    if (!initialBody) return initialBody;
    return initialBody.endsWith("\n") ? initialBody : initialBody + "\n";
  });
  const [selectedTags, setSelectedTags] = useState<string[]>(initialTags);
  const [selectedReferences, setSelectedReferences] = useState<string[]>(initialReferences);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [allReferences, setAllReferences] = useState<string[]>([]);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) {
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    }
    api.tags.list().then(setAllTags);
    api.references.list().then(rs => setAllReferences(rs.map(r => r.name)));
  }, []);

  function handleKeyDown(e: React.KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      if (canSave) onSave(prepareBody(body), selectedTags, selectedReferences);
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

  const canSave = body.trim().length > 0 || selectedTags.length > 0 || selectedReferences.length > 0;

  return (
    <div className="note-editor">
      <div className="note-editor-hint">Ctrl+Enter to save · Esc to cancel · ⌘1 log · ⌘2 recall</div>
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
        <TagReferencePicker
          label="Tags"
          prefix="#"
          kind="tag"
          allItems={allTags}
          selected={selectedTags}
          onChange={setSelectedTags}
        />
        <TagReferencePicker
          label="References"
          prefix="@"
          kind="reference"
          allItems={allReferences}
          selected={selectedReferences}
          onChange={setSelectedReferences}
        />
      </div>
      <div className="note-editor-actions">
        <button className="btn btn-primary" onClick={() => onSave(prepareBody(body), selectedTags, selectedReferences)} disabled={!canSave}>
          Save
        </button>
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        {onPin && (
          <button className="btn-icon btn-icon--flag note-editor-pin" title={isPinned ? "unpin" : "pin"} onClick={isPinned ? onUnpin : onPin}>
            {isPinned ? "★" : "☆"}
          </button>
        )}
      </div>
    </div>
  );
}
