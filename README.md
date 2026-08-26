# AMP Change Control

A small Flask application for authenticated requirement and signal change handoffs between developers and testers.

## Features

- Developer and tester registration and credential-based login
- One-hour password-reset links, delivered by Outlook SMTP when configured
- Developer change requests with requirement/signal ID, function, tester, reason, and priority
- Side-by-side comparison of the previous and newly updated requirement or signal
- Tester dashboard filtered by the tester's registered email
- Tester status decisions: New, In Review, Approved, or Rejected
- Automatic Outlook SMTP notification plus an Outlook Web compose fallback
- SQLite persistence, password hashing, CSRF protection, and role-based access

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SECRET_KEY = "replace-with-a-long-random-value"
python app.py
```

Open `http://127.0.0.1:5000`, register one developer and one tester, then use the tester's email when creating a request.

## Outlook configuration

Set the values shown in `.env.example` in the process environment. Microsoft 365 tenants may require SMTP AUTH to be enabled and an app password or SMTP relay account. Without these values, requests are still saved and the **Open in Outlook** button prepares the tester email in Outlook Web.