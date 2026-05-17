import { useState } from "react";
import { api } from "../api";

interface Props {
  onSyncComplete: () => void;
}

type State = "idle" | "syncing" | "needs_auth" | "connecting";

export function SyncButton({ onSyncComplete }: Props) {
  const [state, setState] = useState<State>("idle");
  const [msg, setMsg]     = useState("");

  async function handleSync() {
    setState("syncing");
    setMsg("");
    try {
      const res = await api.sync.run();
      if (res.needs_auth) {
        setState("needs_auth");
        setMsg("Google Drive is not authorized.");
      } else {
        setState("idle");
        setMsg(res.message);
        onSyncComplete();
      }
    } catch (err) {
      setState("idle");
      setMsg(String(err));
    }
  }

  async function handleConnect() {
    setState("connecting");
    setMsg("A browser window has been opened. Complete authorization to continue.");
    try {
      await api.auth.googleConnect();
      setMsg("");
      await handleSync();
    } catch (err) {
      setState("idle");
      setMsg(String(err));
    }
  }

  const busy = state === "syncing" || state === "connecting";

  return (
    <div className="sync-wrapper">
      <button className="btn btn-secondary" onClick={handleSync} disabled={busy}>
        {state === "syncing" ? "Syncing…" : "Sync"}
      </button>
      {state === "needs_auth" && (
        <button className="btn btn-primary" onClick={handleConnect} disabled={busy}>
          Connect Google Drive
        </button>
      )}
      {msg && <span className="sync-msg">{msg}</span>}
    </div>
  );
}
