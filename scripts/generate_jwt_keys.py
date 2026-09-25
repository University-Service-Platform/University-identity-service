"""
Generate an RSA key pair for signing Identity Service JWTs (RS256).

    python scripts/generate_jwt_keys.py [output_dir]     # default: keys/

Then set JWT_PRIVATE_KEY_PATH and JWT_PUBLIC_KEY_PATH to the generated files.
The keys/ directory is git-ignored: never commit private keys. Only the public key
(also served at /.well-known/jwks.json) may be shared with other services.
"""
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    output_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "keys")
    output_dir.mkdir(parents=True, exist_ok=True)
    private_path = output_dir / "jwt_private.pem"
    public_path = output_dir / "jwt_public.pem"

    if private_path.exists():
        sys.exit(f"{private_path} already exists; refusing to overwrite an existing signing key.")

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.write_bytes(private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ))
    public_path.write_bytes(private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ))
    print(f"Wrote {private_path} and {public_path}")


if __name__ == "__main__":
    main()
