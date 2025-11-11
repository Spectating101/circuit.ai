"""
SQL Injection Protection

Provides SQL injection protection through:
- Query parameter validation
- Safe query builder helpers
- Detection of SQL injection patterns
"""

import re
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from loguru import logger

class SQLProtector:
    """SQL injection protection utilities."""

    # Dangerous SQL keywords
    DANGEROUS_KEYWORDS = [
        'DROP', 'DELETE', 'INSERT', 'UPDATE', 'EXEC', 'EXECUTE',
        'UNION', 'ALTER', 'CREATE', 'GRANT', 'REVOKE', 'TRUNCATE'
    ]

    # SQL injection patterns
    INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bSELECT\b.*\bFROM\b.*\bWHERE\b.*\bOR\b.*=)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bEXEC\b\s*\()",
        r"(--.*$)",
        r"(/\*.*\*/)",
        r"(;\s*\w+\s*\()",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"(\bAND\b\s+\d+\s*=\s*\d+)",
    ]

    @classmethod
    def validate_identifier(cls, identifier: str, max_length: int = 64) -> bool:
        """
        Validate SQL identifier (table name, column name, etc).

        Args:
            identifier: Identifier to validate
            max_length: Maximum allowed length

        Returns:
            True if valid, False otherwise
        """
        if not identifier:
            return False

        # Check length
        if len(identifier) > max_length:
            logger.warning(f"SQL identifier too long: {len(identifier)} > {max_length}")
            return False

        # Only allow alphanumeric and underscore
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
            logger.warning(f"Invalid SQL identifier format: {identifier}")
            return False

        # Check for dangerous keywords
        if identifier.upper() in cls.DANGEROUS_KEYWORDS:
            logger.warning(f"Dangerous SQL keyword used as identifier: {identifier}")
            return False

        return True

    @classmethod
    def validate_value(cls, value: str) -> bool:
        """
        Validate user input value for SQL injection patterns.

        Args:
            value: Value to validate

        Returns:
            True if safe, False if potential injection detected
        """
        if not isinstance(value, str):
            return True  # Non-string values are generally safe

        # Check for SQL injection patterns
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {pattern} in '{value}'")
                return False

        return True

    @classmethod
    def validate_query_params(cls, params: Dict[str, Any]) -> bool:
        """
        Validate all query parameters.

        Args:
            params: Dictionary of query parameters

        Returns:
            True if all safe, False if any potential injection
        """
        for key, value in params.items():
            # Validate key (should be identifier)
            if not cls.validate_identifier(key):
                return False

            # Validate value
            if isinstance(value, str):
                if not cls.validate_value(value):
                    return False
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, str) and not cls.validate_value(item):
                        return False

        return True

    @classmethod
    def safe_like_pattern(cls, value: str) -> str:
        """
        Escape LIKE pattern special characters.

        Args:
            value: Value to escape

        Returns:
            Escaped value safe for LIKE queries
        """
        # Escape special LIKE characters
        value = value.replace('\\', '\\\\')  # Escape backslash first
        value = value.replace('%', '\\%')
        value = value.replace('_', '\\_')
        return value

    @classmethod
    def build_safe_where_clause(cls, conditions: Dict[str, Any]) -> tuple:
        """
        Build a safe WHERE clause with parameterized values.

        Args:
            conditions: Dictionary of column: value pairs

        Returns:
            Tuple of (where_clause, params)
        """
        if not conditions:
            return "", {}

        where_parts = []
        params = {}

        for column, value in conditions.items():
            # Validate column name
            if not cls.validate_identifier(column):
                logger.error(f"Invalid column name: {column}")
                continue

            param_name = f"param_{column}"

            if value is None:
                where_parts.append(f"{column} IS NULL")
            elif isinstance(value, (list, tuple)):
                # IN clause
                where_parts.append(f"{column} IN :{param_name}")
                params[param_name] = value
            else:
                where_parts.append(f"{column} = :{param_name}")
                params[param_name] = value

        where_clause = " AND ".join(where_parts)
        return where_clause, params


def validate_query_params(params: Dict[str, Any]) -> bool:
    """Convenience function to validate query parameters."""
    return SQLProtector.validate_query_params(params)
