def audit_event(action, actor="SYSTEM", target="", metadata=None):
    return {"action":action,"actor":actor,"target":target,"metadata":metadata or {}}
