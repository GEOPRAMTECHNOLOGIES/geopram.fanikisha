def normalize_phone(phone):
    p=(phone or "").replace(" ","").replace("-","")
    if p.startswith("07") or p.startswith("01"): return "254"+p[1:]
    if p.startswith("+254"): return p[1:]
    return p
