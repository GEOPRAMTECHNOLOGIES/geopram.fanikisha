def webhook_event_name(payload): return payload.get("event","UNKNOWN") if isinstance(payload,dict) else "UNKNOWN"
