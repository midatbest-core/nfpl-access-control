"""Credential generation and one-way token hashing."""

from __future__ import annotations

import hashlib
import secrets

TOKEN_PREFIX = "nfpl_"


def generate_api_token() -> str:
    """Return a high-entropy bearer credential.

    The plaintext token is intended to be shown once; only its digest is persisted.
    """

    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_token(token: str) -> str:
    """Return a deterministic SHA-256 digest suitable for indexed lookup."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()
