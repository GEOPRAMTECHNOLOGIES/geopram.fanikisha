def subscription_active(sub): return bool(sub and sub.get("status")=="ACTIVE")
