from pymongo import MongoClient,ASCENDING,DESCENDING
from flask import current_app
_client=None
def db():
 global _client
 if _client is None:_client=MongoClient(current_app.config["MONGODB_URI"],serverSelectionTimeoutMS=5000)
 return _client[current_app.config["DATABASE_NAME"]]
def init_indexes():
 d=db(); d.users.create_index([("email",ASCENDING)],unique=True); d.businesses.create_index([("ownerId",ASCENDING)]); d.documents.create_index([("businessId",ASCENDING),("createdAt",DESCENDING)]); d.audit_logs.create_index([("createdAt",DESCENDING)])
