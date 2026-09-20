import os
class Config:
 ADMIN_PATH=os.environ.get("ADMIN_PATH","admin")
 MONGODB_URI=os.environ["MONGODB_URI"]; DATABASE_NAME=os.environ.get("DATABASE_NAME","whatsapp_saas")
 SESSION_SECRET=os.environ["SESSION_SECRET"]; ENCRYPTION_KEY=os.environ["ENCRYPTION_KEY"]; COOKIE_NAME=os.environ.get("COOKIE_NAME","fluent_session"); COOKIE_SECURE=os.environ.get("COOKIE_SECURE","true").lower()=="true"; COOKIE_DOMAIN=os.environ.get("COOKIE_DOMAIN") or None
 SMTP_HOST=os.environ.get("SMTP_HOST","smtp.gmail.com"); SMTP_PORT=int(os.environ.get("SMTP_PORT","587")); SMTP_USERNAME=os.environ.get("SMTP_USERNAME",""); SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD",""); SMTP_FROM=os.environ.get("SMTP_FROM","")
 OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY",""); OPENAI_ADMIN_MODEL=os.environ.get("OPENAI_ADMIN_MODEL","gpt-5.6-luna")
 REDIS_URL=os.environ.get("REDIS_URL","")
 DARAJA_ENV=os.environ.get("DARAJA_ENV","production"); DARAJA_BASE_URL=os.environ.get("DARAJA_BASE_URL","https://api.safaricom.co.ke"); DARAJA_CONSUMER_KEY=os.environ.get("DARAJA_CONSUMER_KEY",""); DARAJA_CONSUMER_SECRET=os.environ.get("DARAJA_CONSUMER_SECRET",""); DARAJA_PASSKEY=os.environ.get("DARAJA_PASSKEY",""); DARAJA_SHORTCODE=os.environ.get("DARAJA_SHORTCODE",""); DARAJA_TILL_NUMBER=os.environ.get("DARAJA_TILL_NUMBER",""); DARAJA_CALLBACK_URL=os.environ.get("DARAJA_CALLBACK_URL",""); DARAJA_TRANSACTION_TYPE=os.environ.get("DARAJA_TRANSACTION_TYPE","")
 WHATSAPP_VERIFY_TOKEN=os.environ.get("WHATSAPP_VERIFY_TOKEN",""); WHATSAPP_APP_SECRET=os.environ.get("WHATSAPP_APP_SECRET","")
 GOOGLE_SERVICE_ACCOUNT_JSON=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON",""); GOOGLE_SHEET_ID=os.environ.get("GOOGLE_SHEET_ID","")

# Admin-role integration review: this file is included in the complete deployment build.
