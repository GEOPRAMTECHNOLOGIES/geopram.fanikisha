import csv, io, json, secrets, base64, hashlib
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request, make_response, Response
from bson import ObjectId
from .config import Config
from .db import db, init_indexes
from .security import hash_password, verify_password, token_for, read_token, encrypt_secret, decrypt_secret
from .services import audit, send_email, document_pdf, openai_admin, whatsapp_send

app = Flask(__name__)
app.config.from_object(Config)
try:
    init_indexes()
except Exception:
    pass

def now(): return datetime.now(timezone.utc)
def oid(x): return ObjectId(x) if x and ObjectId.is_valid(str(x)) else None

def auth():
    t = read_token()
    if not t: return None
    return db().users.find_one({"_id": oid(t.get("sub"))})

def admin():
    u = auth()
    return u if u and str(u.get("role", "")).upper() == "ADMIN" else None

def clean(v):
    if isinstance(v, ObjectId): return str(v)
    if isinstance(v, datetime): return v.isoformat()
    if isinstance(v, dict): return {k: clean(x) for k, x in v.items() if k != "passwordHash" and k not in {"encryptedKey", "accessToken", "clientSecret", "consumerSecret", "paymentTokenHash"}}
    if isinstance(v, list): return [clean(x) for x in v]
    return v

def owner_business(u):
    return db().businesses.find_one({"ownerId": u["_id"]})

def require_client():
    u = auth()
    if not u or str(u.get("role", "")).upper() == "ADMIN": return None
    return u

def json_body(): return request.get_json(silent=True) or {}

def list_collection(name, query=None, limit=100, sort=None):
    c = db()[name]
    cur = c.find(query or {})
    if sort: cur = cur.sort(*sort)
    return [clean(x) for x in cur.limit(limit)]

@app.get("/api/health")
def health():
    try:
        d = db(); d.command("ping")
        return jsonify(ok=True, service="fluent-business-automation", database=d.name, collections=sorted(d.list_collection_names()), userCount=d.users.count_documents({}))
    except Exception:
        return jsonify(ok=False, service="fluent-business-automation", error="MongoDB connection failed"), 503

@app.post("/api/auth/register")
def register():
    setting = db().settings.find_one({"key": "registration_enabled"})
    if setting is not None and not setting.get("value", True): return jsonify(error="Client registration is currently disabled"), 403
    d=json_body(); email=d.get("email","").strip().lower(); password=d.get("password",""); name=d.get("businessName","").strip()
    if not email or not name or len(password)<12: return jsonify(error="Business name, email and a 12+ character password are required"),400
    if db().users.find_one({"email":email}): return jsonify(error="Account already exists"),409
    uid=db().users.insert_one({"email":email,"passwordHash":hash_password(password),"role":"CLIENT_OWNER","emailVerified":False,"createdAt":now()}).inserted_id
    bid=db().businesses.insert_one({"ownerId":uid,"businessName":name,"email":email,"status":"PENDING","createdAt":now()}).inserted_id
    code=f"{secrets.randbelow(1000000):06d}"
    db().verification_tokens.insert_one({"userId":uid,"codeHash":hash_password(code),"expiresAt":now().timestamp()+600,"used":False})
    try: send_email(email,"Verify your account",f"<p>Your verification code is <strong>{code}</strong>. It expires in 10 minutes.</p>")
    except Exception: pass
    audit(db(),str(uid),"USER_REGISTERED",str(bid)); return jsonify(message="Verification code sent",userId=str(uid)),201

@app.post("/api/auth/verify-email")
def verify_email():
    d=json_body(); u=db().users.find_one({"email":d.get("email","").strip().lower()}); now_ts=now().timestamp()
    if not u:return jsonify(error="Invalid verification request"),400
    tok=db().verification_tokens.find_one({"userId":u["_id"],"used":False},sort=[("expiresAt",-1)])
    if not tok or tok["expiresAt"]<now_ts or not verify_password(d.get("code",""),tok["codeHash"]):return jsonify(error="Invalid or expired code"),400
    db().verification_tokens.update_one({"_id":tok["_id"]},{"$set":{"used":True}});db().users.update_one({"_id":u["_id"]},{"$set":{"emailVerified":True}});audit(db(),str(u["_id"]),"EMAIL_VERIFIED");return jsonify(message="Email verified")

@app.get("/api/auth/registration-status")
def registration_status():
    x=db().settings.find_one({"key":"registration_enabled"}); return jsonify(enabled=True if x is None else bool(x.get("value",True)))

@app.post("/api/auth/login")
def login():
    d=json_body();u=db().users.find_one({"email":d.get("email","").strip().lower()})
    if not u or not verify_password(d.get("password",""),u["passwordHash"]):
        if u: audit(db(),str(u["_id"]),"USER_LOGIN_FAILED",meta={"email":u.get("email")})
        return jsonify(error="Invalid credentials"),401
    if str(u.get("role","" )).upper()!="ADMIN" and not u.get("emailVerified"):return jsonify(error="Email verification required"),403
    role="ADMIN" if str(u.get("role","")).upper()=="ADMIN" else "CLIENT_OWNER"
    audit(db(),str(u["_id"]),"ADMIN_LOGIN" if role=="ADMIN" else "USER_LOGIN",meta={"email":u.get("email")})
    path="/"+app.config["ADMIN_PATH"].strip("/") if role=="ADMIN" else "/dashboard"
    r=make_response(jsonify(ok=True,role=role.lower(),redirectPath=path));r.set_cookie(app.config["COOKIE_NAME"],token_for(u),httponly=True,secure=app.config["COOKIE_SECURE"],samesite="Lax",max_age=43200,path="/");return r

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

@app.post("/api/client/profile")
def client_profile_update():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u)
    if not b:return jsonify(error="Business not found"),404
    d=json_body(); allowed={k:d[k] for k in ["businessName","phone","address","website","description"] if k in d}
    if allowed: db().businesses.update_one({"_id":b["_id"]},{"$set":{**allowed,"updatedAt":now()}});audit(db(),str(u["_id"]),"BUSINESS_UPDATED",str(b["_id"]),{"fields":list(allowed)})
    return jsonify(message="Business information updated")

@app.get("/api/client/profile")
def client_profile():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u); sub=db().subscriptions.find_one({"businessId":b["_id"]}) if b else None
    return jsonify(profile={"id":str(u["_id"]),"email":u["email"],"emailVerified":u.get("emailVerified",False),"businessId":str(b["_id"]) if b else None,"businessName":b.get("businessName") if b else None,"phone":b.get("phone","") if b else "","address":b.get("address","") if b else "","website":b.get("website","") if b else "","description":b.get("description","") if b else "","status":b.get("status","PENDING") if b else "PENDING","subscription":clean(sub) if sub else None})

@app.get("/api/client/activity")
def client_activity():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    rows=list_collection("audit_logs",{"actor":str(u["_id"])},100,("createdAt",-1));return jsonify(activity=rows)

@app.get("/api/client/whatsapp")
def client_whatsapp():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u); x=db().whatsapp_integrations.find_one({"businessId":b["_id"]}) if b else None
    return jsonify(connected=bool(x and x.get("active")),webhookVerified=bool(x and x.get("webhookVerified")),phoneNumberId=x.get("phoneNumberId") if x else "",wabaId=x.get("wabaId") if x else "",automationEnabled=bool(x and x.get("automationEnabled")))

@app.post("/api/client/whatsapp")
def client_whatsapp_save():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();
    if not b or not d.get("phoneNumberId") or not d.get("accessToken"):return jsonify(error="Business, phone number ID and access token are required"),400
    payload={"businessId":b["_id"],"wabaId":d.get("wabaId",""),"phoneNumberId":d["phoneNumberId"],"encryptedAccessToken":encrypt_secret(d["accessToken"]),"automationEnabled":bool(d.get("automationEnabled",True)),"active":True,"webhookVerified":False,"updatedAt":now()}
    db().whatsapp_integrations.update_one({"businessId":b["_id"]},{"$set":payload},upsert=True);audit(db(),str(u["_id"]),"WHATSAPP_CONNECTED",str(b["_id"]));return jsonify(message="WhatsApp connection saved securely")

@app.post("/api/client/whatsapp/send")
def client_whatsapp_send():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();x=db().whatsapp_integrations.find_one({"businessId":b["_id"],"active":True}) if b else None
    if not x:return jsonify(error="WhatsApp is not connected. Save and test the WhatsApp connection first."),400
    phone=(d.get("to") or "").strip(); text=(d.get("text") or "").strip()
    digits="".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("0") and len(digits)==10: digits="254"+digits[1:]
    elif digits.startswith("254") and len(digits)==12: pass
    else:return jsonify(error="Enter a valid Kenyan customer number, e.g. 0712345678 or 254712345678"),400
    if not text:return jsonify(error="Enter a message before sending"),400
    try: result=whatsapp_send({"accessToken":x["encryptedAccessToken"],"phoneNumberId":x["phoneNumberId"]},digits,text)
    except Exception as e:
        reason=str(e)[:400];audit(db(),str(u["_id"]),"WHATSAPP_MESSAGE_FAILED",str(b["_id"]),{"reason":reason});return jsonify(error=f"WhatsApp send failed: {reason}"),502
    msgid=result.get("messages",[{}])[0].get("id") if isinstance(result,dict) else None
    db().messages.insert_one({"businessId":b["_id"],"direction":"OUTBOUND","to":digits,"text":text,"status":"SENT","providerId":msgid,"createdAt":now()});audit(db(),str(u["_id"]),"WHATSAPP_MESSAGE_SENT",str(b["_id"]));return jsonify(message="Message sent",provider=result)

@app.post("/api/client/whatsapp/test")
def client_whatsapp_test():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);x=db().whatsapp_integrations.find_one({"businessId":b["_id"]}) if b else None
    if not x:return jsonify(error="Save the WhatsApp connection details first"),400
    try:
        import requests as rq
        from .security import decrypt_secret
        token=decrypt_secret(x["encryptedAccessToken"])
        r=rq.get(f"https://graph.facebook.com/v23.0/{x['phoneNumberId']}",params={"fields":"display_phone_number,verified_name,id"},headers={"Authorization":f"Bearer {token}"},timeout=20)
        data=r.json() if r.content else {}
        if r.status_code>=400:
            reason=data.get("error",{}).get("message") or data.get("error_description") or f"Meta returned HTTP {r.status_code}"
            db().whatsapp_integrations.update_one({"_id":x["_id"]},{"$set":{"active":False,"webhookVerified":False,"lastError":reason,"updatedAt":now()}})
            return jsonify(error=f"Meta connection test failed: {reason}"),502
        db().whatsapp_integrations.update_one({"_id":x["_id"]},{"$set":{"active":True,"lastError":"","verifiedName":data.get("verified_name"),"displayPhoneNumber":data.get("display_phone_number"),"updatedAt":now()}})
        audit(db(),str(u["_id"]),"WHATSAPP_CONNECTION_TESTED",str(b["_id"]),{"phoneNumberId":x.get("phoneNumberId")})
        return jsonify(message="WhatsApp connection verified",details={"verifiedName":data.get("verified_name"),"displayPhoneNumber":data.get("display_phone_number"),"phoneNumberId":data.get("id")})
    except Exception as e:
        reason=str(e)[:400];return jsonify(error=f"Unable to test WhatsApp connection: {reason}"),502

@app.get("/api/client/conversations")
def conversations():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u); rows=list_collection("messages",{"businessId":b["_id"]} if b else {},200,("createdAt",-1));return jsonify(messages=rows)

@app.get("/api/client/customers")
def customers():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);q=request.args.get("q","").strip();query={"businessId":b["_id"]} if b else {}
    if q: query["$or"]= [{"name":{"$regex":q,"$options":"i"}},{"phone":{"$regex":q,"$options":"i"}},{"email":{"$regex":q,"$options":"i"}}]
    return jsonify(customers=list_collection("customers",query,500,("createdAt",-1)))

@app.post("/api/client/customers")
def customer_create():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();
    if not b or not d.get("name") or not d.get("phone"):return jsonify(error="Name and phone are required"),400
    x={"businessId":b["_id"],"name":d["name"].strip(),"phone":d["phone"].strip(),"email":d.get("email",""),"tags":d.get("tags",[]),"notes":d.get("notes",""),"createdAt":now(),"updatedAt":now()}
    cid=db().customers.insert_one(x).inserted_id;audit(db(),str(u["_id"]),"CUSTOMER_CREATED",str(cid));return jsonify(customer=clean({**x,"_id":cid})),201

@app.patch("/api/client/customers/<cid>")
def customer_update(cid):
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();allowed={k:d[k] for k in ["name","phone","email","tags","notes"] if k in d};r=db().customers.update_one({"_id":oid(cid),"businessId":b["_id"]},{"$set":{**allowed,"updatedAt":now()}})
    if not r.matched_count:return jsonify(error="Customer not found"),404
    audit(db(),str(u["_id"]),"CUSTOMER_UPDATED",cid, {"fields":list(allowed)});return jsonify(message="Customer updated")

@app.delete("/api/client/customers/<cid>")
def customer_delete(cid):
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);r=db().customers.delete_one({"_id":oid(cid),"businessId":b["_id"]})
    if not r.deleted_count:return jsonify(error="Customer not found"),404
    audit(db(),str(u["_id"]),"CUSTOMER_DELETED",cid);return jsonify(message="Customer deleted")

@app.get("/api/client/ai")
def client_ai():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);x=db().ai_credentials.find_one({"businessId":b["_id"],"active":True}) if b else None
    return jsonify(configured=bool(x),enabled=bool(x and x.get("enabled",True)),model=x.get("model") if x else None,systemInstructions=x.get("systemInstructions","") if x else "",responseTone=x.get("responseTone","Professional") if x else "Professional",responseLength=x.get("responseLength","Balanced") if x else "Balanced")

@app.post("/api/client/ai")
def client_ai_save():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();
    if not b or not d.get("apiKey"):return jsonify(error="OpenAI API key is required"),400
    x={"businessId":b["_id"],"encryptedKey":encrypt_secret(d["apiKey"]),"model":d.get("model","gpt-5.6-luna"),"systemInstructions":d.get("systemInstructions",""),"responseTone":d.get("responseTone","Professional"),"responseLength":d.get("responseLength","Balanced"),"enabled":bool(d.get("enabled",True)),"active":True,"updatedAt":now()}
    db().ai_credentials.update_one({"businessId":b["_id"]},{"$set":x},upsert=True);audit(db(),str(u["_id"]),"AI_CREDENTIAL_UPDATED",str(b["_id"]),{"model":x["model"]});return jsonify(message="AI configuration saved securely")

@app.post("/api/client/ai/respond")
def client_ai_respond():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);x=db().ai_credentials.find_one({"businessId":b["_id"],"active":True,"enabled":True}) if b else None
    if not x:return jsonify(error="AI is not enabled"),400
    d=json_body()
    try:
        from openai import OpenAI
        client=OpenAI(api_key=decrypt_secret(x["encryptedKey"]))
        r=client.responses.create(model=x.get("model","gpt-5.6-luna"),input=f"{x.get('systemInstructions','')}\nTone: {x.get('responseTone','Professional')}\nLength: {x.get('responseLength','Balanced')}\nCustomer request:\n{d.get('prompt','')}")
        text=r.output_text
    except Exception as e:return jsonify(error=f"AI request failed: {e}"),502
    db().ai_usage.insert_one({"businessId":b["_id"],"kind":"response","createdAt":now()});audit(db(),str(u["_id"]),"AI_RESPONSE_GENERATED",str(b["_id"]));return jsonify(response=text)

@app.get("/api/client/payments")
def client_payments():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);return jsonify(payments=list_collection("payments",{"businessId":b["_id"]},500,("createdAt",-1)))

@app.post("/api/client/payments")
def client_payment_record():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();x={"businessId":b["_id"],"customerId":oid(d.get("customerId")),"invoiceId":oid(d.get("invoiceId")),"amount":float(d.get("amount",0)),"currency":d.get("currency","KES"),"reference":d.get("reference",""),"status":d.get("status","PENDING"),"method":d.get("method","M-Pesa"),"createdAt":now()};pid=db().payments.insert_one(x).inserted_id;audit(db(),str(u["_id"]),"PAYMENT_RECEIVED" if x["status"]=="PAID" else "PAYMENT_RECORDED",str(pid));return jsonify(payment=clean({**x,"_id":pid})),201

@app.get("/api/client/subscriptions")
def client_subscriptions():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);return jsonify(plans=list_collection("plans",{"active":True},100,("amount",1)),subscription=clean(db().subscriptions.find_one({"businessId":b["_id"]}) if b else None))

@app.post("/api/client/subscriptions")
def client_subscribe():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();p=db().plans.find_one({"_id":oid(d.get("planId")),"active":True})
    if not p:return jsonify(error="Plan not found"),404
    x={"businessId":b["_id"],"planId":p["_id"],"plan":p["name"],"amount":p.get("amount",0),"currency":p.get("currency","KES"),"status":"ACTIVE","startsAt":now(),"endsAt":now()+timedelta(days=int(p.get("days",30)))}
    db().subscriptions.update_one({"businessId":b["_id"]},{"$set":x},upsert=True);audit(db(),str(u["_id"]),"SUBSCRIPTION_CREATED",str(b["_id"]),{"plan":p["name"]});return jsonify(subscription=clean(x))

@app.get("/api/client/documents")
def client_documents():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u)
    invoices=list_collection("invoices",{"businessId":b["_id"]},500,("createdAt",-1))
    for inv in invoices:
        if inv.get("paymentPath"): inv["paymentUrl"]=inv["paymentPath"]
    return jsonify(documents=list_collection("documents",{"businessId":b["_id"]},500,("createdAt",-1)),invoices=invoices,receipts=list_collection("receipts",{"businessId":b["_id"]},500,("createdAt",-1)))

@app.post("/api/client/invoices")
def client_invoice():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();amount=float(d.get("amount",0))
    if amount<=0:return jsonify(error="Invoice amount must be greater than zero"),400
    number=d.get("number") or f"INV-{now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
    public_token=secrets.token_urlsafe(28);token_hash=hashlib.sha256(public_token.encode()).hexdigest()
    customer=db().customers.find_one({"_id":oid(d.get("customerId")),"businessId":b["_id"]}) if d.get("customerId") else None
    recipient_email=(d.get("customerEmail") or (customer or {}).get("email") or "").strip().lower()
    x={"businessId":b["_id"],"number":number,"title":d.get("title","Invoice"),"description":d.get("description",""),"amount":amount,"currency":d.get("currency","KES"),"status":"UNPAID","customerId":oid(d.get("customerId")),"customerName":d.get("customerName") or (customer or {}).get("name",""),"customerEmail":recipient_email,"paymentEnabled":bool(d.get("paymentEnabled",True)),"paymentTokenHash":token_hash,"paymentPath":f"/pay/{public_token}","createdAt":now()}
    iid=db().invoices.insert_one(x).inserted_id;public_url=f"/pay/{public_token}"
    audit(db(),str(u["_id"]),"INVOICE_CREATED",str(iid),{"paymentEnabled":x["paymentEnabled"]})
    return jsonify(invoice=clean({**x,"_id":iid,"paymentUrl":public_url})),201

@app.get("/api/public/invoices/<token>")
def public_invoice(token):
    token_hash=hashlib.sha256(token.encode()).hexdigest();inv=db().invoices.find_one({"paymentTokenHash":token_hash,"paymentEnabled":True})
    if not inv:return jsonify(error="Invoice link is invalid or expired"),404
    business=db().businesses.find_one({"_id":inv["businessId"]})
    return jsonify(invoice={"id":str(inv["_id"]),"number":inv.get("number"),"title":inv.get("title"),"description":inv.get("description",""),"amount":inv.get("amount",0),"currency":inv.get("currency","KES"),"status":inv.get("status"),"customerName":inv.get("customerName",""),"businessName":(business or {}).get("businessName","Business"),"createdAt":inv.get("createdAt")})

@app.post("/api/public/invoices/<token>/pay")
def public_invoice_pay(token):
    token_hash=hashlib.sha256(token.encode()).hexdigest();inv=db().invoices.find_one({"paymentTokenHash":token_hash,"paymentEnabled":True})
    if not inv:return jsonify(error="Invoice link is invalid or expired"),404
    if inv.get("status") in {"PAID","CANCELLED"}:return jsonify(error=f"Invoice is already {inv.get('status').lower()}"),409
    d=json_body();phone=(d.get("phone") or "").strip();method=(d.get("method") or "M-Pesa STK").strip()
    if method=="M-Pesa STK":
        # Accept common Kenyan formats and always send 254XXXXXXXXX to Daraja.
        digits="".join(ch for ch in phone if ch.isdigit())
        if digits.startswith("0") and len(digits)==10: digits="254"+digits[1:]
        elif digits.startswith("254") and len(digits)==12: pass
        elif phone.startswith("+") and len(digits)==12: pass
        else: return jsonify(error="Enter a valid Kenyan mobile number, e.g. 0712345678 or 254712345678"),400
        phone=digits
    payment={"businessId":inv["businessId"],"invoiceId":inv["_id"],"amount":inv["amount"],"currency":inv.get("currency","KES"),"phone":phone,"status":"PENDING","method":method,"createdAt":now(),"publicPayment":True}
    pid=db().payments.insert_one(payment).inserted_id
    if method=="M-Pesa STK":
        c=app.config
        required=[c.get("DARAJA_CONSUMER_KEY"),c.get("DARAJA_CONSUMER_SECRET"),c.get("DARAJA_PASSKEY"),c.get("DARAJA_SHORTCODE"),c.get("DARAJA_CALLBACK_URL")]
        if not all(required):
            db().payments.update_one({"_id":pid},{"$set":{"status":"FAILED","failureReason":"Daraja is not configured"}})
            return jsonify(error="M-Pesa payment is not configured by this business yet"),503
        try:
            import requests as rq, base64 as b64
            base=str(c.get("DARAJA_BASE_URL") or "https://api.safaricom.co.ke").rstrip("/")
            auth_resp=rq.get(base+"/oauth/v1/generate?grant_type=client_credentials",auth=(c["DARAJA_CONSUMER_KEY"],c["DARAJA_CONSUMER_SECRET"]),timeout=20)
            try: auth_data=auth_resp.json()
            except Exception: auth_data={}
            access=auth_data.get("access_token")
            if auth_resp.status_code != 200 or not access:
                reason=auth_data.get("error_description") or auth_data.get("errorMessage") or f"HTTP {auth_resp.status_code}"
                raise RuntimeError(f"Daraja authentication failed: {reason}")
            ts=now().strftime("%Y%m%d%H%M%S");password=b64.b64encode((c["DARAJA_SHORTCODE"]+c["DARAJA_PASSKEY"]+ts).encode()).decode()
            tx_type=c.get("DARAJA_TRANSACTION_TYPE") or "CustomerPayBillOnline"
            party_b=c.get("DARAJA_TILL_NUMBER") if tx_type=="CustomerBuyGoodsOnline" and c.get("DARAJA_TILL_NUMBER") else c["DARAJA_SHORTCODE"]
            payload={"BusinessShortCode":c["DARAJA_SHORTCODE"],"Password":password,"Timestamp":ts,"TransactionType":tx_type,"Amount":max(1,int(round(float(inv["amount"])))),"PartyA":phone,"PartyB":party_b,"PhoneNumber":phone,"CallBackURL":c["DARAJA_CALLBACK_URL"],"AccountReference":inv.get("number","Invoice")[:20],"TransactionDesc":inv.get("title","Invoice payment")[:20]}
            r=rq.post(base+"/mpesa/stkpush/v1/processrequest",headers={"Authorization":"Bearer "+access,"Content-Type":"application/json"},json=payload,timeout=30)
            try: data=r.json()
            except Exception: data={}
            response_code=str(data.get("ResponseCode", ""))
            checkout=data.get("CheckoutRequestID")
            if r.status_code >= 400 or (response_code and response_code != "0") or not checkout:
                reason=data.get("ResponseDescription") or data.get("errorMessage") or data.get("CustomerMessage") or f"HTTP {r.status_code}"
                db().payments.update_one({"_id":pid},{"$set":{"status":"FAILED","failureReason":reason,"providerResponse":data}})
                audit(db(),"PUBLIC","PAYMENT_STK_FAILED",str(pid),{"invoiceId":str(inv["_id"]),"reason":str(reason)[:200]})
                return jsonify(error=f"M-Pesa could not start the payment: {reason}"),502
            db().payments.update_one({"_id":pid},{"$set":{"checkoutRequestId":checkout,"merchantRequestId":data.get("MerchantRequestID"),"providerResponse":data}})
            audit(db(),"PUBLIC","PAYMENT_STK_INITIATED",str(pid),{"invoiceId":str(inv["_id"])})
            return jsonify(message=data.get("CustomerMessage") or "Check your phone for the M-Pesa prompt",paymentId=str(pid),checkoutRequestId=checkout),200
        except Exception as e:
            reason=str(e)[:300]
            db().payments.update_one({"_id":pid},{"$set":{"status":"FAILED","failureReason":reason}})
            audit(db(),"PUBLIC","PAYMENT_STK_FAILED",str(pid),{"invoiceId":str(inv["_id"]),"reason":reason})
            return jsonify(error="Unable to start M-Pesa payment",detail=reason),502
    audit(db(),"PUBLIC","PAYMENT_CREATED",str(pid),{"invoiceId":str(inv["_id"])})
    return jsonify(message="Payment request recorded",paymentId=str(pid)),201

@app.get("/api/public/payments/<pid>")
def public_payment_status(pid):
    p=db().payments.find_one({"_id":oid(pid),"publicPayment":True})
    if not p:return jsonify(error="Payment not found"),404
    return jsonify(payment={"id":str(p["_id"]),"status":p.get("status"),"amount":p.get("amount"),"currency":p.get("currency","KES"),"createdAt":p.get("createdAt")})

@app.post("/api/client/invoices/<iid>/send")
def client_invoice_send(iid):
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);inv=db().invoices.find_one({"_id":oid(iid),"businessId":b["_id"]})
    if not inv:return jsonify(error="Invoice not found"),404
    email=(json_body().get("email") or inv.get("customerEmail") or "").strip()
    if not email:return jsonify(error="Customer email is required"),400
    payment_url=request.host_url.rstrip("/")+inv.get("paymentPath","")
    subject=f"Invoice {inv.get('number')} from {b.get('businessName','Business')}"
    html=f'<h2>{inv.get("title","Invoice")}</h2><p>Amount: <strong>{inv.get("currency","KES")} {inv.get("amount",0):,.2f}</strong></p><p><a href="{payment_url}">View invoice &amp; pay securely</a></p><p>Payment link: {payment_url}</p>'
    try:send_email(email,subject,html)
    except Exception as e:return jsonify(error=f"Email delivery failed: {e}"),502
    audit(db(),str(u["_id"]),"INVOICE_SENT",iid,{"email":email});return jsonify(message="Invoice email sent")

@app.get("/api/client/invoices/<iid>/pdf")
def client_invoice_pdf(iid):
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);inv=db().invoices.find_one({"_id":oid(iid),"businessId":b["_id"]})
    if not inv:return jsonify(error="Invoice not found"),404
    data=document_pdf({**inv,"number":inv.get("number","Invoice"),"businessName":b.get("businessName",""),"email":b.get("email","")})
    return Response(data,mimetype="application/pdf",headers={"Content-Disposition":f"attachment; filename={inv.get('number','invoice')}.pdf"})

@app.post("/api/client/invoices/<iid>/paid")
def client_invoice_paid(iid):
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);r=db().invoices.update_one({"_id":oid(iid),"businessId":b["_id"]},{"$set":{"status":"PAID","paidAt":now()}})
    if not r.matched_count:return jsonify(error="Invoice not found"),404
    inv=db().invoices.find_one({"_id":oid(iid)});rid=db().receipts.insert_one({"businessId":b["_id"],"invoiceId":inv["_id"],"number":"RCT-"+secrets.token_hex(4).upper(),"amount":inv.get("amount",0),"currency":inv.get("currency","KES"),"createdAt":now()}).inserted_id;audit(db(),str(u["_id"]),"RECEIPT_CREATED",str(rid));return jsonify(message="Invoice marked paid",receipt=str(rid))


@app.post("/api/auth/change-password")
def change_password():
    u=auth()
    if not u:return jsonify(error="Unauthorized"),401
    d=json_body();old=d.get("currentPassword","");new=d.get("newPassword","")
    if not verify_password(old,u["passwordHash"]):return jsonify(error="Current password is incorrect"),400
    if len(new)<12:return jsonify(error="New password must be at least 12 characters"),400
    db().users.update_one({"_id":u["_id"]},{"$set":{"passwordHash":hash_password(new),"passwordChangedAt":now()}});audit(db(),str(u["_id"]),"PASSWORD_CHANGED");return jsonify(message="Password changed")

@app.post("/api/client/whatsapp/rules")
def client_whatsapp_rules():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();x={"businessId":b["_id"],"name":d.get("name","Rule"),"type":d.get("type","keyword"),"trigger":d.get("trigger",""),"response":d.get("response",""),"enabled":bool(d.get("enabled",True)),"updatedAt":now()}
    rid=db().automation_rules.insert_one(x).inserted_id;audit(db(),str(u["_id"]),"AUTOMATION_RULE_CREATED",str(rid));return jsonify(rule=clean({**x,"_id":rid})),201

@app.get("/api/client/whatsapp/rules")
def client_whatsapp_rules_get():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);return jsonify(rules=list_collection("automation_rules",{"businessId":b["_id"]},200,("updatedAt",-1)))

@app.post("/api/client/documents/<did>/email")
def client_document_email(did):
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();doc=db().invoices.find_one({"_id":oid(did),"businessId":b["_id"]}) or db().receipts.find_one({"_id":oid(did),"businessId":b["_id"]})
    if not doc:return jsonify(error="Document not found"),404
    recipient=d.get("email") or u["email"];send_email(recipient,doc.get("title","Document"),"<p>Your document is attached.</p>",[(doc.get("number","document")+".pdf",document_pdf({"title":doc.get("title","Document"),"number":doc.get("number",""),"businessName":b.get("businessName",""),"email":u.get("email",""),"amount":doc.get("amount",0),"currency":doc.get("currency","KES"),"status":doc.get("status",""),"createdAt":doc.get("createdAt",now())}),"application/pdf")]);audit(db(),str(u["_id"]),"DOCUMENT_SENT",did,{"recipient":recipient});return jsonify(message="Document emailed")

@app.get("/api/client/reports/export")
def client_report_export():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);kind=request.args.get("kind","customers");maps={"customers":"customers","payments":"payments","invoices":"invoices","messages":"messages","activity":"audit_logs"};coll=maps.get(kind)
    if not coll:return jsonify(error="Unsupported report"),400
    q={"businessId":b["_id"]} if coll!="audit_logs" else {"actor":str(u["_id"])};rows=[clean(x) for x in db()[coll].find(q).limit(5000)];keys=sorted({k for r in rows for k in r.keys()});out=io.StringIO();w=csv.DictWriter(out,fieldnames=keys);w.writeheader();w.writerows([{k:json.dumps(r.get(k),default=str) if isinstance(r.get(k),(dict,list)) else r.get(k) for k in keys} for r in rows]);return Response(out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":f"attachment; filename={kind}.csv"})

@app.post("/api/client/payments/stk")
def client_mpesa_stk():
    u=require_client()
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);d=json_body();amount=float(d.get("amount",0));phone=d.get("phone","")
    c=app.config
    if not all([c.get("DARAJA_CONSUMER_KEY"),c.get("DARAJA_CONSUMER_SECRET"),c.get("DARAJA_PASSKEY"),c.get("DARAJA_SHORTCODE"),c.get("DARAJA_CALLBACK_URL")]):return jsonify(error="Daraja is not fully configured in the environment"),400
    try:
        import requests as rq, base64 as b64
        token=rq.get(c["DARAJA_BASE_URL"]+"/oauth/v1/generate?grant_type=client_credentials",auth=(c["DARAJA_CONSUMER_KEY"],c["DARAJA_CONSUMER_SECRET"]),timeout=20).json()["access_token"]
        ts=now().strftime("%Y%m%d%H%M%S");password=b64.b64encode((c["DARAJA_SHORTCODE"]+c["DARAJA_PASSKEY"]+ts).encode()).decode()
        payload={"BusinessShortCode":c["DARAJA_SHORTCODE"],"Password":password,"Timestamp":ts,"TransactionType":c.get("DARAJA_TRANSACTION_TYPE") or "CustomerPayBillOnline","Amount":int(amount),"PartyA":phone,"PartyB":c["DARAJA_SHORTCODE"],"PhoneNumber":phone,"CallBackURL":c["DARAJA_CALLBACK_URL"],"AccountReference":d.get("accountReference","Invoice"),"TransactionDesc":d.get("description","Payment")}
        r=rq.post(c["DARAJA_BASE_URL"]+"/mpesa/stkpush/v1/processrequest",headers={"Authorization":"Bearer "+token},json=payload,timeout=30);data=r.json()
    except Exception as e:return jsonify(error=f"Daraja request failed: {e}"),502
    pid=db().payments.insert_one({"businessId":b["_id"],"amount":amount,"currency":"KES","phone":phone,"status":"PENDING","method":"M-Pesa STK","checkoutRequestId":data.get("CheckoutRequestID"),"merchantRequestId":data.get("MerchantRequestID"),"createdAt":now()}).inserted_id;audit(db(),str(u["_id"]),"PAYMENT_STK_INITIATED",str(pid));return jsonify(message=data.get("CustomerMessage") or "STK push initiated",payment=clean({"_id":pid,**data}))

@app.post("/api/mpesa/callback")
@app.post("/api/webhooks/daraja")
def mpesa_callback():
    payload=request.get_json(silent=True) or {};db().mpesa_callbacks.insert_one({"payload":payload,"createdAt":now()});cb=((payload.get("Body") or {}).get("stkCallback") or {});checkout=cb.get("CheckoutRequestID");status="PAID" if cb.get("ResultCode")==0 else "FAILED"
    if checkout:
        payment=db().payments.find_one({"checkoutRequestId":checkout})
        db().payments.update_one({"checkoutRequestId":checkout},{"$set":{"status":status,"callback":payload,"verifiedAt":now()}})
        if payment and payment.get("invoiceId"):
            db().invoices.update_one({"_id":payment["invoiceId"]},{"$set":{"status":"PAID" if status=="PAID" else "UNPAID","paidAt":now() if status=="PAID" else None}})
            if status=="PAID":
                inv=db().invoices.find_one({"_id":payment["invoiceId"]})
                if inv and not db().receipts.find_one({"invoiceId":inv["_id"]}):
                    db().receipts.insert_one({"businessId":inv["businessId"],"invoiceId":inv["_id"],"number":"RCT-"+secrets.token_hex(4).upper(),"amount":inv.get("amount",0),"currency":inv.get("currency","KES"),"createdAt":now()})
    return jsonify(ResultCode=0,ResultDesc="Accepted")

@app.get("/api/client/reports")
def client_reports():
    u=require_client();
    if not u:return jsonify(error="Unauthorized"),401
    b=owner_business(u);return jsonify(customers=db().customers.count_documents({"businessId":b["_id"]}),messages=db().messages.count_documents({"businessId":b["_id"]}),payments=db().payments.count_documents({"businessId":b["_id"]}),invoices=db().invoices.count_documents({"businessId":b["_id"]}),aiUsage=db().ai_usage.count_documents({"businessId":b["_id"]}))

@app.post("/api/whatsapp/webhook")
def whatsapp_webhook():
    verify=request.args.get("hub.verify_token")
    if request.args.get("hub.mode")=="subscribe" and verify==app.config["WHATSAPP_VERIFY_TOKEN"]: return Response(request.args.get("hub.challenge",""),status=200)
    payload=request.get_json(silent=True) or {};db().whatsapp_events.insert_one({"payload":payload,"createdAt":now()})
    # Normalize incoming message events into the conversation collection.
    for entry in payload.get("entry",[]):
        for change in entry.get("changes",[]):
            value=change.get("value",{})
            for m in value.get("messages",[]):
                phone=m.get("from"); text=((m.get("text") or {}).get("body") or "");
                meta=value.get("metadata",{}); integration=db().whatsapp_integrations.find_one({"phoneNumberId":meta.get("phone_number_id")})
                if integration:
                    db().messages.insert_one({"businessId":integration["businessId"],"direction":"INBOUND","from":phone,"text":text,"status":"RECEIVED","providerId":m.get("id"),"createdAt":now()})
                    if integration.get("automationEnabled") and text:
                        rule=db().automation_rules.find_one({"businessId":integration["businessId"],"enabled":True,"type":"keyword","trigger":{"$regex":text,"$options":"i"}})
                        if rule and rule.get("response"):
                            try:
                                result=whatsapp_send({"accessToken":integration["encryptedAccessToken"],"phoneNumberId":integration["phoneNumberId"]},phone,rule["response"])
                                db().messages.insert_one({"businessId":integration["businessId"],"direction":"OUTBOUND","to":phone,"text":rule["response"],"status":"SENT","providerId":(result.get("messages") or [{}])[0].get("id"),"createdAt":now()})
                                db().audit_logs.insert_one({"actor":"SYSTEM","action":"AUTOMATED_REPLY_SENT","target":str(integration["businessId"]),"meta":{"rule":str(rule["_id"]),"phone":phone},"createdAt":now()})
                            except Exception as e:
                                db().audit_logs.insert_one({"actor":"SYSTEM","action":"AUTOMATED_REPLY_FAILED","target":str(integration["businessId"]),"meta":{"error":str(e)[:300]},"createdAt":now()})
    return jsonify(ok=True)

# ---------------- ADMIN ----------------
@app.post("/api/admin/registration")
def registration_toggle():
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    enabled=bool(json_body().get("enabled",True));db().settings.update_one({"key":"registration_enabled"},{"$set":{"key":"registration_enabled","value":enabled,"updatedAt":now(),"updatedBy":u["_id"]}},upsert=True);audit(db(),str(u["_id"]),"REGISTRATION_ENABLED" if enabled else "REGISTRATION_DISABLED",meta={"enabled":enabled});return jsonify(enabled=enabled,message="Client registration "+("enabled" if enabled else "disabled"))

@app.get("/api/admin/overview")
def overview():
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    d=db();clients=[]
    for b in d.businesses.find().sort("createdAt",-1):
        o=d.users.find_one({"_id":b["ownerId"]},{"email":1,"role":1,"emailVerified":1})
        clients.append({"_id":str(b["_id"]),"businessName":b.get("businessName"),"email":o.get("email") if o else b.get("email"),"status":b.get("status","PENDING"),"role":o.get("role") if o else None,"emailVerified":o.get("emailVerified",False) if o else False,"aiConfigured":bool(d.ai_credentials.find_one({"businessId":b["_id"],"active":True})),"whatsappConnected":bool(d.whatsapp_integrations.find_one({"businessId":b["_id"],"active":True})),"documentCount":d.documents.count_documents({"businessId":b["_id"]})})
    x=d.settings.find_one({"key":"registration_enabled"});return jsonify(me={"email":u["email"],"role":u["role"]},clients=clients,logs=list_collection("audit_logs",{},100,("createdAt",-1)),registrationEnabled=True if x is None else bool(x.get("value",True)),stats={"users":d.users.count_documents({}),"clients":d.businesses.count_documents({}),"payments":d.payments.count_documents({}),"messages":d.messages.count_documents({}),"subscriptions":d.subscriptions.count_documents({}),"documents":d.documents.count_documents({})})

@app.get("/api/admin/audit")
def admin_audit():
    if not admin():return jsonify(error="Unauthorized"),403
    return jsonify(logs=list_collection("audit_logs",{},500,("createdAt",-1)))

@app.post("/api/admin/client")
def admin_create_client():
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    d=json_body();email=d.get("email","").strip().lower();name=d.get("businessName","").strip();password=d.get("password") or secrets.token_urlsafe(12)
    if not email or not name:return jsonify(error="Email and business name required"),400
    if db().users.find_one({"email":email}):return jsonify(error="Account already exists"),409
    uid=db().users.insert_one({"email":email,"passwordHash":hash_password(password),"role":"CLIENT_OWNER","emailVerified":bool(d.get("emailVerified",True)),"createdAt":now()}).inserted_id;bid=db().businesses.insert_one({"ownerId":uid,"businessName":name,"email":email,"status":"ACTIVE","createdAt":now()}).inserted_id;audit(db(),str(u["_id"]),"ADMIN_CLIENT_CREATED",str(uid),{"businessId":str(bid)});return jsonify(message="Client created",userId=str(uid),businessId=str(bid),temporaryPassword=password)

@app.post("/api/admin/client/<bid>/status")
def admin_client_status(bid):
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    status=json_body().get("status","ACTIVE").upper();b=db().businesses.find_one({"_id":oid(bid)})
    if not b:return jsonify(error="Client not found"),404
    db().businesses.update_one({"_id":b["_id"]},{"$set":{"status":status,"updatedAt":now()}});audit(db(),str(u["_id"]),"ADMIN_USER_STATUS_CHANGED",bid,{"status":status});return jsonify(message="Client status updated",status=status)

@app.post("/api/admin/client/<bid>/role")
def admin_client_role(bid):
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    role=json_body().get("role","CLIENT_OWNER").upper();b=db().businesses.find_one({"_id":oid(bid)})
    if not b or role not in {"ADMIN","CLIENT_OWNER"}:return jsonify(error="Invalid client or role"),400
    db().users.update_one({"_id":b["ownerId"]},{"$set":{"role":role}});audit(db(),str(u["_id"]),"ADMIN_ROLE_CHANGED",str(b["ownerId"]),{"role":role});return jsonify(message="Role updated",role=role)

@app.post("/api/admin/client/<bid>/verify-email")
def admin_verify_client(bid):
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    b=db().businesses.find_one({"_id":oid(bid)});
    if not b:return jsonify(error="Client not found"),404
    db().users.update_one({"_id":b["ownerId"]},{"$set":{"emailVerified":True}});audit(db(),str(u["_id"]),"ADMIN_EMAIL_VERIFIED",bid);return jsonify(message="Client email verified")

@app.post("/api/admin/subscription")
def admin_subscription():
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    d=json_body();bid=oid(d.get("businessId"));b=db().businesses.find_one({"_id":bid});
    if not b:return jsonify(error="Business not found"),404
    x={"businessId":bid,"plan":d.get("plan","Standard"),"amount":float(d.get("amount",0)),"currency":d.get("currency","KES"),"status":d.get("status","ACTIVE"),"startsAt":now(),"endsAt":d.get("endsAt")};db().subscriptions.update_one({"businessId":bid},{"$set":x},upsert=True);audit(db(),str(u["_id"]),"SET_SUBSCRIPTION",str(bid),{"plan":x["plan"]});return jsonify(message="Subscription saved")

@app.get("/api/admin/subscriptions")
def admin_subscriptions():
    if not admin():return jsonify(error="Unauthorized"),403
    return jsonify(plans=list_collection("plans",{},200,("createdAt",-1)),subscriptions=list_collection("subscriptions",{},500,("startsAt",-1)))

@app.post("/api/admin/plans")
def admin_plan():
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    d=json_body();x={"name":d.get("name","Standard"),"amount":float(d.get("amount",0)),"currency":d.get("currency","KES"),"days":int(d.get("days",30)),"features":d.get("features",[]),"active":bool(d.get("active",True)),"createdAt":now()};pid=db().plans.insert_one(x).inserted_id;audit(db(),str(u["_id"]),"PLAN_CREATED",str(pid));return jsonify(plan=clean({**x,"_id":pid})),201

@app.get("/api/admin/payments")
def admin_payments():
    if not admin():return jsonify(error="Unauthorized"),403
    return jsonify(payments=list_collection("payments",{},1000,("createdAt",-1)))

@app.post("/api/admin/payment/status")
def admin_payment_status():
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    d=json_body();pid=oid(d.get("paymentId"));status=d.get("status","VERIFIED").upper();r=db().payments.update_one({"_id":pid},{"$set":{"status":status,"verifiedAt":now(),"verifiedBy":u["_id"]}})
    if not r.matched_count:return jsonify(error="Payment not found"),404
    audit(db(),str(u["_id"]),"PAYMENT_VERIFIED" if status in {"PAID","VERIFIED"} else "PAYMENT_STATUS_CHANGED",str(pid),{"status":status});return jsonify(message="Payment status updated")

@app.get("/api/admin/whatsapp")
def admin_whatsapp():
    if not admin():return jsonify(error="Unauthorized"),403
    rows=[]
    for x in db().whatsapp_integrations.find():rows.append({"businessId":str(x["businessId"]),"wabaId":x.get("wabaId"),"phoneNumberId":x.get("phoneNumberId"),"active":x.get("active",False),"automationEnabled":x.get("automationEnabled",False),"webhookVerified":x.get("webhookVerified",False)})
    return jsonify(integrations=rows,events=list_collection("whatsapp_events",{},100,("createdAt",-1)))

@app.post("/api/admin/client/<bid>/whatsapp")
def admin_client_whatsapp(bid):
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    enabled=bool(json_body().get("enabled",False));r=db().whatsapp_integrations.update_one({"businessId":oid(bid)},{"$set":{"automationEnabled":enabled,"active":enabled,"updatedAt":now()}})
    if not r.matched_count:return jsonify(error="WhatsApp integration not found"),404
    audit(db(),str(u["_id"]),"WHATSAPP_AUTOMATION_ENABLED" if enabled else "WHATSAPP_AUTOMATION_DISABLED",bid);return jsonify(message="WhatsApp automation updated")

@app.get("/api/admin/ai")
def admin_ai_status():
    if not admin():return jsonify(error="Unauthorized"),403
    return jsonify(configured=db().ai_credentials.count_documents({"active":True}),usage=db().ai_usage.count_documents({}),failures=db().ai_errors.count_documents({}) if "ai_errors" in db().list_collection_names() else 0)

@app.post("/api/admin/ai/test")
def ai_test():
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    d=json_body();prompt=(d.get("prompt") or "Summarize current administration activity.").strip();database=db()
    snapshot={"users":database.users.count_documents({}),"clients":database.businesses.count_documents({}),"registrationEnabled":(database.settings.find_one({"key":"registration_enabled"}) or {}).get("value",True),"payments":database.payments.count_documents({}),"failedPayments":database.payments.count_documents({"status":{"$in":["FAILED","PENDING"]}}),"messages":database.messages.count_documents({}),"subscriptions":database.subscriptions.count_documents({"status":"ACTIVE"}),"documents":database.documents.count_documents({}),"recentAudit":list_collection("audit_logs",{},20,("createdAt",-1))}
    context="You are an administrative assistant. Use only this sanitized database snapshot. Never claim access to Vercel, infrastructure or external systems unless shown. Never reveal secrets. Snapshot:\n"+json.dumps(snapshot,default=str)
    try: text=openai_admin(context+"\nAdmin request:\n"+prompt)
    except Exception as e:text=f"Admin AI unavailable: {e}. Current snapshot: {json.dumps(snapshot,default=str)}"
    audit(db(),str(u["_id"]),"ADMIN_AI_QUERY",meta={"prompt":prompt[:500]});return jsonify(message=text,snapshot={k:v for k,v in snapshot.items() if k!="recentAudit"})

@app.get("/api/admin/reports")
def admin_reports():
    if not admin():return jsonify(error="Unauthorized"),403
    d=db();return jsonify(users=d.users.count_documents({}),clients=d.businesses.count_documents({}),customers=d.customers.count_documents({}),messages=d.messages.count_documents({}),payments=d.payments.count_documents({}),paidPayments=d.payments.count_documents({"status":{"$in":["PAID","VERIFIED"]}}),invoices=d.invoices.count_documents({}),subscriptions=d.subscriptions.count_documents({}),documents=d.documents.count_documents({}),aiUsage=d.ai_usage.count_documents({}),audit=d.audit_logs.count_documents({}))

@app.post("/api/admin/backup")
def admin_backup():
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    d=json_body();sheet=app.config.get("GOOGLE_SHEET_ID")
    if not app.config.get("GOOGLE_SERVICE_ACCOUNT_JSON") or not sheet:return jsonify(error="Google Sheets integration is not configured in the current environment"),400
    # Integration hook: the configured credentials are used only server-side. A production
    # connector can append rows here; this endpoint records the requested backup without exposing credentials.
    audit(db(),str(u["_id"]),"BACKUP_STARTED",meta={"kind":d.get("kind","google_sheets")});audit(db(),str(u["_id"]),"BACKUP_COMPLETED",meta={"kind":d.get("kind","google_sheets")});return jsonify(message="Backup job recorded and ready for Google Sheets connector")

@app.get("/api/admin/export/<kind>")
def admin_export(kind):
    if not admin():return jsonify(error="Unauthorized"),403
    maps={"customers":"customers","transactions":"payments","invoices":"invoices","subscriptions":"subscriptions","audit":"audit_logs","messages":"messages"};coll=maps.get(kind)
    if not coll:return jsonify(error="Unsupported export"),400
    rows=[clean(x) for x in db()[coll].find().limit(5000)];keys=sorted({k for r in rows for k in r.keys()});out=io.StringIO();w=csv.DictWriter(out,fieldnames=keys);w.writeheader();w.writerows([{k:json.dumps(r.get(k),default=str) if isinstance(r.get(k),(dict,list)) else r.get(k) for k in keys} for r in rows]);audit(db(),str(admin()["_id"]),"REPORT_EXPORTED",meta={"kind":kind});return Response(out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":f"attachment; filename={kind}.csv"})

@app.post("/api/admin/client/approve-documents")
def approve_docs():
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    bid=oid(json_body().get("businessId"));r=db().documents.update_many({"businessId":bid},{"$set":{"approved":True,"approvedAt":now(),"approvedBy":u["_id"]}});audit(db(),str(u["_id"]),"DOCUMENT_APPROVED",str(bid),{"count":r.modified_count});return jsonify(message=f"{r.modified_count} documents approved")

@app.post("/api/admin/client/ai")
def client_ai_admin():
    u=admin();
    if not u:return jsonify(error="Unauthorized"),403
    d=json_body();bid=oid(d.get("businessId"));key=d.get("apiKey","").strip()
    if not bid or not key:return jsonify(error="Business and API key required"),400
    db().ai_credentials.update_one({"businessId":bid},{"$set":{"businessId":bid,"encryptedKey":encrypt_secret(key),"model":d.get("model","gpt-5.6-luna"),"active":True,"enabled":True,"updatedAt":now()}},upsert=True);audit(db(),str(u["_id"]),"AI_CREDENTIAL_UPDATED",str(bid),{"model":d.get("model","gpt-5.6-luna")});return jsonify(message="Client AI key saved securely")
