export default function CustomerTags({tags}:{tags:string[]}){return <div className="flex gap-1 flex-wrap">{(tags||[]).map(t=><span className="status-pill" key={t}>{t}</span>)}</div>}
