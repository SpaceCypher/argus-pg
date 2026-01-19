import hashlib
import re


class Fingerprinter:
    """
    Normalizes and fingerprints SQL queries to ensure deterministic identification.
    Addresses whitespace, casing (partially), and comments.
    """

    # Regex to match SQL comments: -- ... or /* ... */
    _COMMENT_PATTERN = re.compile(
        r"(--[^\n\r]*)|(/\*[\s\S]*?\*/)",  # Match -- until end of line OR /* ... */
        re.MULTILINE,
    )

    # Regex to match whitespace sequences
    _WHITESPACE_PATTERN = re.compile(r"\s+")

    @classmethod
    def normalize(cls, sql: str) -> str:
        """
        Returns a normalized version of the SQL string:
        - Comments removed
        - Whitespace collapsed to single spaces
        - Stripped
        """
        # 1. Remove comments
        # Replace matches with empty string or space to prevent joining tokens.
        # Note: Removing -- comment might need newline check for terminator.
        # But usually collapsing whitespace handles the join.
        # Replacing blocks with space is safer.

        # Simple approach: Replace matches with a single space
        normalized = cls._COMMENT_PATTERN.sub(" ", sql)

        # 2. Collapse whitespace
        normalized = cls._WHITESPACE_PATTERN.sub(" ", normalized)

        # 3. Strip
        return normalized.strip()

    @classmethod
    def fingerprint(cls, sql: str) -> str:
        """
        Returns a SHA-256 hash of the normalized SQL.
        """
        normalized = cls.normalize(sql)
        # Encode to bytes
        encoded = normalized.encode("utf-8")
        # Hash
        return hashlib.sha256(encoded).hexdigest()
