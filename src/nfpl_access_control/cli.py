"""Local administrative setup commands."""

from __future__ import annotations

import argparse
import getpass

from nfpl_access_control.db.session import SessionLocal
from nfpl_access_control.services.bootstrap import BootstrapError, bootstrap_first_admin


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the first NFPL Admin.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--branch-code", required=True)
    parser.add_argument("--branch-name", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords do not match.")
    try:
        with SessionLocal.begin() as session:
            user = bootstrap_first_admin(
                session,
                display_name=args.name,
                email=args.email,
                password=password,
                branch_code=args.branch_code,
                branch_name=args.branch_name,
            )
            user_id = user.id
    except BootstrapError as error:
        parser.error(str(error))
    print(f"Created first Admin {user_id}.")
