#!/usr/bin/env python3
"""Manage AI Office account-to-system bindings in the Sushi user database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sushi-fast"))

from ai_office_gateway import (  # noqa: E402
    bind_account,
    ensure_access_schema,
    list_bindings,
    register_system,
    unbind_account,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    system = commands.add_parser("system", help="register or update a local dashboard system")
    system.add_argument("--id", required=True, dest="system_id")
    system.add_argument("--host", required=True, dest="hostname")
    system.add_argument("--label", required=True)
    system.add_argument("--upstream", required=True, dest="upstream_url")

    bind = commands.add_parser("bind", help="connect a Sushi account to a system")
    bind.add_argument("--email", required=True)
    bind.add_argument("--system", required=True, dest="system_id")
    bind.add_argument("--role", choices=("owner", "viewer"), default="viewer")

    unbind = commands.add_parser("unbind", help="remove an account-system connection")
    unbind.add_argument("--email", required=True)
    unbind.add_argument("--system", required=True, dest="system_id")

    commands.add_parser("list", help="list account-system connections")
    args = parser.parse_args()
    ensure_access_schema()

    if args.command == "system":
        register_system(args.system_id, args.hostname, args.label, args.upstream_url)
        print(f"Registered system: {args.system_id} ({args.hostname})")
    elif args.command == "bind":
        account_id = bind_account(args.email, args.system_id, args.role)
        print(f"Bound Sushi account ID {account_id} to {args.system_id} as {args.role}.")
    elif args.command == "unbind":
        if unbind_account(args.email, args.system_id):
            print(f"Removed binding for {args.email.strip().lower()} from {args.system_id}.")
        else:
            print("No matching binding found.")
    else:
        rows = list_bindings()
        if not rows:
            print("No account-system bindings.")
        for row in rows:
            state = "enabled" if row["enabled"] else "disabled"
            print(f"{row['email']} -> {row['system_id']} ({row['role']}, {state})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
