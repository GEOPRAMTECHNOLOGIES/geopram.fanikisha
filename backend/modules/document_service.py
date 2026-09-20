def document_status(approved=False, rejected=False): return "REJECTED" if rejected else "APPROVED" if approved else "PENDING"
