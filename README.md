# Cvent Plus

A Django hall-rental operations and commission management starter application.

## Stack
- Django 5, server-rendered Django templates (no Django Forms)
- Tailwind CSS CDN for rapid UI styling
- Lucide icons via CDN
- SQLite by default; switch `DATABASES` for production
- White / near-black visual system

## Setup
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Visit `/` and sign in with the superuser credentials. There is no public registration page.
Django's built-in admin is available at `/django-admin/`.

## Roles and workflow
- **Superuser / system administrator:** Django superuser; can create staff admins in Django admin.
- **Admin:** manages super agents, hall owners, bookings, withdrawals, payment proof, and account status.
- **Super agent:** creates agents, hall owners, payment methods, and withdrawal requests; sees direct and downline owners.
- **Agent:** creates hall owners, payment methods, and withdrawal requests; sees own owners and commission ledger.
- A super agent can suspend an agent they created, with a required reason. Suspended accounts cannot log in.
- Hall owners require admin approval before bookings can be entered.
- Admin can add multiple payment proofs (maximum 20), record partial payments, add remaining-payment proofs later, and mark a booking paid only when recorded advance plus proof amounts cover the total.
- Marking a booking paid creates commission ledger entries once: 1% to the responsible agent and 1% to their super agent; a super agent's direct owner booking earns that super agent 2%.

## Important implementation notes
- Commission is calculated from the booking's **total amount** when admin marks it paid.
- Commission ledger rows are idempotent per booking and beneficiary.
- Withdrawal approval records an uploaded proof image and debits the requested amount.
- File uploads are stored under `media/`; configure durable private object storage and access controls in production.
- Tailwind CDN is suitable for a prototype. For production, compile Tailwind assets locally.
- Add deployment hardening before production: PostgreSQL, HTTPS, secure cookies, email delivery, audit log retention, backups, malware scanning for uploads, and object-level authorization review.

## Initial admin workflow
1. Create a superuser with `createsuperuser`.
2. Log in to `/django-admin/` and create staff users with role `admin` (or create them in Django admin).
3. Admin creates/activates super agents and approves hall owners.
4. Super agents create agents; agents and super agents add hall owners.
5. Admin creates bookings and marks them paid after all payment has been verified.
