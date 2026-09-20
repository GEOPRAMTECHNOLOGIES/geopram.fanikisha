def is_admin(user): return bool(user and str(user.get("role","")).upper()=="ADMIN")
