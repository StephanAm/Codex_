import { useEffect, useRef, useState } from "react";

interface Props {
  initialBody?: string;
  onSave: (body: string) => void;
  onCancel: () => void;
}

export function NoteEditor({ initialBody = "", onSave, onCancel }: Props) {
  const [body, setBody] = useState(initialBody);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    ref.current?.focus();
  }, []);

  function handleKeyDown(e: React.KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      onSave(body.trim());
    }
    if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
    }
  }

  return (
    <div className="note-editor">
      <div className="note-editor-hint">Ctrl+Enter to save · Esc to cancel</div>
      <textarea
        ref={ref}
        className="note-editor-textarea"
        value={body}
        onChange={e => setBody(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Write your note here…  Use #tags and @entities"
        spellCheck
      />
      <div className="note-editor-actions">
        <button className="btn btn-primary" onClick={() => onSave(body.trim())} disabled={!body.trim()}>
          Save
        </button>
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
