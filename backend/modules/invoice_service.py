from datetime import datetime, timezone
import hashlib, secrets
def utcnow(): return datetime.now(timezone.utc)
def create_payment_token():
    token=secrets.token_urlsafe(28); return token, hashlib.sha256(token.encode()).hexdigest()
def public_path(token): return f"/pay/{token}"
