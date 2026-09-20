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
1. Create a MongoDB Atlas project and database user. Set `DATABASE_NAME=whatsapp_saas`. You do not need to manually create a database in Atlas; the deployment creates the application collections on startup.
2. Copy `.env.example` and generate `SESSION_SECRET` and `ENCRYPTION_KEY`.
3. Seed first admin with `scripts/create_admin.py`.
4. Set Vercel Production environment variables.
5. Mark production secrets Sensitive in Vercel.
6. Deploy and redeploy after env changes.

Vercel supports Flask through the Python runtime; `api/index.py` imports the Flask application.

## Important production follow-ups
This scaffold is the core system, not a claim that every external provider is already live-configured. Before public launch, add/enable: email OTP verification and password reset, Redis rate limiting/queues, WhatsApp signature validation, exact Daraja API flow approved for your production app, idempotent payment callbacks, background jobs, monitoring, automated tests, and Google Sheets export if desired.

Do not put any real API keys in source control or in chat.

## Admin login and database role

There is no hard-coded administrator account. Create a normal account or insert/update a user in MongoDB, then set that user's `role` field to exactly `ADMIN` and `emailVerified` to `true`. The login endpoint checks the database user record, and the configured `ADMIN_PATH` is protected by a signed session cookie. Direct access to `/admin-ui` or `__ADMIN__` is also blocked unless the session has the `ADMIN` role.

Example MongoDB update (replace the email):

```javascript
db.users.updateOne(
  { email: "admin@example.com" },
  { $set: { role: "ADMIN", emailVerified: true } }
)
```

The password must still be created using the included `scripts/create_admin.py` or through the application's password registration flow; do not put a plaintext password into MongoDB.

Set `ADMIN_PATH` in Vercel, for example:

```env
ADMIN_PATH=control-center-a8K4mQ72
```

Then an authenticated ADMIN reaches `/control-center-a8K4mQ72`. A client account, even if it knows the URL, is redirected to login and cannot render the admin UI.


## MongoDB visibility and login diagnostics

The application database is **`whatsapp_saas`** unless `DATABASE_NAME` is changed in Vercel. The deployment explicitly creates these collections on startup: `users`, `businesses`, `documents`, `audit_logs`, `ai_credentials`, `verification_tokens`, `subscriptions`, and `daraja_callbacks`.

After deployment, open `/api/health`. A healthy response includes the active database name, collection names, and user count. This is a safe diagnostic endpoint and does not expose MongoDB credentials.

If login returns `401 Invalid credentials`, verify that the account exists in the **same Atlas cluster/database configured by `MONGODB_URI` and `DATABASE_NAME`**. If you registered an account before changing the database settings, that account may exist in a different database.

For the admin account, the existing user document must contain:

```javascript
{ role: "ADMIN", emailVerified: true }
```

Do not put a plaintext password in MongoDB.

<!-- Project integration marker: complete admin-role + registration build -->
