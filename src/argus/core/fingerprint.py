import hashlib
import logging
import re

import sqlglot

logger = logging.getLogger(__name__)


class Fingerprinter:
    """
    Normalizes and fingerprints SQL queries to ensure deterministic identification.
    Uses sqlglot AST normalization with regex fallback.
    """

    _COMMENT_PATTERN = re.compile(
        r"(--[^\n\r]*)|(/\*[\s\S]*?\*/)",
        re.MULTILINE,
    )
    _WHITESPACE_PATTERN = re.compile(r"\s+")

    @classmethod
    def normalize(cls, sql: str) -> str:
        """
        Returns a normalized version of the SQL string:
        - Parsed and formatted via sqlglot (if possible)
        - Comments removed
        - Whitespace collapsed
        """
        try:
            # Parse with sqlglot and generate clean canonical SQL
            parsed = sqlglot.parse_one(sql, read="postgres")
            return parsed.sql(
                dialect="postgres", comments=False, normalize=True
            ).strip()
        except Exception:
            # Fallback regex normalization
            normalized = cls._COMMENT_PATTERN.sub(" ", sql)
            normalized = cls._WHITESPACE_PATTERN.sub(" ", normalized)
            return normalized.strip()

    @classmethod
    def fingerprint(cls, sql: str) -> str:
        """
        Returns a SHA-256 hash of the normalized SQL.
        """
        normalized = cls.normalize(sql)
        encoded = normalized.encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
