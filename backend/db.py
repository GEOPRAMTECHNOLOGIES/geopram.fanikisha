from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid
from flask import current_app

_client = None

COLLECTIONS = [
    "users",
    "businesses",
    "documents",
    "audit_logs",
    "ai_credentials",
    "verification_tokens",
    "subscriptions",
    "daraja_callbacks",
    "settings",
]

def db():
    global _client
    if _client is None:
        _client = MongoClient(
            current_app.config["MONGODB_URI"],
            serverSelectionTimeoutMS=5000,
        )
    return _client[current_app.config["DATABASE_NAME"]]

def init_indexes():
    d = db()
    # Explicitly create the application collections so MongoDB Atlas shows
    # the configured database immediately after the first deployment.
    existing = set(d.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            try:
                d.create_collection(name)
            except CollectionInvalid:
                pass

    d.users.create_index([("email", ASCENDING)], unique=True)
    d.businesses.create_index([("ownerId", ASCENDING)])
    d.documents.create_index([("businessId", ASCENDING), ("createdAt", DESCENDING)])
    d.audit_logs.create_index([("createdAt", DESCENDING)])
    d.verification_tokens.create_index("userId")
    d.settings.create_index("key", unique=True)
    if d.settings.find_one({"key":"registration_enabled"}) is None:
        d.settings.insert_one({"key":"registration_enabled","value":True})

# Project integration marker: complete admin-role + registration build
