"""
Unit tests for PII redaction functionality
"""
from unittest.mock import patch, MagicMock

# Mock the presidio imports since they may not be available in test environment
with patch.dict(
    'sys.modules',
    {
        'presidio_analyzer': MagicMock(),
        'presidio_anonymizer': MagicMock(),
    },
):
    from src.app.common.pii import redact_and_map, reidentify


class TestPIIRedaction:
    """Test cases for PII redaction functionality"""

    def test_redact_and_map_email(self):
        """Test that email addresses are properly redacted and mapped"""
        text = "連絡先は test@example.com です"

        with patch('src.app.common.pii.analyzer') as mock_analyzer, patch(
            'src.app.common.pii.anonymizer'
        ) as mock_anonymizer:

            # Mock analyzer results
            mock_analyzer.analyze.return_value = [
                MagicMock(
                    entity_type="EMAIL_ADDRESS",
                    start=5,
                    end=20,
                    score=0.9,
                )
            ]

            # Mock anonymizer results
            mock_anonymizer.anonymize.return_value = MagicMock(
                text="連絡先は [EMAIL_1] です",
                items=[
                    MagicMock(
                        operator="replace",
                        start=5,
                        end=20,
                        text="[EMAIL_1]",
                    )
                ],
            )

            redacted_text, pii_map = redact_and_map(text)

            assert redacted_text == "連絡先は [EMAIL_1] です"
            assert "[EMAIL_1]" in pii_map
            assert pii_map["[EMAIL_1]"] == "test@example.com"

    def test_redact_and_map_phone(self):
        """Test that phone numbers are properly redacted and mapped"""
        text = "電話番号は 090-1234-5678 です"

        with patch('src.app.common.pii.analyzer') as mock_analyzer, patch(
            'src.app.common.pii.anonymizer'
        ) as mock_anonymizer:

            # Mock analyzer results
            mock_analyzer.analyze.return_value = [
                MagicMock(
                    entity_type="PHONE_NUMBER",
                    start=5,
                    end=18,
                    score=0.9,
                )
            ]

            # Mock anonymizer results
            mock_anonymizer.anonymize.return_value = MagicMock(
                text="電話番号は [PHONE_1] です",
                items=[
                    MagicMock(
                        operator="replace",
                        start=5,
                        end=18,
                        text="[PHONE_1]",
                    )
                ],
            )

            redacted_text, pii_map = redact_and_map(text)

            assert redacted_text == "電話番号は [PHONE_1] です"
            assert "[PHONE_1]" in pii_map
            assert pii_map["[PHONE_1]"] == "090-1234-5678"

    def test_redact_and_map_no_pii(self):
        """Test that text without PII is returned unchanged"""
        text = "これは普通のテキストです"

        with patch('src.app.common.pii.analyzer') as mock_analyzer, patch(
            'src.app.common.pii.anonymizer'
        ) as mock_anonymizer:

            # Mock analyzer results - no PII found
            mock_analyzer.analyze.return_value = []

            # Mock anonymizer results
            mock_anonymizer.anonymize.return_value = MagicMock(
                text=text,
                items=[]
            )

            redacted_text, pii_map = redact_and_map(text)

            assert redacted_text == text
            assert pii_map == {}

    def test_reidentify_text(self):
        """Test that PII placeholders are properly reidentified"""
        text = "連絡先は [EMAIL_1] で、電話は [PHONE_1] です"
        pii_map = {
            "[EMAIL_1]": "test@example.com",
            "[PHONE_1]": "090-1234-5678"
        }

        result = reidentify(text, pii_map)

        assert result == "連絡先は test@example.com で、電話は 090-1234-5678 です"

    def test_reidentify_partial_map(self):
        """Test reidentification when some placeholders are missing from map"""
        text = "連絡先は [EMAIL_1] で、電話は [PHONE_1] です"
        pii_map = {
            "[EMAIL_1]": "test@example.com"
            # [PHONE_1] is missing
        }

        result = reidentify(text, pii_map)

        assert result == "連絡先は test@example.com で、電話は [PHONE_1] です"

    def test_reidentify_empty_map(self):
        """Test reidentification with empty PII map"""
        text = "連絡先は [EMAIL_1] です"
        pii_map = {}

        result = reidentify(text, pii_map)

        assert result == text  # Should return original text unchanged
