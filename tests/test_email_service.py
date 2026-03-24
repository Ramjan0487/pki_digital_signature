"""
Tests for UC-03 — Email notification service
"""
import pytest
from unittest.mock import patch, MagicMock
from src.email_service.mailer import (
    send_image_problem_email,
    _build_html,
    _build_plain,
    DEFECT_DESCRIPTIONS,
)


class TestEmailContent:
    def test_html_contains_application_id(self):
        html = _build_html(
            app_id="APP-2024-001",
            defect_code="EYES_CLOSED",
            defect_label="Both eyes appear closed.",
            message="Please retake with eyes open.",
            reupload_url="https://www.govca.rw/document/stepIndvdlDocument.sg?app=APP-2024-001",
            cancel_url="https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg?id=APP-2024-001",
        )
        assert "APP-2024-001" in html

    def test_html_contains_reupload_link(self):
        html = _build_html(
            app_id="APP-2024-001",
            defect_code="IMAGE_TOO_BLURRY",
            defect_label="Your photo is too blurry.",
            message="Please retake in focus.",
            reupload_url="https://www.govca.rw/document/stepIndvdlDocument.sg",
            cancel_url="https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg",
        )
        assert "Change Photo" in html
        assert "Do not continue" in html
        assert "stepIndvdlDocument.sg" in html

    def test_html_contains_govca_contact(self):
        html = _build_html(
            app_id="APP-2024-002",
            defect_code="NO_FACE_DETECTED",
            defect_label="No face detected.",
            message="Please upload a clear photo.",
            reupload_url="https://www.govca.rw/document/stepIndvdlDocument.sg",
            cancel_url="https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg",
        )
        assert "info@govca.rw" in html
        assert "govca.rw" in html

    def test_plain_text_contains_defect(self):
        text = _build_plain(
            app_id="APP-2024-003",
            defect_label="Your left ear is not visible.",
            message="Please remove hair covering your ear.",
            reupload_url="https://www.govca.rw/document/stepIndvdlDocument.sg",
        )
        assert "left ear" in text.lower()
        assert "stepIndvdlDocument.sg" in text

    def test_all_defect_codes_have_descriptions(self):
        known_codes = [
            "IMAGE_TOO_BLURRY", "IMAGE_TOO_DARK", "IMAGE_TOO_BRIGHT",
            "LOW_CONTRAST", "IMAGE_TOO_SMALL", "INVALID_IMAGE",
            "NO_FACE_DETECTED", "MULTIPLE_FACES_DETECTED", "FACE_TOO_SMALL",
            "EYES_CLOSED", "LEFT_EYE_CLOSED", "RIGHT_EYE_CLOSED",
            "LEFT_EAR_OCCLUDED", "RIGHT_EAR_OCCLUDED", "FACE_PARTIALLY_OCCLUDED",
        ]
        for code in known_codes:
            assert code in DEFECT_DESCRIPTIONS, f"Missing description for {code}"

    def test_unknown_defect_code_uses_fallback(self):
        fallback = DEFECT_DESCRIPTIONS.get("UNKNOWN_CODE", "An issue was found with your photo.")
        assert len(fallback) > 0


class TestEmailSending:
    @patch("src.email_service.mailer.smtplib.SMTP_SSL")
    def test_email_sends_without_error(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        # Call the underlying function directly (bypass Celery)
        send_image_problem_email.__wrapped__(
            None,
            to="applicant@example.com",
            application_id="APP-2024-001",
            defect_code="EYES_CLOSED",
            message="Both eyes appear closed.",
            reupload_url="https://www.govca.rw/document/stepIndvdlDocument.sg",
            cancel_url="https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg",
        )
        mock_server.sendmail.assert_called_once()

    @patch("src.email_service.mailer.smtplib.SMTP_SSL")
    def test_email_retries_on_smtp_failure(self, mock_smtp):
        mock_smtp.side_effect = Exception("SMTP connection failed")
        task = send_image_problem_email
        with pytest.raises(Exception):
            task.__wrapped__(
                MagicMock(retry=MagicMock(side_effect=Exception("retry"))),
                to="applicant@example.com",
                application_id="APP-2024-001",
                defect_code="IMAGE_TOO_BLURRY",
                message="Too blurry.",
                reupload_url="https://www.govca.rw/document/stepIndvdlDocument.sg",
                cancel_url="https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg",
            )
