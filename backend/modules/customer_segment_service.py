def segment(customers,tag): return [c for c in customers if tag in (c.get("tags") or [])]
