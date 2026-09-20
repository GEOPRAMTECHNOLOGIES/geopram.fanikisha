import io,ssl,smtplib,requests
from email.message import EmailMessage
from datetime import datetime,timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from flask import current_app
from .security import decrypt_secret
def now():return datetime.now(timezone.utc)
def audit(db,actor,action,target="",meta=None):db.audit_logs.insert_one({"actor":actor,"action":action,"target":target,"meta":meta or {},"createdAt":now()})
def send_email(to,subject,html,attachments=None):
 c=current_app.config
 if not c["SMTP_USERNAME"] or not c["SMTP_PASSWORD"]:raise RuntimeError("SMTP not configured")
 m=EmailMessage();m["From"]=c["SMTP_FROM"] or c["SMTP_USERNAME"];m["To"]=to;m["Subject"]=subject;m.set_content("HTML email");m.add_alternative(html,subtype="html")
 for name,data,ctype in attachments or []:m.add_attachment(data,maintype=ctype[0],subtype=ctype[1],filename=name)
 with smtplib.SMTP(c["SMTP_HOST"],c["SMTP_PORT"],timeout=20) as s:s.starttls(context=ssl.create_default_context());s.login(c["SMTP_USERNAME"],c["SMTP_PASSWORD"]);s.send_message(m)
def document_pdf(doc):
 b=io.BytesIO();c=canvas.Canvas(b,pagesize=A4);_,h=A4;c.setFont("Helvetica-Bold",18);c.drawString(50,h-60,doc["title"]);y=h-100;c.setFont("Helvetica",10)
 for a,v in [("Number",doc["number"]),("Business",doc.get("businessName","")),("Email",doc.get("email","")),("Amount",f'{doc.get("currency","KES")} {doc.get("amount",0):,.2f}'),("Status",doc.get("status",""))]:c.drawString(50,y,f"{a}: {v}");y-=22
 c.drawString(50,y,f"Created: {doc['createdAt'].isoformat()}");c.save();return b.getvalue()
def openai_admin(prompt):
 from openai import OpenAI
 key=current_app.config["OPENAI_API_KEY"]
 if not key:raise RuntimeError("OPENAI_API_KEY not configured")
 return OpenAI(api_key=key).responses.create(model=current_app.config["OPENAI_ADMIN_MODEL"],input=prompt).output_text
def whatsapp_send(integration,to,text):
 token=decrypt_secret(integration["accessToken"]);r=requests.post(f"https://graph.facebook.com/v23.0/{integration['phoneNumberId']}/messages",headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},json={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text}},timeout=20);r.raise_for_status();return r.json()
