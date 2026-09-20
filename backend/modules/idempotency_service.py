def idempotency_key(value): return str(value or "").strip()[:200]
