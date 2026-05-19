interface Props { className?: string; }

export function RecallSidebar({ className = "" }: Props) {
  return (
    <div className={`recall-sidebar${className ? " " + className : ""}`}>
      <span className="recall-sidebar-empty">no pins yet.</span>
    </div>
  );
}
