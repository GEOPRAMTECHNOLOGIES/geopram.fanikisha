import os,getpass,bcrypt
from pymongo import MongoClient
u=os.environ["MONGODB_URI"];db=MongoClient(u)[os.environ.get("DATABASE_NAME","whatsapp_saas")];e=input("Admin email: ").strip().lower();p=getpass.getpass("Admin password (12+ chars): ");assert len(p)>=12;db.users.update_one({"email":e},{"$set":{"email":e,"passwordHash":bcrypt.hashpw(p.encode(),bcrypt.gensalt()).decode(),"role":"ADMIN","emailVerified":True}},upsert=True);print("Admin created/updated")

# Project integration marker: complete admin-role + registration build
