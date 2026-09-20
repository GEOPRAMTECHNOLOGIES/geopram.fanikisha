def backup_kind(kind): return kind if kind in {"daily","weekly","monthly","manual"} else "manual"
