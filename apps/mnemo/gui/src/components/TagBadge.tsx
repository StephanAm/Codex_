interface Props {
  text: string;
  kind: "tag" | "entity";
}

export function TagBadge({ text, kind }: Props) {
  return (
    <span className={`badge badge-${kind}`}>
      {kind === "tag" ? `#${text}` : `@${text}`}
    </span>
  );
}
