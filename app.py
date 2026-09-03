import os
import secrets
import smtplib
import sqlite3
import json
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATABASE = Path(os.getenv("DATABASE_PATH", BASE_DIR / "amp.db"))

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
    DATABASE=str(DATABASE),
    RESET_TOKEN_HOURS=1,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('developer', 'tester')),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS change_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement_signal_id TEXT NOT NULL,
            function_name TEXT NOT NULL,
            previous_value TEXT NOT NULL DEFAULT '',
            new_value TEXT NOT NULL DEFAULT '',
            developer_name TEXT NOT NULL,
            developer_id INTEGER NOT NULL REFERENCES users(id),
            tester_name TEXT NOT NULL,
            tester_email TEXT NOT NULL COLLATE NOCASE,
            reason TEXT NOT NULL,
            priority TEXT NOT NULL CHECK (priority IN ('Low', 'Medium', 'High', 'Critical')),
            status TEXT NOT NULL DEFAULT 'New' CHECK (status IN ('New', 'In Review', 'Approved', 'Rejected')),
            notification_status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    request_columns = {row["name"] for row in db.execute("PRAGMA table_info(change_requests)")}
    for column in ("previous_value", "new_value"):
        if column not in request_columns:
            db.execute(f"ALTER TABLE change_requests ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
    db.commit()


@app.before_request
def load_user_and_csrf():
    user_id = session.get("user_id")
    g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone() if user_id else None
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    if request.method == "POST" and request.form.get("csrf_token") != session["csrf_token"]:
        abort(400, "Invalid CSRF token")


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)

    return wrapped_view


def send_email(recipient, subject, body):
    resend_api_key = os.getenv("RESEND_API_KEY")
    resend_from_email = os.getenv("RESEND_FROM_EMAIL")
    if resend_api_key and resend_from_email:
        payload = json.dumps(
            {"from": resend_from_email, "to": [recipient], "subject": subject, "text": body}
        ).encode()
        request_data = Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={"Authorization": f"Bearer {resend_api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request_data, timeout=15):
                pass
            return True, "Sent"
        except OSError as error:
            app.logger.warning("Resend notification failed: %s", error)
            return False, "Delivery failed"

    host = os.getenv("OUTLOOK_SMTP_HOST", "smtp.office365.com")
    port = int(os.getenv("OUTLOOK_SMTP_PORT", "587"))
    username = os.getenv("OUTLOOK_SMTP_USER")
    password = os.getenv("OUTLOOK_SMTP_PASSWORD")
    if not username or not password:
        return False, "Outlook SMTP is not configured"

    message = EmailMessage()
    message["From"] = username
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)
        return True, "Sent"
    except (OSError, smtplib.SMTPException) as error:
        app.logger.warning("Outlook notification failed: %s", error)
        return False, "Delivery failed"


def request_email(change_request):
    detail_url = url_for("request_detail", request_id=change_request["id"], _external=True)
    subject = f"[{change_request['priority']}] APM Change Control request {change_request['requirement_signal_id']}"
    body = (
        f"Hello {change_request['tester_name']},\n\n"
        f"{change_request['developer_name']} submitted a change for testing.\n\n"
        f"Requirement / Signal ID: {change_request['requirement_signal_id']}\n"
        f"Function: {change_request['function_name']}\n"
        f"Previous value:\n{change_request['previous_value']}\n\n"
        f"New value:\n{change_request['new_value']}\n\n"
        f"Reason: {change_request['reason']}\n"
        f"Priority: {change_request['priority']}\n\n"
        f"Open request: {detail_url}\n"
    )
    return subject, body


@app.route("/")
def index():
    return redirect(url_for("dashboard") if g.user else url_for("login"))


@app.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            next_url = request.args.get("next", "")
            return redirect(next_url if next_url.startswith("/") and not next_url.startswith("//") else url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("login.html")


@app.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        error = None
        if not name or not email or not password:
            error = "All fields are required."
        elif role not in {"developer", "tester"}:
            error = "Select a valid role."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        if error is None:
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                    (name, email, generate_password_hash(password), role, datetime.now(UTC).isoformat()),
                )
                db.commit()
                flash("Account created. You can now sign in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                error = "An account with this email already exists."
        flash(error, "error")
    return render_template("register.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=("GET", "POST"))
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            flash("Account is not registered.", "error")
        else:
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(UTC) + timedelta(hours=app.config["RESET_TOKEN_HOURS"])
            db = get_db()
            db.execute("UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0", (user["id"],))
            db.execute(
                "INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)",
                (user["id"], token, expires_at.isoformat()),
            )
            db.commit()
            reset_link = url_for("reset_password", token=token, _external=True)
            sent, _status = send_email(
                email,
                "Reset your APM Change Control password",
                f"Use this link within one hour to set a new password:\n\n{reset_link}",
            )
            if sent:
                flash("Password reset link sent. Check your email.", "success")
            else:
                flash("Password reset email could not be sent. Contact your administrator.", "error")
    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=("GET", "POST"))
def reset_password(token):
    reset = get_db().execute(
        "SELECT * FROM password_resets WHERE token = ? AND used = 0", (token,)
    ).fetchone()
    if not reset or datetime.fromisoformat(reset["expires_at"]) < datetime.now(UTC):
        flash("This reset link is invalid or expired.", "error")
        return redirect(url_for("forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            db = get_db()
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password), reset["user_id"]))
            db.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (reset["id"],))
            db.commit()
            flash("Password updated. Sign in with your new password.", "success")
            return redirect(url_for("login"))
    return render_template("reset_password.html")


@app.route("/account/password", methods=("GET", "POST"))
@login_required
def change_password():
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            db = get_db()
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password), g.user["id"]))
            db.commit()
            flash("Password updated.", "success")
            return redirect(url_for("dashboard"))
    return render_template("change_password.html")


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    rows = db.execute("SELECT * FROM change_requests ORDER BY created_at DESC").fetchall()
    counts = {status: sum(row["status"] == status for row in rows) for status in ("New", "In Review", "Approved", "Rejected")}
    return render_template("dashboard.html", requests=rows, counts=counts)


@app.route("/requests/new", methods=("GET", "POST"))
@login_required
def new_request():
    if g.user["role"] != "developer":
        abort(403)
    if request.method == "POST":
        values = {
            "requirement_signal_id": request.form.get("requirement_signal_id", "").strip(),
            "function_name": request.form.get("function_name", "").strip(),
            "previous_value": request.form.get("previous_value", "").strip(),
            "new_value": request.form.get("new_value", "").strip(),
            "tester_name": request.form.get("tester_name", "").strip(),
            "tester_email": request.form.get("tester_email", "").strip().lower(),
            "reason": request.form.get("reason", "").strip(),
            "priority": request.form.get("priority", ""),
        }
        if not all(values.values()) or values["priority"] not in {"Low", "Medium", "High", "Critical"}:
            flash("Complete every request field.", "error")
        else:
            now = datetime.now(UTC).isoformat()
            db = get_db()
            cursor = db.execute(
                """INSERT INTO change_requests
                (requirement_signal_id, function_name, previous_value, new_value, developer_name, developer_id,
                 tester_name, tester_email, reason, priority, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    values["requirement_signal_id"], values["function_name"], values["previous_value"],
                    values["new_value"], g.user["name"], g.user["id"], values["tester_name"],
                    values["tester_email"], values["reason"], values["priority"], now, now,
                ),
            )
            db.commit()
            change_request = db.execute("SELECT * FROM change_requests WHERE id = ?", (cursor.lastrowid,)).fetchone()
            subject, body = request_email(change_request)
            sent, status = send_email(change_request["tester_email"], subject, body)
            db.execute("UPDATE change_requests SET notification_status = ? WHERE id = ?", (status, change_request["id"]))
            db.commit()
            flash("Request created and tester notified." if sent else "Request created. Outlook delivery needs configuration; use the Outlook button.", "success")
            return redirect(url_for("request_detail", request_id=change_request["id"]))
    testers = get_db().execute("SELECT name, email FROM users WHERE role = 'tester' ORDER BY name").fetchall()
    return render_template("new_request.html", testers=testers, item=None)


def accessible_request(request_id):
    change_request = get_db().execute("SELECT * FROM change_requests WHERE id = ?", (request_id,)).fetchone()
    if not change_request:
        abort(404)
    return change_request


def owned_request(request_id):
    change_request = accessible_request(request_id)
    if g.user["role"] != "developer" or change_request["developer_id"] != g.user["id"]:
        abort(403)
    return change_request


@app.route("/requests/<int:request_id>/edit", methods=("GET", "POST"))
@login_required
def edit_request(request_id):
    change_request = owned_request(request_id)
    if request.method == "POST":
        values = {
            "requirement_signal_id": request.form.get("requirement_signal_id", "").strip(),
            "function_name": request.form.get("function_name", "").strip(),
            "previous_value": request.form.get("previous_value", "").strip(),
            "new_value": request.form.get("new_value", "").strip(),
            "tester_name": request.form.get("tester_name", "").strip(),
            "tester_email": request.form.get("tester_email", "").strip().lower(),
            "reason": request.form.get("reason", "").strip(),
            "priority": request.form.get("priority", ""),
        }
        if not all(values.values()) or values["priority"] not in {"Low", "Medium", "High", "Critical"}:
            flash("Complete every request field.", "error")
        else:
            db = get_db()
            db.execute(
                """UPDATE change_requests SET requirement_signal_id = ?, function_name = ?, previous_value = ?,
                new_value = ?, tester_name = ?, tester_email = ?, reason = ?, priority = ?, status = 'New',
                notification_status = 'Pending', updated_at = ? WHERE id = ?""",
                (
                    values["requirement_signal_id"], values["function_name"], values["previous_value"],
                    values["new_value"], values["tester_name"], values["tester_email"], values["reason"],
                    values["priority"], datetime.now(UTC).isoformat(), request_id,
                ),
            )
            db.commit()
            change_request = db.execute("SELECT * FROM change_requests WHERE id = ?", (request_id,)).fetchone()
            subject, body = request_email(change_request)
            sent, status = send_email(change_request["tester_email"], f"Updated: {subject}", body)
            db.execute("UPDATE change_requests SET notification_status = ? WHERE id = ?", (status, request_id))
            db.commit()
            flash("Request updated and tester notified." if sent else "Request updated. Use the Outlook button to notify the tester.", "success")
            return redirect(url_for("request_detail", request_id=request_id))
    testers = get_db().execute("SELECT name, email FROM users WHERE role = 'tester' ORDER BY name").fetchall()
    return render_template("new_request.html", testers=testers, item=change_request)


@app.post("/requests/<int:request_id>/delete")
@login_required
def delete_request(request_id):
    change_request = owned_request(request_id)
    get_db().execute("DELETE FROM change_requests WHERE id = ?", (request_id,))
    get_db().commit()
    flash(f"Request {change_request['requirement_signal_id']} deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/requests/<int:request_id>")
@login_required
def request_detail(request_id):
    change_request = accessible_request(request_id)
    subject, body = request_email(change_request)
    outlook_url = f"https://outlook.office.com/mail/deeplink/compose?to={quote(change_request['tester_email'])}&subject={quote(subject)}&body={quote(body)}"
    return render_template("request_detail.html", item=change_request, outlook_url=outlook_url)


@app.post("/requests/<int:request_id>/status")
@login_required
def update_status(request_id):
    accessible_request(request_id)
    if g.user["role"] != "tester":
        abort(403)
    status = request.form.get("status", "")
    if status not in {"New", "In Review", "Approved", "Rejected"}:
        abort(400)
    db = get_db()
    db.execute(
        "UPDATE change_requests SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now(UTC).isoformat(), request_id),
    )
    db.commit()
    flash("Request status updated.", "success")
    return redirect(url_for("request_detail", request_id=request_id))


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Database initialized.")


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )