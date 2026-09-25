"""
Password hashing and JWT signing/verification for the Identity Service.

RS256 (default): the Identity Service signs tokens with its private key and publishes
the public key at /.well-known/jwks.json, so the API Gateway and other services can
verify tokens without being able to issue them.
HS256: shared-secret signing, kept for simple local setups.
"""
import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import bcrypt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.core.config import Settings, get_settings
from app.core.time import utc_now

logger = logging.getLogger("identity.security")

# bcrypt only uses the first 72 bytes of a password; longer input is rejected explicitly.
BCRYPT_MAX_PASSWORD_BYTES = 72


# ---------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must not exceed {BCRYPT_MAX_PASSWORD_BYTES} bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))


# A real bcrypt hash used to keep login timing uniform when the account does not exist.
_TIMING_EQUALIZER_HASH = bcrypt.hashpw(b"timing-equalizer", bcrypt.gensalt()).decode("utf-8")


def burn_password_check() -> None:
    bcrypt.checkpw(b"not-the-password", _TIMING_EQUALIZER_HASH.encode("utf-8"))


# ---------------------------------------------------------------- signing keys

def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class SigningKeys:
    algorithm: str
    signing_key: str
    verification_key: str
    key_id: Optional[str]
    public_jwk: Optional[Dict[str, str]]


def _rsa_keys_from_files(settings: Settings) -> tuple:
    private_pem = Path(settings.jwt_private_key_path).read_bytes()
    public_pem = Path(settings.jwt_public_key_path).read_bytes()
    return private_pem, public_pem


def _ephemeral_rsa_keys() -> tuple:
    logger.warning(
        "JWT_PRIVATE_KEY_PATH/JWT_PUBLIC_KEY_PATH not set: using an ephemeral RSA key pair. "
        "Tokens become invalid on restart. Run scripts/generate_jwt_keys.py for a persistent key."
    )
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_pem, public_pem


def _public_jwk(public_pem: bytes) -> Dict[str, str]:
    numbers = serialization.load_pem_public_key(public_pem).public_numbers()
    jwk = {"e": _b64url_uint(numbers.e), "kty": "RSA", "n": _b64url_uint(numbers.n)}
    # RFC 7638 thumbprint as a stable key ID
    thumbprint = hashlib.sha256(json.dumps(jwk, separators=(",", ":"), sort_keys=True).encode()).digest()
    kid = base64.urlsafe_b64encode(thumbprint).rstrip(b"=").decode("ascii")
    return {**jwk, "kid": kid, "use": "sig", "alg": "RS256"}


@lru_cache
def get_signing_keys() -> SigningKeys:
    settings = get_settings()
    if settings.jwt_algorithm == "HS256":
        return SigningKeys("HS256", settings.jwt_secret_key, settings.jwt_secret_key, None, None)

    if settings.jwt_private_key_path and settings.jwt_public_key_path:
        private_pem, public_pem = _rsa_keys_from_files(settings)
    else:
        private_pem, public_pem = _ephemeral_rsa_keys()

    jwk = _public_jwk(public_pem)
    return SigningKeys("RS256", private_pem.decode(), public_pem.decode(), jwk["kid"], jwk)


def jwks() -> Dict[str, List[Dict[str, str]]]:
    keys = get_signing_keys()
    return {"keys": [keys.public_jwk] if keys.public_jwk else []}


# ---------------------------------------------------------------- tokens

def encode_token(claims: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Sign a token, adding the standard iss/aud/iat/exp claims."""
    settings = get_settings()
    keys = get_signing_keys()
    now = utc_now()
    to_encode = dict(claims)
    to_encode.update({
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes)),
    })
    headers = {"kid": keys.key_id} if keys.key_id else None
    return jwt.encode(to_encode, keys.signing_key, algorithm=keys.algorithm, headers=headers)


def decode_token(token: str) -> Dict[str, Any]:
    """Verify signature, expiry, issuer and audience. Raises jose.JWTError on failure."""
    settings = get_settings()
    keys = get_signing_keys()
    return jwt.decode(
        token,
        keys.verification_key,
        algorithms=[keys.algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )
