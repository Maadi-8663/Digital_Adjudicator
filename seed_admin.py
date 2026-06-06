"""Create an admin user. Run once.

Usage:
    python seed_admin.py
"""

import getpass
import sys

from app import create_app, db
from app.models import User

app = create_app()


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def main() -> None:
    print("\n  Digital Adjudicator  -  Admin seeder\n")

    with app.app_context():
        existing_admins = User.query.filter_by(role="admin").count()
        if existing_admins:
            print(f"  Note: {existing_admins} admin(s) already exist.\n")

        full_name = prompt("Full name", "Tournament Admin")
        username = prompt("Username", "admin")

        if User.query.filter_by(username=username).first():
            print(f"  ! Username '{username}' is already taken.")
            sys.exit(1)

        email = prompt("Email", "admin@uet.edu.pk")
        if User.query.filter_by(email=email.lower()).first():
            print(f"  ! Email '{email}' is already registered.")
            sys.exit(1)

        institution = prompt("Institution", "UET Lahore - New Campus")
        password = getpass.getpass("Password (hidden): ")
        if not password or len(password) < 6:
            print("  ! Password must be at least six characters.")
            sys.exit(1)

        admin = User(
            username=username,
            email=email.lower(),
            full_name=full_name,
            institution=institution,
            role="admin",
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        print(f"\n  Admin '{username}' created. You can sign in at /auth/login\n")


if __name__ == "__main__":
    main()
