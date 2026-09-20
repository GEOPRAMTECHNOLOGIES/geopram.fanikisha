export default function AuditEntry({entry}:{entry:any}){return <div className="activity-row"><strong>{entry?.action}</strong><span>{entry?.createdAt||""}</span></div>}
