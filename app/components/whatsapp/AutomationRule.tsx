export default function AutomationRule({name,trigger}:{name:string;trigger:string}){return <div className="activity-row"><strong>{name}</strong><span>{trigger}</span></div>}
