# Fluent Business Automation SaaS

Next.js + TypeScript + Tailwind frontend, Flask/Python backend, MongoDB Atlas, secure admin console, encrypted client AI keys, invoices/receipts, SMTP, WhatsApp webhook, Daraja environment configuration, optional Redis and Google Sheets hooks.

## Security model
- Platform secrets stay in Vercel environment variables.
- Client AI keys are encrypted with AES-256-GCM before MongoDB storage.
- Raw secrets are never returned to the browser.
- Admin authorization is enforced by MongoDB `role=ADMIN`; `ADMIN_PATH` is only a routing layer.
- Cookies are HttpOnly/Secure in production.
- Documents require admin approval before client visibility.
- Admin actions are audited.
- Daraja credentials are never stored in MongoDB.

## Deploy
1. Create MongoDB Atlas database/user.
2. Copy `.env.example` and generate `SESSION_SECRET` and `ENCRYPTION_KEY`.
3. Seed first admin with `scripts/create_admin.py`.
4. Set Vercel Production environment variables.
5. Mark production secrets Sensitive in Vercel.
6. Deploy and redeploy after env changes.

Vercel supports Flask through the Python runtime; `api/index.py` imports the Flask application.

## Important production follow-ups
This scaffold is the core system, not a claim that every external provider is already live-configured. Before public launch, add/enable: email OTP verification and password reset, Redis rate limiting/queues, WhatsApp signature validation, exact Daraja API flow approved for your production app, idempotent payment callbacks, background jobs, monitoring, automated tests, and Google Sheets export if desired.

Do not put any real API keys in source control or in chat.
