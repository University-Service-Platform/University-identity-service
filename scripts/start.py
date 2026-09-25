"""
Container entrypoint: migrate, seed, then serve.

    1. alembic upgrade head          (schema)
    2. python -m app.seed [--demo]   (reference data; demo users when SEED_DEMO_DATA=true)
    3. uvicorn app.main:app          (replaces this process)

Written in Python rather than shell so it behaves the same on every platform.
"""
import os
import subprocess
import sys


def run(*command: str) -> None:
    print(f"[start] {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    run(sys.executable, "-m", "alembic", "upgrade", "head")

    seed = [sys.executable, "-m", "app.seed"]
    if os.getenv("SEED_DEMO_DATA", "false").lower() == "true":
        seed.append("--demo")
    run(*seed)

    port = os.getenv("PORT", "8001")
    print(f"[start] serving on port {port}", flush=True)
    os.execvp(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app",
                               "--host", "0.0.0.0", "--port", port, "--proxy-headers"])


if __name__ == "__main__":
    main()
