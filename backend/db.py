import os
from pymongo import MongoClient
_client=None

def db():
    global _client
    if _client is None:
        _client=MongoClient(os.environ["MONGODB_URI"],serverSelectionTimeoutMS=10000)
    return _client[os.environ.get("DATABASE_NAME","whatsapp_saas")]

def init_indexes():
    d=db()
    d.users.create_index("email",unique=True)
    for name in ["businesses","customers","messages","payments","subscriptions","documents","invoices","receipts","ai_credentials","whatsapp_integrations","ai_usage"]:
        d[name].create_index([("businessId",1),("createdAt",-1)])
    d.audit_logs.create_index([("createdAt",-1)])
    d.audit_logs.create_index([("actor",1),("createdAt",-1)])
    d.verification_tokens.create_index("userId")
    d.verification_tokens.create_index("expiresAt",expireAfterSeconds=0)
    d.settings.create_index("key",unique=True)
    d.plans.create_index("active")
    d.messages.create_index([("businessId",1),("createdAt",-1)])
    d.customers.create_index([("businessId",1),("phone",1)])
    if "settings" not in d.list_collection_names():
        d.settings.insert_one({"key":"registration_enabled","value":True})
    if d.plans.count_documents({}) == 0:
        d.plans.insert_many([
            {"name":"Basic","amount":1500,"currency":"KES","days":30,"features":["1 WhatsApp number","CRM","Basic automation"],"active":True},
            {"name":"Standard","amount":3500,"currency":"KES","days":30,"features":["WhatsApp automation","AI replies","Reports"],"active":True},
            {"name":"Pro","amount":7000,"currency":"KES","days":30,"features":["Advanced automation","AI","M-Pesa","Priority workflows"],"active":True},
        ])
