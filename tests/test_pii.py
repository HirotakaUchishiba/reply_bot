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

        # Import the module to patch its variables directly
        from src.app.common import pii
        from src.app.common.pii import redact_and_map

        # Create mock objects
        mock_analyzer = MagicMock()
        mock_anonymizer = MagicMock()
        # Mock analyzer results
        mock_analyzer.analyze.return_value = [
            MagicMock(
                entity_type="EMAIL_ADDRESS",
                start=5,
                end=21,  # test@example.com is 16 chars, so 5+16=21
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
                    end=21,
                    text="[EMAIL_1]",
                )
            ],
        )

        # Temporarily replace the module variables
        original_analyzer = pii.analyzer
        original_anonymizer = pii.anonymizer

        try:
            pii.analyzer = mock_analyzer
            pii.anonymizer = mock_anonymizer
            redacted_text, pii_map = redact_and_map(text)

            assert redacted_text == "連絡先は [EMAIL_1] です"
            assert "[EMAIL_1]" in pii_map
            assert pii_map["[EMAIL_1]"] == "test@example.com"
        finally:
            # Restore original values
            pii.analyzer = original_analyzer
            pii.anonymizer = original_anonymizer

    def test_redact_and_map_phone(self):
        """Test that phone numbers are properly redacted and mapped"""
        text = "電話番号は 090-1234-5678 です"

        # Import the module to patch its variables directly
        from src.app.common import pii
        from src.app.common.pii import redact_and_map

        # Create mock objects
        mock_analyzer = MagicMock()
        mock_anonymizer = MagicMock()

        # Mock analyzer results
        mock_analyzer.analyze.return_value = [
            MagicMock(
                entity_type="PHONE_NUMBER",
                start=6,  # 090-1234-5678 starts at position 6
                end=19,   # 090-1234-5678 ends at position 19
                score=0.9,
            )
        ]

        # Mock anonymizer results
        mock_anonymizer.anonymize.return_value = MagicMock(
            text="電話番号は [PHONE_1] です",
            items=[
                MagicMock(
                    operator="replace",
                    start=6,
                    end=19,
                    text="[PHONE_1]",
                )
            ],
        )

        # Temporarily replace the module variables
        original_analyzer = pii.analyzer
        original_anonymizer = pii.anonymizer

        try:
            pii.analyzer = mock_analyzer
            pii.anonymizer = mock_anonymizer
            redacted_text, pii_map = redact_and_map(text)

            assert redacted_text == "電話番号は [PHONE_1] です"
            assert "[PHONE_1]" in pii_map
            assert pii_map["[PHONE_1]"] == "090-1234-5678"
        finally:
            # Restore original values
            pii.analyzer = original_analyzer
            pii.anonymizer = original_anonymizer

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
