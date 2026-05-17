export type SyncState = "idle" | "syncing" | "needs_auth" | "connecting";

interface Props {
  syncState: SyncState;
  syncMsg:   string;
  onSync:    () => void;
  onConnect: () => void;
}

export function SyncButton({ syncState, syncMsg, onSync, onConnect }: Props) {
  const busy = syncState === "syncing" || syncState === "connecting";

  return (
    <div className="sync-wrapper">
      <button className="btn btn-secondary" onClick={onSync} disabled={busy}>
        {syncState === "syncing" ? "Syncing…" : "Sync"}
      </button>
      {syncState === "needs_auth" && (
        <button className="btn btn-primary" onClick={onConnect} disabled={busy}>
          Connect Google Drive
        </button>
      )}
      {syncMsg && <span className="sync-msg">{syncMsg}</span>}
    </div>
  );
}
