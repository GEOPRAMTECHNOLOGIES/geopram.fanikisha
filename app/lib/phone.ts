export function normalizeKenyanPhone(v:string){const p=(v||"").replace(/\D/g,"");return p.startsWith("0")?`254${p.slice(1)}`:p.startsWith("254")?p:p}
