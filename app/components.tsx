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


export function HelpCenter({topic='general'}:{topic?:'general'|'whatsapp'|'payments'|'ai'|'invoices'}){
  const [open,setOpen]=useState(false);
  const [tab,setTab]=useState(topic);
  const topics=[
    {id:'general',label:'Getting started'},
    {id:'whatsapp',label:'WhatsApp API'},
    {id:'payments',label:'M-Pesa / Daraja'},
    {id:'ai',label:'AI setup'},
    {id:'invoices',label:'Invoices & payment links'}
  ] as const;
  return <>
    <button type="button" className="help-button" onClick={()=>{setTab(topic);setOpen(true)}}><span className="help-question">?</span> How to use</button>
    {open&&<div className="help-overlay" onMouseDown={()=>setOpen(false)}>
      <div className="help-modal" role="dialog" aria-modal="true" aria-label="How to use Business Automation" onMouseDown={e=>e.stopPropagation()}>
        <div className="help-modal-head"><div><div className="help-eyebrow">LEARN & SET UP</div><h2>How to use Business Automation</h2><p>Step-by-step guidance for navigation, API credentials and the main workflows.</p></div><button className="help-close" onClick={()=>setOpen(false)} aria-label="Close">×</button></div>
        <div className="help-tabs">{topics.map(t=><button key={t.id} className={tab===t.id?'active':''} onClick={()=>setTab(t.id)}>{t.label}</button>)}</div>
        <div className="help-content">
          {tab==='general'&&<div className="help-section"><h3>Start here</h3><ol><li><b>Overview</b> — see customers, messages, payments and AI usage.</li><li><b>WhatsApp</b> — connect your Meta WhatsApp Cloud API account, test the connection, then send messages and create automation rules.</li><li><b>Customers / CRM</b> — create and manage customer records.</li><li><b>AI</b> — add your OpenAI API key and configure customer-response behavior.</li><li><b>Payments</b> — record payments or initiate an M-Pesa STK Push when Daraja is configured.</li><li><b>Invoices & Receipts</b> — create invoices, copy payment links, send invoices and open PDF receipts.</li><li><b>Reports</b> and <b>Audit history</b> — review activity and operational totals.</li></ol><div className="help-tip">If a connection says <b>Not connected</b>, save the credentials first and use <b>Test connection</b> before trying to send a message.</div></div>}
          {tab==='whatsapp'&&<div className="help-section"><h3>WhatsApp Cloud API</h3><p className="help-muted">The values in the WhatsApp form come from Meta, not from the customer's normal WhatsApp app.</p><div className="help-steps"><div><span>1</span><p>Open <a href="https://developers.facebook.com/" target="_blank" rel="noreferrer">Meta for Developers</a> and sign in with the Meta business account that owns the WhatsApp Business account.</p></div><div><span>2</span><p>Open your Meta app → <b>WhatsApp</b> → <b>API Setup</b>. Copy the <b>Phone Number ID</b>. It is normally a numeric Meta ID, not the phone number itself.</p></div><div><span>3</span><p>Find the <b>WhatsApp Business Account ID (WABA ID)</b> in the WhatsApp/Business settings. It is also a Meta numeric ID, not an email address.</p></div><div><span>4</span><p>For development, Meta provides a temporary access token in API Setup. For production, create a System User in Meta Business Settings and generate a token with the required WhatsApp permissions.</p></div><div><span>5</span><p>Paste the token into <b>Access token</b>, save it, then press <b>Test connection</b>. Only after the status shows Connected should you send a message.</p></div></div><div className="help-tip"><b>Important:</b> WABA ID and Phone Number ID are identifiers. Do not enter your Gmail address or the ordinary customer phone number in those fields.</div><a className="help-link" href="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/" target="_blank" rel="noreferrer">Open WhatsApp Cloud API guide ↗</a></div>}
          {tab==='payments'&&<div className="help-section"><h3>M-Pesa / Daraja setup</h3><div className="help-steps"><div><span>1</span><p>Open <a href="https://developer.safaricom.co.ke/" target="_blank" rel="noreferrer">Safaricom Daraja</a> and sign in/register your developer account.</p></div><div><span>2</span><p>Create/select an app and enable the M-Pesa APIs required by your business.</p></div><div><span>3</span><p>Configure the Daraja consumer key, consumer secret, passkey, shortcode and public callback URL in your Vercel environment.</p></div><div><span>4</span><p>The callback URL must point to <b>/api/webhooks/daraja</b> on your deployed domain. The application now accepts this route and the legacy M-Pesa callback route.</p></div><div><span>5</span><p>Use the Payments page to initiate a test STK Push. Check the transaction history and Vercel logs if Daraja rejects the request.</p></div></div><div className="help-tip">Never paste your Daraja consumer secret or passkey into a normal customer-facing form. Keep credentials in the deployment environment.</div><a className="help-link" href="https://developer.safaricom.co.ke/" target="_blank" rel="noreferrer">Open Safaricom Daraja ↗</a></div>}
          {tab==='ai'&&<div className="help-section"><h3>AI setup</h3><ol><li>Go to <b>AI</b> in the left navigation.</li><li>Paste the OpenAI API key into the protected API-key field.</li><li>Select the model and define the business instructions, tone and response length.</li><li>Save AI, then use <b>Generate</b> to test a customer response.</li><li>For administrator AI, use the separate Admin AI workspace; it reads a sanitized server-side snapshot rather than exposing credentials.</li></ol><a className="help-link" href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer">Open OpenAI API keys ↗</a></div>}
          {tab==='invoices'&&<div className="help-section"><h3>Invoices & online payment</h3><ol><li>Open <b>Invoices & Receipts</b>.</li><li>Enter the customer and amount and keep <b>Enable public payment link</b> enabled.</li><li>Create the invoice and copy the generated payment link.</li><li>Send the link to the customer. They can open it without logging into the dashboard.</li><li>For M-Pesa STK Push, the customer enters a valid Kenyan mobile number and submits the payment.</li><li>After Daraja confirms the callback, the payment/invoice status is updated.</li></ol><div className="help-tip">If a payment returns 502, open the payment record/log details. The application now records the provider failure reason instead of hiding it.</div></div>}
        </div>
        <div className="help-modal-foot"><span>Credentials are never shown in the help window.</span><button className="fluent-primary" onClick={()=>setOpen(false)}>Got it</button></div>
      </div>
    </div>}
  </>;
}
