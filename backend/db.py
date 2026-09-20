import os
from pymongo import MongoClient
_client=None
def db():
 global _client
 if _client is None:_client=MongoClient(os.environ["MONGODB_URI"],serverSelectionTimeoutMS=10000)
 return _client[os.environ.get("DATABASE_NAME","whatsapp_saas")]
def init_indexes():
 d=db()
 d.users.create_index("email",unique=True)
 d.businesses.create_index("ownerId")
 d.documents.create_index([("businessId",1),("createdAt",-1)])
 d.audit_logs.create_index([("createdAt",-1)])
 d.verification_tokens.create_index("userId")
 d.settings.create_index("key",unique=True)
 # Touch the database so it appears in MongoDB Atlas even before a user registers.
 if "settings" not in d.list_collection_names():
  d.settings.insert_one({"key":"registration_enabled","value":True})
