# Vercel deployment checklist

## Build
- Node.js: 20.9+ (Vercel uses the project engine declaration)
- Build command: `npm run build`
- Do not add `next export`.
- Flask entry point: `api/index.py`

## Required production environment variables
`MONGODB_URI`, `DATABASE_NAME`, `SESSION_SECRET`, `ENCRYPTION_KEY`, SMTP variables, and `ADMIN_PATH`.

Add provider variables only when the integration is configured: OpenAI, WhatsApp, Daraja, Redis/Upstash, Google Sheets.

## Security
- Never commit `.env` or service-account JSON.
- Keep `SESSION_SECRET` and `ENCRYPTION_KEY` stable after production data exists.
- `ADMIN_PATH` is routing obfuscation, not authorization. The Flask API requires the live MongoDB user record to have `role=ADMIN` (case-insensitive). The admin UI performs a second database-backed session check before rendering.
- Client AI credentials are encrypted before MongoDB storage.

/* Admin-role integration review: included in complete deployment build. */
