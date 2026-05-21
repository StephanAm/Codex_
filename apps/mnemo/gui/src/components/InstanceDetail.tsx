import { Instance } from "../api";

interface Props {
  instance: Instance;
}

export function InstanceDetail({ instance }: Props) {
  return (
    <div className="instance-detail">
      <div className="instance-detail-header">
        <span className="instance-detail-kind">{instance.type.name}</span>
        <span className="instance-detail-name">{instance.name}</span>
      </div>
      {instance.description && (
        <p className="instance-detail-desc">{instance.description}</p>
      )}
      {instance.references.length > 0 && (
        <div className="instance-detail-refs">
          {instance.references.map(r => (
            <span key={r} className="badge badge-reference">@{r}</span>
          ))}
        </div>
      )}
    </div>
  );
}
