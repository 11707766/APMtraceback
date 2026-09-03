# APM Change Control

A small Flask application for authenticated requirement and signal change handoffs between developers and testers.

## Features

- Developer and tester registration and credential-based login
- Administrator-only temporary password reset
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

## Email configuration

Copy `.env.example` to a new `.env` file. For reliable delivery on Render, set `RESEND_API_KEY` and `RESEND_FROM_EMAIL` using a Resend verified domain. The app uses Resend when both are set, then falls back to Outlook SMTP when configured. Keep `.env` private; it is excluded from Git.

## Recovery codes

Set `RECOVERY_MANAGER_EMAILS` to the comma-separated work emails of authorized recovery managers. A signed-in manager can generate a one-time recovery code for a registered user and share it through an approved internal channel. The user opens Forgot password, enters the code and a new password, and the code expires after one hour.

## Password changes

After signing in, use the password button in the dashboard header to set a new password. This is available only to the signed-in user and does not require the old password.

## Deploy for any network

The included `render.yaml` deploys the app on Render's free compute plan with Gunicorn and HTTPS session cookies. In Render, create a new Blueprint from this GitHub repository. Render supplies a public address similar to `https://apmcontrol.onrender.com`.

The free service uses ephemeral SQLite storage, so accounts and requests can reset when the service restarts or redeploys. For durable production data, upgrade to a persistent disk and set `DATABASE_PATH` to its mount path, or migrate the application to a managed database.

A branded address such as `https://apmcontrol.com` requires registering that domain and connecting it to the deployed service. A single-label address such as `http://ApmControl` is only possible on a private network with custom DNS and cannot be a global mobile link.

## Outlook fallback configuration

Set the values shown in `.env.example` in the process environment. Microsoft 365 tenants may require SMTP AUTH to be enabled and an app password or SMTP relay account. Without these values, requests are still saved and the **Open in Outlook** button prepares the tester email in Outlook Web.