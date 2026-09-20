"use client";
import {useEffect,useState} from "react";
import {Monitor, Moon, Sun, Laptop, Menu, X} from "lucide-react";

export type ThemeMode = "system" | "mac" | "normal";

export function ThemeControl(){
  const [mode,setMode]=useState<ThemeMode>("system");
  useEffect(()=>{
    const saved=(localStorage.getItem("fluent-theme") as ThemeMode)|"system";
    const next=(saved==="mac"||saved==="normal"||saved==="system")?saved:"system";
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
