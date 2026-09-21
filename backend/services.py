import io,ssl,smtplib,requests,base64
from email.message import EmailMessage
from datetime import datetime,timezone
from urllib.parse import urlsplit,urlunsplit
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import qrcode
from flask import current_app
from .security import decrypt_secret
def now():return datetime.now(timezone.utc)
def audit(db,actor,action,target="",meta=None):db.audit_logs.insert_one({"actor":actor,"action":action,"target":target,"meta":meta or {},"createdAt":now()})
def website_root_url():
 raw=(current_app.config.get("DARAJA_CALLBACK_URL") or "").strip()
 if not raw:return ""
 u=urlsplit(raw if "://" in raw else "https://"+raw)
 return urlunsplit((u.scheme,u.netloc,"","",""))

def qr_png(data):
 if not data: return b""
 q=qrcode.QRCode(version=None,error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=8,border=3);q.add_data(data);q.make(fit=True)
 b=io.BytesIO();q.make_image().save(b,format="PNG");return b.getvalue()

def send_email(to,subject,html,attachments=None):
 c=current_app.config
 if not c["SMTP_USERNAME"] or not c["SMTP_PASSWORD"]:raise RuntimeError("SMTP not configured")
 site=website_root_url()
 if site:
  qr=qr_png(site);html += f'<hr style="border:0;border-top:1px solid #e5e7eb;margin:28px 0"><div style="font:14px Arial,sans-serif;color:#475569"><strong>GEOPRAM TECHNOLOGIES</strong><br>Scan to open our website<br><img src="cid:website-qr" width="150" height="150" alt="Website QR code" style="margin-top:8px"><br><a href="{site}">{site}</a></div>'
 else: qr=b""
 m=EmailMessage();m["From"]=c["SMTP_FROM"] or c["SMTP_USERNAME"];m["To"]=to;m["Subject"]=subject;m.set_content("HTML email");m.add_alternative(html,subtype="html")
 if qr:
  m.get_payload()[-1].add_related(qr,maintype="image",subtype="png",cid="<website-qr>")
 for name,data,ctype in attachments or []:m.add_attachment(data,maintype=ctype[0],subtype=ctype[1],filename=name)
 with smtplib.SMTP(c["SMTP_HOST"],c["SMTP_PORT"],timeout=20) as s:s.starttls(context=ssl.create_default_context());s.login(c["SMTP_USERNAME"],c["SMTP_PASSWORD"]);s.send_message(m)

def receipt_pdf(receipt,business_name="Business"):
 b=io.BytesIO();c=canvas.Canvas(b,pagesize=A4);_,h=A4
 c.setFont("Helvetica-Bold",20);c.drawString(50,h-60,"PAYMENT RECEIPT")
 c.setFont("Helvetica",10);y=h-100
 rows=[("Receipt",receipt.get("number","")),("Business",business_name),("Invoice",receipt.get("invoiceNumber",receipt.get("invoiceId",""))), ("Amount",f'{receipt.get("currency","KES")} {float(receipt.get("amount",0)):,.2f}'),("Status","PAID"),("Payment method",receipt.get("method","M-Pesa STK")),("M-Pesa receipt",receipt.get("mpesaReceiptNumber","") or "—"),("Paid at",str(receipt.get("paidAt",receipt.get("createdAt",""))))]
 for a,v in rows:c.setFont("Helvetica-Bold",10);c.drawString(50,y,a+":");c.setFont("Helvetica",10);c.drawString(155,y,str(v));y-=22
 verify=receipt.get("verifyUrl","")
 if verify:
  qr=ImageReader(io.BytesIO(qr_png(verify)));c.drawImage(qr,50,105,width=105,height=105,mask="auto");c.setFont("Helvetica",8);c.drawString(165,155,"Scan to verify this receipt online");c.drawString(165,142,verify[:90])
 c.setFont("Helvetica-Bold",42);c.setFillAlpha(0.08);c.drawCentredString(300,38,"G");c.setFillAlpha(1);c.setFont("Helvetica",8);c.drawCentredString(300,22,"GEOPRAM TECHNOLOGIES • DIGITAL RECEIPT")
 c.save();return b.getvalue()
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
