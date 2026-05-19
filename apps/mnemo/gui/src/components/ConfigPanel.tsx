import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { api, Config } from "../api";

interface GuiConfig {
  start_backend_on_startup: boolean;
  kill_backend_on_exit: boolean;
}

interface Props {
  onClose: () => void;
}

export function ConfigPanel({ onClose }: Props) {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [tagsInput, setTagsInput] = useState("");
  const [folderInput, setFolderInput] = useState("");
  const [adapterInput, setAdapterInput] = useState("google_drive");
  const [localPathInput, setLocalPathInput] = useState("");
  const [debounceInput, setDebounceInput] = useState("600000");
  const [guiCfg, setGuiCfg] = useState<GuiConfig>({ start_backend_on_startup: true, kill_backend_on_exit: true });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.config.get().then(c => {
      setCfg(c);
      setTagsInput(c.default_tags.join(" "));
      setFolderInput(c.sync_folder);
      setAdapterInput(c.sync_adapter);
      setLocalPathInput(c.sync_local_path);
      setDebounceInput(String(c.autosync_debounce_ms));
    });
    invoke<GuiConfig>("get_gui_config").then(g => setGuiCfg(g));
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      await api.config.update({
        default_tags: tagsInput.split(/\s+/).filter(Boolean),
        sync_folder: folderInput.trim() || "note-taker-sync",
        sync_adapter: adapterInput,
        sync_local_path: localPathInput,
        autosync_debounce_ms: parseInt(debounceInput, 10) || 600_000,
      });
      await invoke("set_gui_config", { config: guiCfg });
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

      <label className="config-label">
        Auto-sync idle timeout (ms)
        <span className="config-hint">Push after this many ms of inactivity. Default: 600000 (10 min).</span>
        <input
          className="config-input"
          value={debounceInput}
          onChange={e => setDebounceInput(e.target.value)}
          placeholder="600000"
        />
      </label>

      <div className="config-label">
        Backend lifecycle
        <span className="config-hint">Controls how Mnemo manages the API server process. Takes effect on next launch.</span>
      </div>
      <label className="config-toggle">
        <input
          type="checkbox"
          checked={guiCfg.start_backend_on_startup}
          onChange={e => setGuiCfg(g => ({ ...g, start_backend_on_startup: e.target.checked }))}
        />
        Start backend on startup
      </label>
      <label className="config-toggle">
        <input
          type="checkbox"
          checked={guiCfg.kill_backend_on_exit}
          onChange={e => setGuiCfg(g => ({ ...g, kill_backend_on_exit: e.target.checked }))}
        />
        Kill backend on exit
      </label>

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
