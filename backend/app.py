import json
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
 u=auth();return u if u and str(u.get("role","")).upper()=="ADMIN" else None
@app.get("/api/health")
def health():
 try:
  d = db()
  d.command("ping")
  return jsonify(
   ok=True,
   service="fluent-business-automation",
   database=d.name,
   collections=sorted(d.list_collection_names()),
   userCount=d.users.count_documents({}),
  )
 except Exception as e:
  return jsonify(ok=False,service="fluent-business-automation",error="MongoDB connection failed"),503
@app.post("/api/auth/register")
def register():
 setting=db().settings.find_one({"key":"registration_enabled"})
 if setting is not None and not setting.get("value",True):return jsonify(error="Client registration is currently disabled"),403
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
@app.get("/api/auth/registration-status")
def registration_status():
 enabled = db().settings.find_one({"key":"registration_enabled"})
 return jsonify(enabled=True if enabled is None else bool(enabled.get("value", True)))

@app.post("/api/auth/login")
def login():
 d=request.get_json() or {};u=db().users.find_one({"email":d.get("email","").strip().lower()})
 if not u or not verify_password(d.get("password",""),u["passwordHash"]):return jsonify(error="Invalid credentials"),401
 if str(u.get("role","")).upper()!="ADMIN" and not u.get("emailVerified"):return jsonify(error="Email verification required"),403
 audit(db(),str(u["_id"]),"ADMIN_LOGIN" if str(u.get("role","")).upper()=="ADMIN" else "USER_LOGIN",meta={"email":u.get("email")})
 r=make_response(jsonify(ok=True,role="admin" if str(u.get("role","")).upper()=="ADMIN" else "client",redirectPath=("/"+app.config["ADMIN_PATH"].strip("/") if str(u.get("role","")).upper()=="ADMIN" else "/dashboard")));r.set_cookie(app.config["COOKIE_NAME"],token_for(u),httponly=True,secure=app.config["COOKIE_SECURE"],samesite="Lax",max_age=43200,path="/");return r
# Use a host-only session cookie so the browser sends it to the deployed Vercel host.
# COOKIE_DOMAIN remains available in environment/config for compatibility, but is not forced onto the cookie.
@app.post("/api/auth/logout")
def logout():
 u=auth()
 if u:audit(db(),str(u["_id"]),"USER_LOGOUT")
 r=make_response(jsonify(ok=True));r.delete_cookie(app.config["COOKIE_NAME"],path="/");return r
@app.get("/api/me")
def me():
 u=auth()
 if not u:return jsonify(error="Unauthorized"),401
 return jsonify(id=str(u["_id"]),email=u["email"],role=u["role"],emailVerified=u.get("emailVerified",False))
@app.post("/api/admin/registration")
def registration_toggle():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 d=request.get_json() or {}; enabled=bool(d.get("enabled",True))
 db().settings.update_one({"key":"registration_enabled"},{"$set":{"key":"registration_enabled","value":enabled,"updatedAt":datetime.now(timezone.utc),"updatedBy":u["_id"]}},upsert=True)
 audit(db(),str(u["_id"]),"TOGGLE_REGISTRATION",meta={"enabled":enabled})
 return jsonify(enabled=enabled,message="Client registration " + ("enabled" if enabled else "disabled"))

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
 d=request.get_json() or {}
 prompt=(d.get("prompt") or "").strip()
 database=db()
 # Build a sanitized, read-only snapshot from the same MongoDB data shown in the
 # Control Center. Secrets, passwords, access tokens and private keys are never
 # included in the AI context. External deployment/capacity telemetry is not
 # claimed unless it is actually available in the application database.
 businesses=list(database.businesses.find({}, {"businessName":1,"status":1,"createdAt":1}).sort("createdAt",-1).limit(100))
 status_counts={}
 for b in businesses:
  st=b.get("status","PENDING");status_counts[st]=status_counts.get(st,0)+1
 now=datetime.now(timezone.utc)
 def count(coll, query=None):
  return database[coll].count_documents(query or {}) if coll in database.list_collection_names() else 0
 registration_doc=database.settings.find_one({"key":"registration_enabled"})
 registration_enabled=bool(registration_doc.get("value",True)) if registration_doc else True
 audit_rows=list(database.audit_logs.find({}, {"action":1,"target":1,"createdAt":1,"meta":1}).sort("createdAt",-1).limit(25))
 recent=[]
 for x in audit_rows:
  recent.append({"action":x.get("action"),"target":x.get("target",""),"createdAt":x.get("createdAt").isoformat() if x.get("createdAt") else None})
 subs_active=count("subscriptions", {"status":"ACTIVE"})
 subs_pending=count("subscriptions", {"status":"PENDING"})
 subs_cancelled=count("subscriptions", {"status":"CANCELLED"})
 failed_payments=count("payments", {"status":{"$in":["FAILED","ERROR"]}})
 pending_payments=count("payments", {"status":"PENDING"})
 whatsapp_connected=count("whatsapp_integrations", {"active":True})
 whatsapp_automation=count("whatsapp_integrations", {"automationEnabled":True})
 whatsapp_webhook_unverified=count("whatsapp_integrations", {"active":True,"webhookVerified":False})
 ai_enabled=count("ai_credentials", {"active":True})
 docs_pending=count("documents", {"approved":False})
 docs_total=count("documents")
 users_total=count("users")
 clients_total=count("users", {"role":{"$ne":"ADMIN"}})
 failed_logins=count("audit_logs", {"action":"USER_LOGIN_FAILED"})
 failed_ai=count("audit_logs", {"action":"ADMIN_AI_FAILED"})
 context={
  "generatedAt":now.isoformat(),
  "adminEmail":u.get("email"),
  "users":{"total":users_total,"nonAdmin":clients_total},
  "businesses":{"total":len(businesses),"byStatus":status_counts},
  "registration":{"enabled":registration_enabled},
  "documents":{"total":docs_total,"pendingApproval":docs_pending},
  "subscriptions":{"active":subs_active,"pending":subs_pending,"cancelled":subs_cancelled},
  "payments":{"failed":failed_payments,"pending":pending_payments},
  "whatsapp":{"connected":whatsapp_connected,"automationEnabled":whatsapp_automation,"webhookUnverified":whatsapp_webhook_unverified},
  "ai":{"enabled":ai_enabled,"adminAIFailures":failed_ai},
  "security":{"failedLogins":failed_logins},
  "recentAuditEvents":recent,
  "availableTelemetry":["MongoDB application data","Control Center metrics","audit logs"],
  "unavailableTelemetry":["Vercel deployment status","infrastructure capacity","external job queues"]
 }
 system_prompt="""You are the administrative assistant inside a WhatsApp Business Automation SaaS Control Center. You DO have read-only access to the sanitized application snapshot supplied below. Never say you lack access to the administration dashboard when the snapshot contains the requested information. Use only the supplied data for factual claims. If a requested metric is not present, say it is not available rather than inventing it. Distinguish current application data from recommendations. Do not reveal secrets, credentials, tokens, passwords, private keys, or encrypted values. For data-changing actions, propose the action and require explicit administrator confirmation; do not claim that an action was executed. For deployment, infrastructure capacity, or external job status, state that this application snapshot does not provide that telemetry. Give a concise operational summary with: overall status, active issues/alerts supported by the data, affected components, recent changes/events, security concerns, and safe next steps.

SANITIZED CONTROL CENTER SNAPSHOT:
""" + json.dumps(context, default=str)
 user_prompt=prompt or "Summarize the current administration dashboard and identify safe operational next actions."
 try:
  out=openai_admin(system_prompt + "\n\nADMIN REQUEST:\n" + user_prompt)
 except Exception as e:
  audit(database,str(u["_id"]),"ADMIN_AI_FAILED",meta={"promptLength":len(user_prompt),"errorType":type(e).__name__})
  return jsonify(error="Admin AI is not configured or is temporarily unavailable"),503
 audit(database,str(u["_id"]),"ADMIN_AI",meta={"promptLength":len(user_prompt),"contextGenerated":True})
 return jsonify(message=out,context=context)
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

@app.get("/api/client/profile")
def client_profile():
 u=auth()
 if not u:return jsonify(error="Unauthorized"),401
 b=db().businesses.find_one({"ownerId":u["_id"]})
 if not b:return jsonify(profile={"email":u["email"],"emailVerified":bool(u.get("emailVerified"))})
 sub=db().subscriptions.find_one({"businessId":b["_id"]})
 return jsonify(profile={"id":str(u["_id"]),"email":u["email"],"emailVerified":bool(u.get("emailVerified")),"businessName":b.get("businessName"),"status":b.get("status","PENDING"),"subscription":sub and {"plan":sub.get("plan"),"status":sub.get("status"),"endsAt":sub.get("endsAt")}})

@app.get("/api/client/activity")
def client_activity():
 u=auth()
 if not u:return jsonify(error="Unauthorized"),401
 rows=[]
 for x in db().audit_logs.find({"actor":str(u["_id"])}, {"action":1,"target":1,"meta":1,"createdAt":1}).sort("createdAt",-1).limit(100):
  rows.append({"action":x.get("action"),"target":x.get("target",""),"meta":x.get("meta",{}),"createdAt":x.get("createdAt").isoformat() if x.get("createdAt") else None})
 return jsonify(activity=rows)

@app.get("/api/client/whatsapp")
def client_whatsapp():
 u=auth()
 if not u:return jsonify(error="Unauthorized"),401
 b=db().businesses.find_one({"ownerId":u["_id"]})
 if not b:return jsonify(connected=False)
 x=db().whatsapp_integrations.find_one({"businessId":b["_id"],"active":True})
 return jsonify(connected=bool(x),wabaId=x.get("wabaId") if x else None,phoneNumberId=x.get("phoneNumberId") if x else None,webhookVerified=bool(x.get("webhookVerified")) if x else False,automationEnabled=bool(x.get("automationEnabled")) if x else False)

@app.post("/api/client/whatsapp")
def save_client_whatsapp():
 u=auth()
 if not u:return jsonify(error="Unauthorized"),401
 d=request.get_json() or {};b=db().businesses.find_one({"ownerId":u["_id"]})
 if not b:return jsonify(error="Business not found"),404
 token=d.get("accessToken","").strip();phone=d.get("phoneNumberId","").strip();waba=d.get("wabaId","").strip()
 if not token or not phone:return jsonify(error="Phone Number ID and access token are required"),400
 db().whatsapp_integrations.update_one({"businessId":b["_id"]},{"$set":{"businessId":b["_id"],"wabaId":waba,"phoneNumberId":phone,"accessToken":encrypt_secret(token),"active":True,"automationEnabled":bool(d.get("automationEnabled",True)),"webhookVerified":False,"updatedAt":datetime.now(timezone.utc)}},upsert=True)
 audit(db(),str(u["_id"]),"WHATSAPP_CONNECTED",str(b["_id"]),{"phoneNumberId":phone})
 return jsonify(message="WhatsApp connection saved securely",connected=True)

@app.post("/api/client/whatsapp/automation")
def client_whatsapp_automation():
 u=auth()
 if not u:return jsonify(error="Unauthorized"),401
 b=db().businesses.find_one({"ownerId":u["_id"]});d=request.get_json() or {}
 if not b:return jsonify(error="Business not found"),404
 enabled=bool(d.get("enabled",True));r=db().whatsapp_integrations.update_one({"businessId":b["_id"]},{"$set":{"automationEnabled":enabled,"updatedAt":datetime.now(timezone.utc)}})
 if not r.matched_count:return jsonify(error="WhatsApp is not connected"),404
 audit(db(),str(u["_id"]),"WHATSAPP_AUTOMATION_ENABLED" if enabled else "WHATSAPP_AUTOMATION_DISABLED",str(b["_id"]));return jsonify(enabled=enabled)

@app.post("/api/client/ai")
def client_ai_config():
 u=auth()
 if not u:return jsonify(error="Unauthorized"),401
 d=request.get_json() or {};b=db().businesses.find_one({"ownerId":u["_id"]});key=d.get("apiKey","").strip()
 if not b:return jsonify(error="Business not found"),404
 if not key:return jsonify(error="API key is required"),400
 db().ai_credentials.update_one({"businessId":b["_id"]},{"$set":{"businessId":b["_id"],"encryptedKey":encrypt_secret(key),"model":d.get("model","gpt-5.6-luna"),"systemInstructions":d.get("systemInstructions","")[:4000],"responseTone":d.get("responseTone","Professional"),"responseLength":d.get("responseLength","Balanced"),"active":bool(d.get("enabled",True)),"updatedAt":datetime.now(timezone.utc)}},upsert=True)
 audit(db(),str(u["_id"]),"AI_CREDENTIAL_UPDATED",str(b["_id"]),{"model":d.get("model","gpt-5.6-luna")})
 return jsonify(message="AI configuration saved securely",enabled=bool(d.get("enabled",True)))

@app.get("/api/client/ai")
def client_ai_status():
 u=auth()
 if not u:return jsonify(error="Unauthorized"),401
 b=db().businesses.find_one({"ownerId":u["_id"]});x=db().ai_credentials.find_one({"businessId":b["_id"]}) if b else None
 return jsonify(configured=bool(x),enabled=bool(x and x.get("active")),model=x.get("model") if x else None,responseTone=x.get("responseTone") if x else None,responseLength=x.get("responseLength") if x else None)

@app.get("/api/admin/audit")
def admin_audit():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 rows=[]
 for x in db().audit_logs.find().sort("createdAt",-1).limit(250):
  rows.append({"id":str(x["_id"]),"actor":x.get("actor"),"action":x.get("action"),"target":x.get("target",""),"meta":x.get("meta",{}),"createdAt":x.get("createdAt").isoformat() if x.get("createdAt") else None})
 return jsonify(logs=rows)

@app.post("/api/admin/client/role")
def admin_client_role():
 u=admin()
 if not u:return jsonify(error="Unauthorized"),403
 d=request.get_json() or {};uid=oid(d.get("userId"));role=str(d.get("role","CLIENT_OWNER")).upper()
 if role not in {"ADMIN","CLIENT_OWNER"}:return jsonify(error="Unsupported role"),400
 if uid==u["_id"] and role!="ADMIN":return jsonify(error="You cannot demote the current administrator"),400
 target=db().users.find_one({"_id":uid})
 if not target:return jsonify(error="User not found"),404
 db().users.update_one({"_id":uid},{"$set":{"role":role,"updatedAt":datetime.now(timezone.utc)}});audit(db(),str(u["_id"]),"ADMIN_ROLE_CHANGED",str(uid),{"role":role});return jsonify(message="Role updated",role=role)

@app.get("/api/webhooks/whatsapp")
def wa_verify():
 if request.args.get("hub.mode")=="subscribe" and request.args.get("hub.verify_token")==app.config["WHATSAPP_VERIFY_TOKEN"]:return request.args.get("hub.challenge","")
 return "Forbidden",403
@app.post("/api/webhooks/whatsapp")
def wa_webhook():
 payload=request.get_json(silent=True) or {}
 db().whatsapp_messages.insert_one({"payload":payload,"receivedAt":datetime.now(timezone.utc)})
 return jsonify(received=True)

@app.post("/api/webhooks/daraja")
def daraja_callback():
 payload=request.get_json(silent=True) or {};db().daraja_callbacks.insert_one({"payload":payload,"createdAt":datetime.now(timezone.utc)});return jsonify(ResultCode=0,ResultDesc="Accepted")
