def registration_allowed(setting): return True if setting is None else bool(setting.get("value",True))
