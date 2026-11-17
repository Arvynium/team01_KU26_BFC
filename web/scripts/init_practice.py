from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


def main() -> None:
    values = {
        "BFC_BIND_IP": "127.0.0.1",
        "BFC_PORT": "3000",
        "LAB_SQL_FLAG": f"FLAG{{practice_sql_{secrets.token_hex(16)}}}",
        "LAB_PATH_FLAG": f"FLAG{{practice_path_{secrets.token_hex(16)}}}",
        "LAB_XSS_FLAG": f"FLAG{{practice_xss_{secrets.token_hex(16)}}}",
        "LAB_COMMAND_FLAG": f"FLAG{{practice_command_{secrets.token_hex(16)}}}",
        "LAB_REVIEW_SECRET": secrets.token_hex(32),
    }
    try:
        descriptor = os.open(ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(".env already exists; existing values were not changed.")
        return
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.writelines(f"{key}={value}\n" for key, value in values.items())
    print("Created a private .env for this local practice instance.")


if __name__ == "__main__":
    main()
