import { useState } from "react";
import { api } from "../api";

interface Props {
  onSyncComplete: () => void;
}

export function SyncButton({ onSyncComplete }: Props) {
  const [syncing, setSyncing] = useState(false);
  const [msg, setMsg] = useState("");

  async function handleSync() {
    setSyncing(true);
    setMsg("");
    try {
      const res = await api.sync.run();
      setMsg(res.message);
      onSyncComplete();
    } catch (err) {
      setMsg(String(err));
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="sync-wrapper">
      <button className="btn btn-secondary" onClick={handleSync} disabled={syncing}>
        {syncing ? "Syncing…" : "Sync"}
      </button>
      {msg && <span className="sync-msg">{msg}</span>}
    </div>
  );
}
