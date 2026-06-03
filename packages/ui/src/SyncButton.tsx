// Copyright (C) 2026 Stephan Marais
// SPDX-License-Identifier: AGPL-3.0-or-later

export type SyncState = "idle" | "syncing" | "needs_auth" | "connecting";

interface Props {
  syncState: SyncState;
  onSync:    () => void;
  onConnect: () => void;
}

export function SyncButton({ syncState, onSync, onConnect }: Props) {
  const busy = syncState === "syncing" || syncState === "connecting";

  return (
    <>
      <button className="btn btn-secondary" onClick={onSync} disabled={busy}>
        {syncState === "syncing" ? "Syncing…" : "Sync"}
      </button>
      {syncState === "needs_auth" && (
        <button className="btn btn-primary" onClick={onConnect} disabled={busy}>
          Connect Google Drive
        </button>
      )}
    </>
  );
}
