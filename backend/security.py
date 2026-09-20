import base64,os,jwt,bcrypt
from datetime import datetime,timedelta,timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app,request
def hash_password(p): return bcrypt.hashpw(p.encode(),bcrypt.gensalt()).decode()
def verify_password(p,h):
 try:return bcrypt.checkpw(p.encode(),h.encode())
 except:return False
def token_for(u): return jwt.encode({"sub":str(u["_id"]),"role":u["role"],"email":u["email"],"exp":datetime.now(timezone.utc)+timedelta(hours=12)},current_app.config["SESSION_SECRET"],algorithm="HS256")
def read_token():
 t=request.cookies.get(current_app.config["COOKIE_NAME"])
 if not t:return None
 try:return jwt.decode(t,current_app.config["SESSION_SECRET"],algorithms=["HS256"])
 except:return None
def encrypt_secret(v):
 key=base64.urlsafe_b64decode(current_app.config["ENCRYPTION_KEY"]); n=os.urandom(12); c=AESGCM(key).encrypt(n,v.encode(),None); return base64.urlsafe_b64encode(n+c).decode()
def decrypt_secret(v):
 key=base64.urlsafe_b64decode(current_app.config["ENCRYPTION_KEY"]); r=base64.urlsafe_b64decode(v.encode()); return AESGCM(key).decrypt(r[:12],r[12:],None).decode()

# Project integration marker: complete admin-role + registration build
