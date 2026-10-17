"""Credential generation and one-way token hashing."""

from __future__ import annotations

import hashlib
import hmac
import secrets

TOKEN_PREFIX = "nfpl_"
PASSWORD_ALGORITHM = "scrypt"
PASSWORD_N = 2**14
PASSWORD_R = 8
PASSWORD_P = 1
PASSWORD_DKLEN = 32


def generate_api_token() -> str:
    """Return a high-entropy bearer credential.

    The plaintext token is intended to be shown once; only its digest is persisted.
    """

    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_token(token: str) -> str:
    """Return a deterministic SHA-256 digest suitable for indexed lookup."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """Encode a password with a unique salt and memory-hard scrypt."""

    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_N,
        r=PASSWORD_R,
        p=PASSWORD_P,
        dklen=PASSWORD_DKLEN,
    )
    return (
        f"{PASSWORD_ALGORITHM}${PASSWORD_N}${PASSWORD_R}${PASSWORD_P}${salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    """Verify a stored scrypt encoding, failing closed for malformed data."""

    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(expected)),
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError, MemoryError):
        return False
