"use client";
import {useEffect,useState} from "react";
import {Monitor, Moon, Sun, Laptop, Menu, X} from "lucide-react";

export type ThemeMode = "system" | "mac" | "normal";

export function ThemeControl(){
  const [mode,setMode]=useState<ThemeMode>("system");
  useEffect(()=>{
    const raw=localStorage.getItem("fluent-theme");
    const next: ThemeMode = raw === "mac" || raw === "normal" || raw === "system" ? raw : "system";
    setMode(next); applyTheme(next);
  },[]);
  function applyTheme(next:ThemeMode){
    document.documentElement.dataset.theme=next;
    localStorage.setItem("fluent-theme",next);
  }
  return <div className="theme-control" aria-label="Appearance mode">
    <button className={mode==="system"?"theme-active":""} onClick={()=>{setMode("system");applyTheme("system")}} title="System"><Monitor size={15}/><span>System</span></button>
    <button className={mode==="mac"?"theme-active":""} onClick={()=>{setMode("mac");applyTheme("mac")}} title="Mac style"><Laptop size={15}/><span>Mac</span></button>
    <button className={mode==="normal"?"theme-active":""} onClick={()=>{setMode("normal");applyTheme("normal")}} title="Fluent style"><Sun size={15}/><span>Normal</span></button>
  </div>
}

export function MobileMenu({open,onToggle}:{open:boolean;onToggle:()=>void}){
  return <button className="mobile-menu" onClick={onToggle} aria-label={open?"Close menu":"Open menu"}>{open?<X size={20}/>:<Menu size={20}/>}</button>
}

export function StatusPill({children,tone="neutral"}:{children:React.ReactNode;tone?:"neutral"|"success"|"warning"|"danger"}){
  return <span className={`status-pill status-${tone}`}>{children}</span>
}

export type CoverageGroup = {name:string; items:string[]};
export function CoverageIndex({title,groups}:{title:string;groups:CoverageGroup[]}){
  const [query,setQuery]=useState("");
  const q=query.trim().toLowerCase();
  const filtered=groups.map(g=>({...g,items:g.items.filter(i=>!q||`${g.name} ${i}`.toLowerCase().includes(q))})).filter(g=>g.items.length);
  return <section className="mt-5 fluent-card section-card" aria-label={title}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="section-title">{title}</div><div className="section-subtitle">Complete activity coverage for navigation, permissions and audit-log planning. Items marked as configuration or review require their corresponding backend integration.</div></div><span className="status-pill status-success">{groups.reduce((n,g)=>n+g.items.length,0)} activities</span></div>
    <div className="mt-4"><input className="fluent-input" aria-label="Search activities" placeholder="Search activities…" value={query} onChange={e=>setQuery(e.target.value)}/></div>
    <div className="coverage-grid mt-4">{filtered.map(g=><div className="coverage-group" key={g.name}><h3>{g.name}</h3><ul>{g.items.map(i=><li key={i}><span className="coverage-dot"/> {i}</li>)}</ul></div>)}</div>
    {!filtered.length&&<div className="notice mt-4">No activities match your search.</div>}
  </section>;
}
