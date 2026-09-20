# AI guardrails

This document defines the production workflow for ai guardrails in the Fluent Business Automation SaaS.

- Server-side authorization is required for client and admin operations.
- Secrets and credentials are never rendered in plaintext.
- State changes create audit records.
- Payment state is confirmed by provider callbacks before an invoice is marked paid.
