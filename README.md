# Fluent Business Automation SaaS

A MongoDB-backed WhatsApp Business Automation SaaS with separate client and administrator workspaces.

## Implemented system

- Client registration, email OTP verification, login/logout and password change.
- MongoDB-backed account and business profiles.
- WhatsApp Business connection with encrypted access-token storage.
- WhatsApp outbound messaging through the configured Graph API.
- WhatsApp webhook verification/ingestion and normalized inbound messages.
- Keyword automation rules that can automatically reply to incoming messages.
- Customer/CRM CRUD with tags and notes.
- Client AI configuration with encrypted OpenAI credentials and response generation.
- M-Pesa payment recording and Daraja STK Push/callback workflow when the existing environment is configured.
- Subscription plans and client subscriptions.
- Invoice, receipt and document records.
- Operational reports and CSV exports.
- Email delivery for verification and document sending using existing SMTP configuration.
- Administrator Control Center with live MongoDB data.
- MongoDB-authoritative ADMIN role enforcement on every admin API.
- Client status and role administration.
- Registration enable/disable control.
- WhatsApp and AI administration without exposing secrets.
- Payment verification and audit trail.
- Google Sheets backup hook using the existing server-side environment credentials.
- Live Admin AI context built from sanitized current database metrics.
- Comprehensive audit logging for security-sensitive actions.
- System/Mac/Normal appearance modes and responsive layouts.

## Security

The hidden administrator path is not the security boundary. Administrative APIs query the current MongoDB user and require `role=ADMIN`. Passwords, session secrets, access tokens and API keys are not returned to browser clients or written into audit metadata.

## Environment

The existing `.env.example` was intentionally left unchanged. No new environment variables were introduced by this build.

## Deployment

Use the existing Vercel configuration and environment values. The Next.js frontend and Flask API are deployed together; `/api/*` is rewritten to `api/index.py`.
