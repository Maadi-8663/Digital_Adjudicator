"""Seed test users for all three roles.

Usage:
    python seed_test_users.py

Creates one admin, one judge, one participant with simple passwords for testing.
Safe to run multiple times - skips users that already exist.
"""

from app import create_app, db
from app.models import User

app = create_app()

TEST_USERS = [
    {
        "username": "admin",
        "password": "admin12345",
        "full_name": "Competition Admin",
        "email": "admin@uet.edu.pk",
        "institution": "UET Lahore - New Campus",
        "role": "admin",
        "department": "Literary and Debating Society",
    },
    {
        "username": "judge",
        "password": "judge12345",
        "full_name": "Sir Usman Ghani",
        "email": "judge@uet.edu.pk",
        "institution": "UET Lahore - New Campus",
        "role": "judge",
        "experience": "Senior",
    },
    {
        "username": "zahra",
        "password": "zahra12345",
        "full_name": "Syeda Gul e Zahra Batool Bukhari",
        "email": "zahra@uet.edu.pk",
        "institution": "UET Lahore - New Campus",
        "team_name": "Team Alpha",
        "role": "participant",
    },
]


def main() -> None:
    print("\n  Digital Adjudicator  -  Test user seeder\n")

    with app.app_context():
        created, skipped = 0, 0
        for data in TEST_USERS:
            existing = User.query.filter_by(username=data["username"]).first()
            if existing:
                print(f"  - {data['username']:<10s} ({data['role']}) already exists, skipping")
                skipped += 1
                continue

            password = data.pop("password")
            user = User(**data)
            user.set_password(password)
            db.session.add(user)
            print(f"  + {data['username']:<10s} ({data['role']}) created")
            created += 1

        db.session.commit()
        print(f"\n  Done. {created} created, {skipped} skipped.\n")
        print("  Sign in at http://localhost:5000/auth/login")
        print("  ----------------------------------------")
        print("    admin    /  admin12345")
        print("    judge    /  judge12345")
        print("    zahra    /  zahra12345")
        print()


if __name__ == "__main__":
    main()
