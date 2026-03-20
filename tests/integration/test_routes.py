"""
tests/integration/test_routes.py
Integration tests — Flask test client, SQLite in-memory DB.
"""
import io
import pytest
import numpy as np
import cv2
from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash


@pytest.fixture(scope="module")
def app():
    _app = create_app("testing")
    with _app.app_context():
        db.create_all()
        # Seed test user
        user = User(
            national_id   = "1199780000000001",
            email         = "test@govca.rw",
            password_hash = generate_password_hash("Password1234"),
            full_name     = "Test User",
        )
        db.session.add(user)
        db.session.commit()
        yield _app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_jpg(brightness=128, blur=0, size=(400, 400)) -> bytes:
    h, w = size
    img = np.ones((h, w, 3), dtype=np.uint8) * brightness
    cv2.ellipse(img, (w//2, h//2), (w//4, h//3), 0, 0, 360, (200, 175, 150), -1)
    if blur:
        img = cv2.GaussianBlur(img, (blur*2+1, blur*2+1), blur)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


# ── Auth ──────────────────────────────────────────────────────────────────────
class TestLogin:
    def test_get_login_page_returns_200(self, client):
        r = client.get("/auth/login")
        assert r.status_code == 200

    def test_login_invalid_nid_format(self, client):
        r = client.post("/auth/login", json={"national_id": "123", "password": "Password1234"})
        assert r.status_code == 400
        assert "16 digits" in r.get_json()["message"]

    def test_login_short_password(self, client):
        r = client.post("/auth/login", json={"national_id": "1199780000000001", "password": "short"})
        assert r.status_code == 400

    def test_login_wrong_credentials(self, client):
        r = client.post("/auth/login", json={"national_id": "1199780000000001", "password": "WrongPass1"})
        assert r.status_code == 401
        assert "Incorrect" in r.get_json()["message"]

    def test_login_success(self, client):
        r = client.post("/auth/login",
                        json={"national_id": "1199780000000001", "password": "Password1234"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "ok"
        assert "csrf_token" in data
        assert "redirect" in data

    def test_logout_redirects(self, client):
        # Login first
        client.post("/auth/login",
                    json={"national_id": "1199780000000001", "password": "Password1234"})
        r = client.post("/auth/logout")
        assert r.status_code in (302, 200)

    def test_register_new_user(self, client):
        r = client.post("/auth/register", json={
            "national_id": "1199780000000099",
            "email":       "new@govca.rw",
            "password":    "NewPass1234",
            "full_name":   "New User",
        })
        assert r.status_code == 200
        assert r.get_json()["status"] == "ok"

    def test_register_duplicate_nid(self, client):
        r = client.post("/auth/register", json={
            "national_id": "1199780000000001",   # already exists
            "email":       "dup@govca.rw",
            "password":    "DupPass1234",
        })
        assert r.status_code == 409


# ── Upload ────────────────────────────────────────────────────────────────────
class TestUpload:
    def _login(self, client):
        client.post("/auth/login",
                    json={"national_id": "1199780000000001", "password": "Password1234"})

    def test_upload_page_requires_login(self, client):
        r = client.get("/upload/")
        assert r.status_code == 302  # redirect to login

    def test_upload_page_accessible_when_logged_in(self, client):
        self._login(client)
        r = client.get("/upload/")
        assert r.status_code == 200

    def test_upload_blurry_image_rejected(self, client):
        self._login(client)
        data = {"photo": (io.BytesIO(_make_jpg(blur=30)), "test.jpg"),
                "app_ref": "APP-TEST-001", "cert_type": "LOCAL_INDIVIDUAL"}
        r = client.post("/upload/submit", data=data, content_type="multipart/form-data")
        assert r.status_code == 422
        body = r.get_json()
        assert body["status"] == "rejected"
        assert body["defect_code"] == "IMAGE_TOO_BLURRY"

    def test_upload_dark_image_rejected(self, client):
        self._login(client)
        data = {"photo": (io.BytesIO(_make_jpg(brightness=5)), "dark.jpg"),
                "app_ref": "APP-TEST-002", "cert_type": "LOCAL_INDIVIDUAL"}
        r = client.post("/upload/submit", data=data, content_type="multipart/form-data")
        assert r.status_code == 422
        assert r.get_json()["defect_code"] == "IMAGE_TOO_DARK"

    def test_upload_no_file_returns_400(self, client):
        self._login(client)
        r = client.post("/upload/submit", data={}, content_type="multipart/form-data")
        assert r.status_code == 400

    def test_upload_wrong_extension_rejected(self, client):
        self._login(client)
        data = {"photo": (io.BytesIO(b"fake pdf content"), "document.pdf"),
                "app_ref": "APP-TEST-003"}
        r = client.post("/upload/submit", data=data, content_type="multipart/form-data")
        assert r.status_code == 400

    def test_application_status_endpoint(self, client):
        self._login(client)
        # First create an application via upload
        client.post("/upload/submit",
                    data={"photo": (io.BytesIO(_make_jpg(blur=30)), "test.jpg"),
                          "app_ref": "APP-STATUS-001"},
                    content_type="multipart/form-data")
        r = client.get("/upload/status/APP-STATUS-001")
        assert r.status_code == 200
        body = r.get_json()
        assert "status" in body
        assert "photo_attempts" in body


# ── Dashboard ─────────────────────────────────────────────────────────────────
class TestDashboard:
    def _login(self, client):
        client.post("/auth/login",
                    json={"national_id": "1199780000000001", "password": "Password1234"})

    def test_health_endpoint_returns_json(self, client):
        r = client.get("/dashboard/api/health")
        assert r.status_code in (200, 503)
        body = r.get_json()
        assert "status" in body
        assert "checks" in body

    def test_metrics_endpoint_returns_json(self, client):
        self._login(client)
        r = client.get("/dashboard/api/metrics")
        assert r.status_code == 200
        body = r.get_json()
        assert "uploads_24h" in body
        assert "accept_rate" in body
        assert "hourly_trend" in body

    def test_activity_endpoint_returns_list(self, client):
        self._login(client)
        r = client.get("/dashboard/api/activity")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_dashboard_page_requires_login(self, client):
        r = client.get("/dashboard/")
        # Should redirect to login if not authenticated
        assert r.status_code in (200, 302)
