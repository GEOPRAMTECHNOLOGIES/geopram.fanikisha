export default function AdminTable({rows}:{rows:any[]}){return <div className="activity-list">{rows.map((r,i)=><div className="activity-row" key={r._id||i}>{JSON.stringify(r)}</div>)}</div>}
