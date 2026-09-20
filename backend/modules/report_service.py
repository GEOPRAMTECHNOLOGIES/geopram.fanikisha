def summarize_counts(rows): return {k:len(v) if isinstance(v,list) else v for k,v in rows.items()}
