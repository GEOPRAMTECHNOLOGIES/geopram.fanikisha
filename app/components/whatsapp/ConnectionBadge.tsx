export default function ConnectionBadge({connected}:{connected:boolean}){return <span className="status-pill">{connected?"Connected":"Not connected"}</span>}
