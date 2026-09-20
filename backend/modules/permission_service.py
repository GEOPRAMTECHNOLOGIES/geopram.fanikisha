def can_manage_client(role): return str(role or "").upper()=="ADMIN"
