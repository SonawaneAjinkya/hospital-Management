"""
Creates default login accounts, one per role, for first-time setup / demo.

⚠️ CHANGE THESE PASSWORDS before using this in anything real — these are
   here so you can log in and try the system immediately.

Run: python3 data/seed_users.py   (from the project root)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
import auth  # noqa: E402

DEFAULT_USERS = [
    ("reception1", "Recep@123", "receptionist", "Front Desk Receptionist"),
    ("medstaff1", "MedStaff@123", "medical_staff", "Pharmacy / Medical Staff"),
    ("admin1", "Admin@123", "admin", "Hospital Administrator"),
]

if __name__ == "__main__":
    print("Seeding default users...\n")
    for username, password, role, full_name in DEFAULT_USERS:
        try:
            result = auth.create_user(username, password, role, full_name)
            print(f"  Created: {result['username']} ({result['role']}) — password: {password}")
        except ValueError as e:
            print(f"  Skipped {username}: {e}")

    print("\nDone. Log in with any of the above at the dashboard's login screen.")
    print("⚠️  Change these passwords before real-world use — see shared/auth.py's change_password().")
