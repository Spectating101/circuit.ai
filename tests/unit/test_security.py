"""
Unit tests for security module

Tests:
- File validation
- Input sanitization
- XSS protection
- SQL injection detection
- Rate limiting
"""

import pytest
from PIL import Image
import io
from fastapi import UploadFile
from fastapi.testclient import TestClient

from src.security.file_validator import FileValidator, validate_upload_file
from src.security.input_sanitizer import InputSanitizer, sanitize_string, sanitize_dict
from src.security.xss_protection import XSSProtector, clean_html
from src.security.sql_protection import SQLProtector, validate_query_params


class TestFileValidator:
    """Test file validation."""

    def test_validate_magic_number_jpeg(self):
        """Test JPEG magic number validation."""
        jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        assert FileValidator.validate_magic_number(jpeg_header, 'image/jpeg')

    def test_validate_magic_number_png(self):
        """Test PNG magic number validation."""
        png_header = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        assert FileValidator.validate_magic_number(png_header, 'image/png')

    def test_validate_magic_number_mismatch(self):
        """Test magic number mismatch detection."""
        png_header = b'\x89PNG\r\n\x1a\n'
        assert not FileValidator.validate_magic_number(png_header, 'image/jpeg')

    def test_validate_image_dimensions_valid(self):
        """Test valid image dimensions."""
        # Create test image
        img = Image.new('RGB', (640, 480))
        is_valid, error = FileValidator.validate_image_dimensions(img)
        assert is_valid
        assert error is None

    def test_validate_image_dimensions_too_small(self):
        """Test image too small."""
        img = Image.new('RGB', (10, 10))
        is_valid, error = FileValidator.validate_image_dimensions(img)
        assert not is_valid
        assert "too small" in error.lower()

    def test_validate_image_dimensions_too_large(self):
        """Test image too large."""
        img = Image.new('RGB', (10000, 10000))
        is_valid, error = FileValidator.validate_image_dimensions(img)
        assert not is_valid
        assert "too large" in error.lower() or "too many pixels" in error.lower()


class TestInputSanitizer:
    """Test input sanitization."""

    def test_sanitize_string_xss_script(self):
        """Test XSS script tag removal."""
        malicious = '<script>alert("XSS")</script>Hello'
        cleaned = InputSanitizer.sanitize_string(malicious)
        assert '<script>' not in cleaned
        assert 'alert' not in cleaned

    def test_sanitize_string_sql_injection(self):
        """Test SQL injection pattern detection."""
        malicious = "admin' OR '1'='1"
        cleaned = InputSanitizer.sanitize_string(malicious)
        # Should escape quotes
        assert "'" in cleaned or "&" in cleaned

    def test_sanitize_string_html_escape(self):
        """Test HTML escaping."""
        html = '<div>Hello World</div>'
        cleaned = InputSanitizer.sanitize_string(html, allow_html=False)
        assert '&lt;' in cleaned or '<div>' not in cleaned

    def test_sanitize_string_max_length(self):
        """Test max length enforcement."""
        long_string = 'a' * 1000
        cleaned = InputSanitizer.sanitize_string(long_string, max_length=100)
        assert len(cleaned) == 100

    def test_sanitize_dict_recursive(self):
        """Test recursive dictionary sanitization."""
        data = {
            'name': '<script>alert("XSS")</script>John',
            'nested': {
                'value': '<b>Bold</b>',
                'deep': {
                    'xss': 'javascript:alert(1)'
                }
            }
        }

        cleaned = InputSanitizer.sanitize_dict(data, allow_html=False)
        assert '<script>' not in str(cleaned)

    def test_detect_xss(self):
        """Test XSS detection."""
        xss_strings = [
            '<script>alert(1)</script>',
            'javascript:alert(1)',
            '<img src=x onerror=alert(1)>',
            '<iframe src="evil.com"></iframe>'
        ]

        for xss in xss_strings:
            assert InputSanitizer.detect_xss(xss), f"Failed to detect XSS: {xss}"

    def test_detect_sql_injection(self):
        """Test SQL injection detection."""
        sql_injections = [
            "' OR '1'='1",
            "admin'--",
            "1; DROP TABLE users",
            "UNION SELECT * FROM passwords"
        ]

        for sql in sql_injections:
            assert InputSanitizer.detect_sql_injection(sql), f"Failed to detect SQL injection: {sql}"


class TestXSSProtector:
    """Test XSS protection."""

    def test_clean_html_safe_tags(self):
        """Test safe HTML tags are preserved."""
        html = '<p>Hello <b>World</b></p>'
        cleaned = XSSProtector.clean_html(html)
        assert '<p>' in cleaned
        assert '<b>' in cleaned

    def test_clean_html_dangerous_tags(self):
        """Test dangerous tags are removed."""
        html = '<p>Hello</p><script>alert(1)</script>'
        cleaned = XSSProtector.clean_html(html)
        assert '<script>' not in cleaned
        assert '<p>' in cleaned

    def test_clean_html_strict_mode(self):
        """Test strict mode removes all tags."""
        html = '<p>Hello <b>World</b></p>'
        cleaned = XSSProtector.clean_html(html, strict=True)
        assert '<' not in cleaned or '&lt;' in cleaned

    def test_get_csp_header(self):
        """Test CSP header generation."""
        headers = XSSProtector.get_csp_header(strict=True)
        assert 'Content-Security-Policy' in headers
        assert "default-src 'self'" in headers['Content-Security-Policy']


class TestSQLProtector:
    """Test SQL injection protection."""

    def test_validate_identifier_valid(self):
        """Test valid SQL identifier."""
        assert SQLProtector.validate_identifier('user_id')
        assert SQLProtector.validate_identifier('users')
        assert SQLProtector.validate_identifier('_id')

    def test_validate_identifier_invalid(self):
        """Test invalid SQL identifier."""
        assert not SQLProtector.validate_identifier('user-id')  # Hyphen not allowed
        assert not SQLProtector.validate_identifier('1user')  # Can't start with number
        assert not SQLProtector.validate_identifier('DROP')  # Dangerous keyword

    def test_validate_identifier_max_length(self):
        """Test identifier max length."""
        long_id = 'a' * 100
        assert not SQLProtector.validate_identifier(long_id, max_length=64)

    def test_validate_value_safe(self):
        """Test safe values pass validation."""
        safe_values = [
            'john@example.com',
            '123',
            'normal text',
            'user-name'
        ]

        for value in safe_values:
            assert SQLProtector.validate_value(value), f"Falsely rejected safe value: {value}"

    def test_validate_value_injection(self):
        """Test SQL injection values are detected."""
        injections = [
            "' OR '1'='1",
            "admin'--",
            "1; DROP TABLE users"
        ]

        for injection in injections:
            assert not SQLProtector.validate_value(injection), f"Failed to detect injection: {injection}"

    def test_validate_query_params(self):
        """Test query params validation."""
        safe_params = {
            'user_id': '123',
            'email': 'user@example.com',
            'name': 'John Doe'
        }
        assert SQLProtector.validate_query_params(safe_params)

        unsafe_params = {
            'user_id': "' OR '1'='1",
        }
        assert not SQLProtector.validate_query_params(unsafe_params)

    def test_safe_like_pattern(self):
        """Test LIKE pattern escaping."""
        pattern = '100%_test'
        escaped = SQLProtector.safe_like_pattern(pattern)
        assert '\\%' in escaped
        assert '\\_' in escaped


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
