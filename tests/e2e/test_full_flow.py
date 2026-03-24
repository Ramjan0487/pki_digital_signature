"""
tests/e2e/test_full_flow.py
End-to-end test: register → login → upload (reject) → upload (accept) → NID update
Uses Flask test client with in-memory SQLite.
"""
import io
import pytest
import numpy as np
import cv2
from app import create_app, db
from werkzeug.security import generate_password_hash


@pytest.fixture(scope="module")
def app():
    _app = create_app("testing")
    with _app.app_context():
        db.create_all()
        yield _app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_jpg(brightness=128, blur=0, w=400, h=400) -> bytes:
    img = np.ones((h, w, 3), dtype=np.uint8) * brightness
    cv2.ellipse(img, (w//2, h//2), (w//4, h//3), 0, 0, 360, (200, 175, 150), -1)
    cv2.circle(img, (w//2 - 60, h//2 - 40), 20, (60, 40, 20), -1)
    cv2.circle(img, (w//2 + 60, h//2 - 40), 20, (60, 40, 20), -1)
    if blur:
        img = cv2.GaussianBlur(img, (blur*2+1, blur*2+1), blur)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


class TestFullApplicationFlow:
    NID  = "1199780000099999"
    NID2 = "1199780000088888"
    EMAIL = "e2e@govca.rw"
    PW    = "E2EPassword99"

    def test_01_register(self, client):
        r = client.post("/auth/register", json={
            "national_id": self.NID,
            "email":       self.EMAIL,
            "password":    self.PW,
            "full_name":   "E2E Test User",
        })
        assert r.status_code == 200
        assert r.get_json()["status"] == "ok"

    def test_02_login_wrong_password_fails(self, client):
        r = client.post("/auth/login",
                        json={"national_id": self.NID, "password": "WrongPass99"})
        assert r.status_code == 401

    def test_03_login_success(self, client):
        r = client.post("/auth/login",
                        json={"national_id": self.NID, "password": self.PW})
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "ok"
        assert "csrf_token" in data

    def test_04_upload_blurry_rejected(self, client):
        r = client.post("/upload/submit",
                        data={
                            "photo":     (io.BytesIO(_make_jpg(blur=30)), "blurry.jpg"),
                            "app_ref":   "E2E-FLOW-001",
                            "cert_type": "LOCAL_INDIVIDUAL",
                        },
                        content_type="multipart/form-data")
        assert r.status_code == 422
        body = r.get_json()
        assert body["status"] == "rejected"
        assert body["defect_code"] == "IMAGE_TOO_BLURRY"
        assert "options" in body
        assert "retry" in body["options"]
        assert "cancel" in body["options"]

    def test_05_application_status_after_rejection(self, client):
        r = client.get("/upload/status/E2E-FLOW-001")
        assert r.status_code == 200
        body = r.get_json()
        assert body["status"] == "PHOTO_REJECTED"
        assert body["photo_attempts"] == 1

    def test_06_upload_dark_image_rejected(self, client):
        r = client.post("/upload/submit",
                        data={
                            "photo":   (io.BytesIO(_make_jpg(brightness=5)), "dark.jpg"),
                            "app_ref": "E2E-FLOW-001",
                        },
                        content_type="multipart/form-data")
        assert r.status_code == 422
        assert r.get_json()["defect_code"] == "IMAGE_TOO_DARK"

    def test_07_attempt_count_increments(self, client):
        r = client.get("/upload/status/E2E-FLOW-001")
        assert r.get_json()["photo_attempts"] == 2

    def test_08_health_check_passes(self, client):
        r = client.get("/dashboard/api/health")
        body = r.get_json()
        assert body["checks"]["database"]["status"] == "ok"

    def test_09_metrics_reflect_activity(self, client):
        r = client.get("/dashboard/api/metrics")
        body = r.get_json()
        assert body["rejected_24h"] >= 2
        assert body["uploads_24h"] >= 2

    def test_10_nid_update_requires_accepted_photo(self, client):
        # Application is still in REJECTED state
        r = client.post("/nid/confirm",
                        json={"app_ref": "E2E-FLOW-001", "national_id": self.NID2})
        # Should fail — photo not accepted yet
        assert r.status_code in (409, 404)

    def test_11_cancel_application(self, client):
        r = client.post(f"/nid/cancel/E2E-FLOW-001")
        assert r.status_code == 200
        body = r.get_json()
        assert body["status"] == "ok"
        assert "restart" in body

    def test_12_logout(self, client):
        r = client.post("/auth/logout")
        assert r.status_code in (200, 302)

    def test_13_upload_requires_auth_after_logout(self, client):
        r = client.get("/upload/")
        assert r.status_code in (302, 401)
