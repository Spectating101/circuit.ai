"""
XSS (Cross-Site Scripting) Protection

Provides comprehensive XSS protection:
- HTML sanitization
- Content Security Policy helpers
- Safe JSON encoding
"""

import json
import html
from typing import Any, Dict
import bleach
from loguru import logger

class XSSProtector:
    """XSS protection utilities."""

    # Safe HTML tags for user content
    SAFE_TAGS = [
        'a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
        'em', 'i', 'li', 'ol', 'strong', 'ul', 'p', 'br',
        'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'pre', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
    ]

    SAFE_ATTRIBUTES = {
        'a': ['href', 'title', 'rel'],
        'abbr': ['title'],
        'acronym': ['title'],
        '*': ['class']  # Allow class on all elements
    }

    SAFE_PROTOCOLS = ['http', 'https', 'mailto']

    @classmethod
    def clean_html(cls, content: str, strict: bool = False) -> str:
        """
        Clean HTML content to prevent XSS.

        Args:
            content: HTML content to clean
            strict: If True, only allow minimal tags

        Returns:
            Cleaned HTML content
        """
        if not content:
            return ''

        tags = [] if strict else cls.SAFE_TAGS
        attributes = {} if strict else cls.SAFE_ATTRIBUTES

        try:
            cleaned = bleach.clean(
                content,
                tags=tags,
                attributes=attributes,
                protocols=cls.SAFE_PROTOCOLS,
                strip=True
            )

            # Additional cleanup - remove empty tags
            cleaned = bleach.linkify(cleaned, parse_email=True)

            return cleaned

        except Exception as e:
            logger.error(f"Error cleaning HTML: {e}")
            # Fall back to escaping everything
            return html.escape(content)

    @classmethod
    def escape_for_js(cls, value: Any) -> str:
        """
        Escape value for safe insertion into JavaScript.

        Args:
            value: Value to escape

        Returns:
            JSON-encoded, escaped string
        """
        # Use JSON encoding which is safe for JS
        return json.dumps(value)

    @classmethod
    def get_csp_header(cls, strict: bool = True) -> Dict[str, str]:
        """
        Get Content Security Policy headers.

        Args:
            strict: If True, use strict CSP

        Returns:
            Dictionary of CSP headers
        """
        if strict:
            csp_value = "; ".join([
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self' 'unsafe-inline'",  # Allow inline styles for Tailwind
                "img-src 'self' data: https:",
                "font-src 'self'",
                "connect-src 'self'",
                "frame-ancestors 'none'",
                "base-uri 'self'",
                "form-action 'self'"
            ])
        else:
            # Less strict for development
            csp_value = "; ".join([
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: https:",
                "font-src 'self' data:",
                "connect-src 'self' ws: wss:",
                "frame-ancestors 'self'"
            ])

        return {
            "Content-Security-Policy": csp_value,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }


def clean_html(content: str, strict: bool = False) -> str:
    """Convenience function to clean HTML."""
    return XSSProtector.clean_html(content, strict)
