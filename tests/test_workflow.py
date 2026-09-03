import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app, get_db, init_db, send_email


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        app.config.update(
            TESTING=True,
            DATABASE=str(Path(self.temp_dir.name) / "test.db"),
            SECRET_KEY="test-secret",
            SERVER_NAME="localhost",
        )
        with app.app_context():
            init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf(self):
        self.client.get("/login")
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def post(self, path, data, follow_redirects=True):
        data["csrf_token"] = self.csrf()
        return self.client.post(path, data=data, follow_redirects=follow_redirects)

    def register(self, name, email, role):
        return self.post(
            "/register",
            {"name": name, "email": email, "role": role, "password": "Password123"},
        )

    def login(self, email, password="Password123"):
        return self.post("/login", {"email": email, "password": password})

    @patch.dict("os.environ", {"RESEND_API_KEY": "test-key", "RESEND_FROM_EMAIL": "APM <no-reply@example.com>"}, clear=True)
    @patch("app.urlopen")
    def test_resend_is_used_when_configured(self, mock_urlopen):
        sent, status = send_email("user@example.com", "Subject", "Body")
        self.assertTrue(sent)
        self.assertEqual(status, "Sent")
        mock_urlopen.assert_called_once()

    def test_complete_developer_to_tester_workflow(self):
        self.assertIn(b"Account created", self.register("Dev User", "dev@example.com", "developer").data)
        self.register("Test User", "tester@example.com", "tester")
        self.register("Observer", "observer@example.com", "tester")

        self.assertIn(b"Developer workspace", self.login("dev@example.com").data)
        changed_password = self.post("/account/password", {"password": "ChangedPassword123"})
        self.assertIn(b"Password updated", changed_password.data)
        self.post("/logout", {})
        self.assertIn(b"Developer workspace", self.login("dev@example.com", "ChangedPassword123").data)
        response = self.post(
            "/requests/new",
            {
                "requirement_signal_id": "SIG-CAN-08",
                "function_name": "Battery state monitoring",
                "previous_value": "Timeout = 500 ms",
                "new_value": "Timeout = 350 ms",
                "tester_name": "Test User",
                "tester_email": "tester@example.com",
                "reason": "Adjust the timeout threshold for the updated control unit.",
                "priority": "High",
            },
        )
        self.assertIn(b"SIG-CAN-08", response.data)
        self.assertIn(b"Timeout = 500 ms", response.data)
        self.assertIn(b"Timeout = 350 ms", response.data)
        self.assertIn(b"Open in Outlook", response.data)

        edited = self.post(
            "/requests/1/edit",
            {
                "requirement_signal_id": "SIG-CAN-08",
                "function_name": "Battery state monitoring",
                "previous_value": "Timeout = 500 ms",
                "new_value": "Timeout = 300 ms",
                "tester_name": "Test User",
                "tester_email": "tester@example.com",
                "reason": "Update the timeout after bench validation.",
                "priority": "Critical",
            },
        )
        self.assertIn(b"Request updated", edited.data)
        self.assertIn(b"Timeout = 300 ms", edited.data)

        self.post("/logout", {})
        tester_dashboard = self.login("tester@example.com")
        self.assertIn(b"Tester workspace", tester_dashboard.data)
        self.assertIn(b"SIG-CAN-08", tester_dashboard.data)
        forbidden_delete = self.post("/requests/1/delete", {}, follow_redirects=False)
        self.assertEqual(forbidden_delete.status_code, 403)

        updated = self.post("/requests/1/status", {"status": "Approved"})
        self.assertIn(b"Approved", updated.data)

        self.post("/logout", {})
        observer_dashboard = self.login("observer@example.com")
        self.assertIn(b"SIG-CAN-08", observer_dashboard.data)
        self.assertEqual(self.client.get("/requests/1").status_code, 200)

        self.post("/logout", {})
        self.login("dev@example.com", "ChangedPassword123")
        deleted = self.post("/requests/1/delete", {})
        self.assertIn(b"Request SIG-CAN-08 deleted", deleted.data)
        self.assertNotIn(b"SIG-CAN-08</strong>", deleted.data)

        forgot_password = self.client.get("/forgot-password", follow_redirects=True)
        self.assertIn(b"Sign in to change your password", forgot_password.data)


if __name__ == "__main__":
    unittest.main()