"""
Security module for Circuit.AI

Provides comprehensive security features:
- File upload validation
- Input sanitization
- XSS protection
- SQL injection protection
- Rate limiting
- Request size limits
"""

from .file_validator import FileValidator, validate_upload_file
from .input_sanitizer import InputSanitizer, sanitize_string, sanitize_dict
from .rate_limiter import IPRateLimiter, get_client_ip
from .xss_protection import XSSProtector, clean_html
from .sql_protection import SQLProtector, validate_query_params

__all__ = [
    "FileValidator",
    "validate_upload_file",
    "InputSanitizer",
    "sanitize_string",
    "sanitize_dict",
    "IPRateLimiter",
    "get_client_ip",
    "XSSProtector",
    "clean_html",
    "SQLProtector",
    "validate_query_params",
]
