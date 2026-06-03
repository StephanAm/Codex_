// Copyright (C) 2026 Stephan Marais
// SPDX-License-Identifier: AGPL-3.0-or-later

interface Props {
  text: string;
  kind: "tag" | "reference";
}

export function TagBadge({ text, kind }: Props) {
  return (
    <span className={`badge badge-${kind}`}>
      {kind === "tag" ? `#${text}` : `@${text}`}
    </span>
  );
}
