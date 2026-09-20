import csv, io
def csv_text(rows):
    if not rows:return ""
    out=io.StringIO();w=csv.DictWriter(out,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows);return out.getvalue()
