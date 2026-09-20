def payment_state(status): return status.upper() if status else "PENDING"
def is_success(status): return payment_state(status) in {"PAID","VERIFIED","SUCCESS"}
