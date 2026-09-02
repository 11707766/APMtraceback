# APM Change Control

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

To open the app from a phone on the same Wi-Fi network, keep the server running and open `http://<computer-ip>:5000` on the phone. The default `APP_HOST=0.0.0.0` enables LAN access. Windows Firewall must allow Python on that network.

## Local email configuration

Copy `.env.example` to a new `.env` file and set `OUTLOOK_SMTP_USER` to the sending mailbox and `OUTLOOK_SMTP_PASSWORD` to its app password. The app loads this local file automatically when it starts. Keep `.env` private; it is excluded from Git.

## Deploy for any network

The included `render.yaml` deploys the app on Render's free compute plan with Gunicorn and HTTPS session cookies. In Render, create a new Blueprint from this GitHub repository. Render supplies a public address similar to `https://apmcontrol.onrender.com`.

The free service uses ephemeral SQLite storage, so accounts and requests can reset when the service restarts or redeploys. For durable production data, upgrade to a persistent disk and set `DATABASE_PATH` to its mount path, or migrate the application to a managed database.

A branded address such as `https://apmcontrol.com` requires registering that domain and connecting it to the deployed service. A single-label address such as `http://ApmControl` is only possible on a private network with custom DNS and cannot be a global mobile link.

## Outlook configuration

Set the values shown in `.env.example` in the process environment. Microsoft 365 tenants may require SMTP AUTH to be enabled and an app password or SMTP relay account. Without these values, requests are still saved and the **Open in Outlook** button prepares the tester email in Outlook Web.