"""
Input sanitization and XSS protection

Provides comprehensive input sanitization to prevent:
- XSS (Cross-Site Scripting) attacks
- SQL injection
- Command injection
- Path traversal
"""

import re
import html
from typing import Any, Dict, List, Union, Optional
from loguru import logger
import bleach

class InputSanitizer:
    """Comprehensive input sanitization for security."""

    # Dangerous patterns to detect
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe',
        r'<object',
        r'<embed',
        r'<applet',
        r'<link',
        r'<style',
        r'<meta',
        r'<base',
        r'<form',
        r'data:text/html',
        r'vbscript:',
    ]

    # SQL injection patterns
    SQL_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bSELECT\b.*\bFROM\b.*\bWHERE\b)",
        r"(\bINSERT\b.*\bINTO\b.*\bVALUES\b)",
        r"(\bUPDATE\b.*\bSET\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bEXEC\b\()",
        r"(--\s*$)",
        r"(/\*.*\*/)",
        r"(\bOR\b.*=.*)",
        r"(\bAND\b.*=.*)",
        r"(;\s*\w+)",
    ]

    # Command injection patterns
    COMMAND_PATTERNS = [
        r'[;&|`$()]',
        r'\$\(.*\)',
        r'`.*`',
        r'\|\|',
        r'&&',
    ]

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r'\.\.',
        r'\./',
        r'/\.\.',
        r'~/',
    ]

    # Allowed HTML tags (if HTML is permitted)
    ALLOWED_TAGS = ['b', 'i', 'u', 'em', 'strong', 'p', 'br', 'a']
    ALLOWED_ATTRIBUTES = {'a': ['href', 'title']}

    @classmethod
    def sanitize_string(cls, value: str,
                       allow_html: bool = False,
                       max_length: Optional[int] = None,
                       strip_dangerous: bool = True) -> str:
        """
        Sanitize a string input.

        Args:
            value: Input string to sanitize
            allow_html: Whether to allow safe HTML tags
            max_length: Maximum allowed length
            strip_dangerous: Whether to strip dangerous patterns

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            value = str(value)

        # Trim whitespace
        value = value.strip()

        # Enforce max length
        if max_length and len(value) > max_length:
            value = value[:max_length]

        if strip_dangerous:
            # Check for dangerous patterns
            for pattern in cls.XSS_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE):
                    logger.warning(f"XSS pattern detected and removed: {pattern}")
                    value = re.sub(pattern, '', value, flags=re.IGNORECASE)

            for pattern in cls.SQL_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE):
                    logger.warning(f"SQL injection pattern detected: {pattern}")
                    # Don't auto-remove SQL patterns - just log and escape

            for pattern in cls.COMMAND_PATTERNS:
                if re.search(pattern, value):
                    logger.warning(f"Command injection pattern detected: {pattern}")

        # Handle HTML
        if allow_html:
            # Use bleach to clean HTML
            value = bleach.clean(
                value,
                tags=cls.ALLOWED_TAGS,
                attributes=cls.ALLOWED_ATTRIBUTES,
                strip=True
            )
        else:
            # Escape all HTML
            value = html.escape(value)

        return value

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any],
                     allow_html: bool = False,
                     max_string_length: Optional[int] = 1000) -> Dict[str, Any]:
        """
        Recursively sanitize dictionary values.

        Args:
            data: Dictionary to sanitize
            allow_html: Whether to allow safe HTML tags
            max_string_length: Maximum length for string values

        Returns:
            Sanitized dictionary
        """
        sanitized = {}

        for key, value in data.items():
            # Sanitize key
            clean_key = cls.sanitize_string(str(key), allow_html=False, max_length=100)

            # Sanitize value based on type
            if isinstance(value, str):
                sanitized[clean_key] = cls.sanitize_string(
                    value,
                    allow_html=allow_html,
                    max_length=max_string_length
                )
            elif isinstance(value, dict):
                sanitized[clean_key] = cls.sanitize_dict(
                    value,
                    allow_html=allow_html,
                    max_string_length=max_string_length
                )
            elif isinstance(value, list):
                sanitized[clean_key] = cls.sanitize_list(
                    value,
                    allow_html=allow_html,
                    max_string_length=max_string_length
                )
            else:
                # Numbers, booleans, None pass through
                sanitized[clean_key] = value

        return sanitized

    @classmethod
    def sanitize_list(cls, data: List[Any],
                     allow_html: bool = False,
                     max_string_length: Optional[int] = 1000) -> List[Any]:
        """
        Recursively sanitize list values.

        Args:
            data: List to sanitize
            allow_html: Whether to allow safe HTML tags
            max_string_length: Maximum length for string values

        Returns:
            Sanitized list
        """
        sanitized = []

        for value in data:
            if isinstance(value, str):
                sanitized.append(cls.sanitize_string(
                    value,
                    allow_html=allow_html,
                    max_length=max_string_length
                ))
            elif isinstance(value, dict):
                sanitized.append(cls.sanitize_dict(
                    value,
                    allow_html=allow_html,
                    max_string_length=max_string_length
                ))
            elif isinstance(value, list):
                sanitized.append(cls.sanitize_list(
                    value,
                    allow_html=allow_html,
                    max_string_length=max_string_length
                ))
            else:
                sanitized.append(value)

        return sanitized

    @classmethod
    def validate_filename(cls, filename: str) -> str:
        """
        Validate and sanitize filename.

        Args:
            filename: Input filename

        Returns:
            Sanitized filename

        Raises:
            ValueError: If filename is invalid
        """
        if not filename:
            raise ValueError("Filename cannot be empty")

        # Remove path components
        filename = filename.split('/')[-1].split('\\')[-1]

        # Check for path traversal
        for pattern in cls.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, filename):
                raise ValueError(f"Invalid filename: path traversal detected")

        # Remove dangerous characters
        filename = re.sub(r'[^\w\s\-\.]', '', filename)

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + ('.' + ext if ext else '')

        if not filename:
            raise ValueError("Filename becomes empty after sanitization")

        return filename

    @classmethod
    def detect_sql_injection(cls, value: str) -> bool:
        """
        Detect potential SQL injection attempts.

        Args:
            value: String to check

        Returns:
            True if SQL injection detected, False otherwise
        """
        for pattern in cls.SQL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {pattern}")
                return True
        return False

    @classmethod
    def detect_xss(cls, value: str) -> bool:
        """
        Detect potential XSS attempts.

        Args:
            value: String to check

        Returns:
            True if XSS detected, False otherwise
        """
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential XSS detected: {pattern}")
                return True
        return False


# Convenience functions
def sanitize_string(value: str, allow_html: bool = False, max_length: Optional[int] = None) -> str:
    """Convenience function to sanitize a string."""
    return InputSanitizer.sanitize_string(value, allow_html=allow_html, max_length=max_length)


def sanitize_dict(data: Dict[str, Any], allow_html: bool = False) -> Dict[str, Any]:
    """Convenience function to sanitize a dictionary."""
    return InputSanitizer.sanitize_dict(data, allow_html=allow_html)
