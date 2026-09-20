def normalize_tags(tags): return sorted({str(x).strip() for x in (tags or []) if str(x).strip()})
