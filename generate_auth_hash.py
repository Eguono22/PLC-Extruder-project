#!/usr/bin/env python3
"""Generate a SHA-256 digest for EXTRUDER_AUTH_PASSWORD_SHA256."""

from __future__ import annotations

import argparse
import getpass

from extruder_app.production import sha256_password_digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a SHA-256 digest for the extruder app auth password.",
    )
    parser.add_argument(
        "password",
        nargs="?",
        help="Optional plaintext password. If omitted, the script prompts securely.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    password = args.password or getpass.getpass("Password: ")
    print(sha256_password_digest(password))


if __name__ == "__main__":
    main()
