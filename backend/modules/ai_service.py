def safe_ai_context(data):
    blocked={"passwordHash","accessToken","encryptedKey","clientSecret","consumerSecret"}
    return {k:v for k,v in data.items() if k not in blocked}
