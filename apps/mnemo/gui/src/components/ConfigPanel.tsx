import { useEffect, useState } from "react";
import { api, Config } from "../api";

interface Props {
  onClose: () => void;
}

export function ConfigPanel({ onClose }: Props) {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [tagsInput, setTagsInput] = useState("");
  const [folderInput, setFolderInput] = useState("");
  const [adapterInput, setAdapterInput] = useState("google_drive");
  const [localPathInput, setLocalPathInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.config.get().then(c => {
      setCfg(c);
      setTagsInput(c.default_tags.join(" "));
      setFolderInput(c.sync_folder);
      setAdapterInput(c.sync_adapter);
      setLocalPathInput(c.sync_local_path);
    });
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      await api.config.update({
        default_tags: tagsInput.split(/\s+/).filter(Boolean),
        sync_folder: folderInput.trim() || "note-taker-sync",
        sync_adapter: adapterInput,
        sync_local_path: localPathInput,
      });
      setMsg("Saved.");
      setTimeout(() => setMsg(""), 2000);
    } finally {
      setSaving(false);
    }
  }

  if (!cfg) return <div className="config-panel"><p>Loading…</p></div>;

  return (
    <div className="config-panel">
      <div className="config-panel-header">
        <h2>Configuration</h2>
        <button className="btn-icon" onClick={onClose} title="Close">✕</button>
      </div>

      <label className="config-label">
        Default tags
        <span className="config-hint">Space-separated, without #. Applied to every new note.</span>
        <input
          className="config-input"
          value={tagsInput}
          onChange={e => setTagsInput(e.target.value)}
          placeholder="e.g. work daily"
        />
      </label>

      <label className="config-label">
        Sync adapter
        <span className="config-hint">Storage backend for sync.</span>
        <select
          className="config-input"
          value={adapterInput}
          onChange={e => setAdapterInput(e.target.value)}
        >
          <option value="google_drive">Google Drive</option>
          <option value="local_folder">Local folder</option>
        </select>
      </label>

      {adapterInput === "local_folder" && (
        <label className="config-label">
          Local sync path
          <span className="config-hint">Folder path used as the sync location.</span>
          <input
            className="config-input"
            value={localPathInput}
            onChange={e => setLocalPathInput(e.target.value)}
            placeholder="/path/to/sync/folder"
          />
        </label>
      )}

      {adapterInput === "google_drive" && (
        <label className="config-label">
          Google Drive folder
          <span className="config-hint">Folder name used for sync.</span>
          <input
            className="config-input"
            value={folderInput}
            onChange={e => setFolderInput(e.target.value)}
            placeholder="note-taker-sync"
          />
        </label>
      )}

      <div className="config-actions">
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        {msg && <span className="config-msg">{msg}</span>}
      </div>
    </div>
  );
}
