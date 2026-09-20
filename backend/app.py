from flask import Flask,jsonify,request,make_response
from datetime import datetime,timezone
from bson import ObjectId
import secrets
from .config import Config
from .db import db,init_indexes
from .security import hash_password,verify_password,token_for,read_token,encrypt_secret
from .services import audit,send_email,document_pdf,openai_admin
app=Flask(__name__);app.config.from_object(Config)
try:init_indexes()
except Exception:pass
def oid(x):return ObjectId(x) if x and ObjectId.is_valid(x) else None
def auth():
 t=read_token()
 if not t:return None
 return db().users.find_one({"_id":oid(t["sub"])})
def admin():
 u=auth();return u if u and u.get("role")=="ADMIN" else None
@app.get("/api/health")
def health():
 try:db().command("ping");ok=True
 except:ok=False
 return jsonify(ok=ok,service="fluent-business-automation")
@app.post("/api/auth/register")
def register():
 d=request.get_json() or {};email=d.get("email","").strip().lower();password=d.get("password","");name=d.get("businessName","").strip()
 if not email or not name or len(password)<12:return jsonify(error="Business name, email and a 12+ character password are required"),400
 if db().users.find_one({"email":email}):return jsonify(error="Account already exists"),409
 code=f"{secrets.randbelow(1000000):06d}";uid=db().users.insert_one({"email":email,"passwordHash":hash_password(password),"role":"CLIENT_OWNER","emailVerified":False,"createdAt":datetime.now(timezone.utc)}).inserted_id
 bid=db().businesses.insert_one({"ownerId":uid,"businessName":name,"email":email,"status":"PENDING","createdAt":datetime.now(timezone.utc)}).inserted_id
 db().verification_tokens.insert_one({"userId":uid,"codeHash":hash_password(code),"expiresAt":datetime.now(timezone.utc).timestamp()+600,"used":False})
 send_email(email,"Verify your account",f"<p>Your verification code is <strong>{code}</strong>. It expires in 10 minutes.</p>")
 audit(db(),str(uid),"REGISTER",str(bid));return jsonify(message="Verification code sent",userId=str(uid)),201
@app.post("/api/auth/verify-email")
def verify_email():
 d=request.get_json() or {};u=db().users.find_one({"email":d.get("email","").strip().lower()});now_ts=datetime.now(timezone.utc).timestamp()
 if not u:return jsonify(error="Invalid verification request"),400
 tok=db().verification_tokens.find_one({"userId":u["_id"],"used":False},sort=[("expiresAt",-1)])
 if not tok or tok["expiresAt"]<now_ts or not verify_password(d.get("code",""),tok["codeHash"]):return jsonify(error="Invalid or expired code"),400
 db().verification_tokens.update_one({"_id":tok["_id"]},{"$set":{"used":True}});db().users.update_one({"_id":u["_id"]},{"$set":{"emailVerified":True}});return jsonify(message="Email verified")
@app.post("/api/auth/login")
def login():
 d=request.get_json() or {};u=db().users.find_one({"email":d.get("email","").strip().lower()})
 if not u or not verify_password(d.get("password",""),u["passwordHash"]):return jsonify(error="Invalid credentials"),401
 if u.get("role")!="ADMIN" and not u.get("emailVerified"):return jsonify(error="Email verification required"),403
 r=make_response(jsonify(ok=True,role="admin" if u.get("role")=="ADMIN" else "client"));r.set_cookie(app.config["COOKIE_NAME"],token_for(u),httponly=True,secure=app.config["COOKIE_SECURE"],samesite="Lax",max_age=43200,path="/");return r
@app.post("/api/auth/logout")
def logout():
 r=make_response(jsonify(ok=True));r.delete_cookie(app.config["COOKIE_NAME"],path="/");return r
@app.get("/api/me")
def me():
 u=auth()
 if not u:return jsonify(error="Unauthorized"),401
 return jsonify(id=str(u["_id"]),email=u["email"],role=u["role"],emailVerified=u.get("emailVerified",False))
@app.post("/api/admin/subscription")
def subscription():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 d=request.get_json() or {};bid=oid(d.get("businessId"));b=db().businesses.find_one({"_id":bid})
 if not b:return jsonify(error="Business not found"),404
 sub={"businessId":bid,"plan":d.get("plan","Standard"),"amount":float(d.get("amount",0)),"currency":d.get("currency","KES"),"status":"ACTIVE","startsAt":datetime.now(timezone.utc),"endsAt":d.get("endsAt")}
 db().subscriptions.update_one({"businessId":bid},{"$set":sub},upsert=True);audit(db(),str(u["_id"]),"SET_SUBSCRIPTION",str(bid),{"plan":sub["plan"],"amount":sub["amount"]});return jsonify(message="Subscription saved")
@app.get("/api/admin/overview")
def overview():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 cs=[]
 for b in db().businesses.find().sort("createdAt",-1):
  o=db().users.find_one({"_id":b["ownerId"]},{"email":1});cs.append({"_id":str(b["_id"]),"businessName":b["businessName"],"email":o["email"] if o else b.get("email"),"status":b.get("status","PENDING"),"aiConfigured":bool(db().ai_credentials.find_one({"businessId":b["_id"],"active":True})),"documentCount":db().documents.count_documents({"businessId":b["_id"]})})
 logs=[{"_id":str(x["_id"]),"action":x["action"],"createdAt":x["createdAt"].isoformat()} for x in db().audit_logs.find().sort("createdAt",-1).limit(50)]
 return jsonify(me={"email":u["email"],"role":u["role"]},clients=cs,logs=logs)
@app.post("/api/admin/client/toggle")
def toggle():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 d=request.get_json() or {};b=db().businesses.find_one({"_id":oid(d.get("businessId"))})
 if not b:return jsonify(error="Not found"),404
 s="SUSPENDED" if b.get("status")=="ACTIVE" else "ACTIVE";db().businesses.update_one({"_id":b["_id"]},{"$set":{"status":s,"updatedAt":datetime.now(timezone.utc)}});audit(db(),str(u["_id"]),"TOGGLE_CLIENT",str(b["_id"]),{"status":s});return jsonify(message=f"Client {s.lower()}")
@app.post("/api/admin/client/approve-documents")
def approve_docs():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 bid=oid((request.get_json() or {}).get("businessId"));db().documents.update_many({"businessId":bid},{"$set":{"approved":True,"approvedAt":datetime.now(timezone.utc),"approvedBy":u["_id"]}});audit(db(),str(u["_id"]),"APPROVE_DOCUMENTS",str(bid));return jsonify(message="Documents approved")
@app.post("/api/admin/client/ai")
def client_ai():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 d=request.get_json() or {};bid=oid(d.get("businessId"));key=d.get("apiKey","").strip()
 if not bid or not key:return jsonify(error="Business and API key required"),400
 db().ai_credentials.update_one({"businessId":bid},{"$set":{"businessId":bid,"encryptedKey":encrypt_secret(key),"model":d.get("model","gpt-5.6-luna"),"active":True,"updatedAt":datetime.now(timezone.utc)}},upsert=True);audit(db(),str(u["_id"]),"REPLACE_CLIENT_AI_KEY",str(bid),{"model":d.get("model","gpt-5.6-luna")});return jsonify(message="Client AI key saved securely")
@app.post("/api/admin/ai/test")
def ai_test():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 d=request.get_json() or {};out=openai_admin(d.get("prompt",""));audit(db(),str(u["_id"]),"ADMIN_AI",meta={"promptLength":len(d.get("prompt",""))});return jsonify(message=out)
@app.post("/api/admin/backup")
def backup():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 audit(db(),str(u["_id"]),"BACKUP_REQUEST",meta={"kind":(request.get_json() or {}).get("kind")});return jsonify(message="Backup hook accepted; configure Google Sheets credentials before export")
@app.get("/api/client/documents")
def client_documents():
 u=auth()
 if not u:return jsonify(error="Unauthorized"),401
 b=db().businesses.find_one({"ownerId":u["_id"]})
 if not b:return jsonify(documents=[])
 out=[]
 for x in db().documents.find({"businessId":b["_id"],"approved":True}).sort("createdAt",-1):
  out.append({"id":str(x["_id"]),"number":x["number"],"title":x["title"],"amount":x["amount"],"currency":x["currency"],"status":x["status"]})
 return jsonify(documents=out)
@app.post("/api/admin/documents")
def create_document():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 d=request.get_json() or {};b=db().businesses.find_one({"_id":oid(d.get("businessId"))})
 if not b:return jsonify(error="Business not found"),404
 kind=d.get("kind","invoice").upper();num=f"{'INV' if kind=='INVOICE' else 'RCT'}-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}";doc={"businessId":b["_id"],"businessName":b["businessName"],"email":b.get("email"),"title":"Invoice" if kind=="INVOICE" else "Receipt","number":num,"amount":float(d.get("amount",0)),"currency":"KES","status":"ISSUED","approved":False,"createdAt":datetime.now(timezone.utc)};did=db().documents.insert_one(doc).inserted_id;audit(db(),str(u["_id"]),f"CREATE_{kind}",str(did),{"amount":doc["amount"]});return jsonify(id=str(did),number=num),201
@app.post("/api/admin/send-document")
def send_document():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 x=db().documents.find_one({"_id":oid((request.get_json() or {}).get("documentId"))})
 if not x:return jsonify(error="Not found"),404
 send_email(x["email"],f'{x["title"]} {x["number"]}',f'<p>Your {x["title"].lower()} <strong>{x["number"]}</strong> is attached.</p>',[(f'{x["number"]}.pdf',document_pdf(x),("application","pdf"))]);db().documents.update_one({"_id":x["_id"]},{"$set":{"sentAt":datetime.now(timezone.utc)}});audit(db(),str(u["_id"]),"SEND_DOCUMENT",str(x["_id"]),{"to":x["email"]});return jsonify(message="Document emailed")
@app.get("/api/documents/<docid>/pdf")
def pdf(docid):
 u=auth();x=db().documents.find_one({"_id":oid(docid)}) if u else None
 if not x:return jsonify(error="Not found"),404
 if u.get("role")!="ADMIN" and not x.get("approved"):return jsonify(error="Not found"),404
 r=make_response(document_pdf(x));r.headers["Content-Type"]="application/pdf";r.headers["Content-Disposition"]=f'inline; filename="{x["number"]}.pdf"';return r
@app.get("/api/webhooks/whatsapp")
def wa_verify():
 if request.args.get("hub.mode")=="subscribe" and request.args.get("hub.verify_token")==app.config["WHATSAPP_VERIFY_TOKEN"]:return request.args.get("hub.challenge","")
 return "Forbidden",403
@app.post("/api/webhooks/whatsapp")
def wa_webhook():return jsonify(received=True)

@app.post("/api/webhooks/daraja")
def daraja_callback():
 payload=request.get_json(silent=True) or {};db().daraja_callbacks.insert_one({"payload":payload,"createdAt":datetime.now(timezone.utc)});return jsonify(ResultCode=0,ResultDesc="Accepted")
