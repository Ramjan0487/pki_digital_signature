"""
Tests for UC-01 — User login and session management
"""
import pytest
from src.auth.login import authenticate_user, validate_session


class TestLogin:
    def test_valid_credentials_return_token(self):
        result = authenticate_user("1199780123456789", "password123")
        assert result["success"] is True
        assert result["token"].startswith("")   # non-empty token
        assert len(result["token"]) == 64       # 32 hex bytes

    def test_short_nid_fails_validation(self):
        result = authenticate_user("12345", "password123")
        assert result["success"] is False
        assert "16 digits" in result["error"]
        assert "forgot_password_url" in result

    def test_non_numeric_nid_fails(self):
        result = authenticate_user("ABCD1234EFGH5678", "password123")
        assert result["success"] is False

    def test_short_password_fails(self):
        result = authenticate_user("1199780123456789", "short")
        assert result["success"] is False
        assert "8 characters" in result["error"]

    def test_session_created_after_login(self):
        result = authenticate_user("1199780123456789", "password123")
        assert validate_session(result["token"]) is True

    def test_invalid_token_rejected(self):
        assert validate_session("fake_token_xyz") is False

    def test_forgot_password_url_in_error(self):
        result = authenticate_user("short", "pw")
        assert "govca.rw/reissue" in result.get("forgot_password_url", "")
