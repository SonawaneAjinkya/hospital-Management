"""
Authentication + role-based access control.

Roles:
  - receptionist  : patient admission/discharge, bed allocation/availability
  - medical_staff : medicine intake (restock) and outgoing (dispense) records
  - admin         : full access to everything, including user management

Passwords are hashed with PBKDF2-HMAC-SHA256 (Python's stdlib `hashlib`,
no extra dependency needed) — never store or compare plain-text passwords.
"""

import sqlite3
import os
import hashlib
import secrets

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "hospital.db")

ROLES = ["receptionist", "medical_staff", "admin"]

# What each role is allowed to see/do in the dashboard. The dashboard reads
# this to decide which sections to render — single source of truth for
# permissions instead of scattering role checks everywhere.
PERMISSIONS = {
    "receptionist": {"patients", "beds"},
    "medical_staff": {"medicines"},
    "admin": {"patients", "beds", "medicines", "staff", "forecast", "user_management"},
}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return pwd_hash, salt


def create_user(username, password, role, full_name):
    if role not in ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of {ROLES}")

    pwd_hash, salt = _hash_password(password)
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO users (username, password_hash, salt, role, full_name, active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (username, pwd_hash, salt, role, full_name),
        )
        conn.commit()
        return {"user_id": cur.lastrowid, "username": username, "role": role}
    except sqlite3.IntegrityError:
        raise ValueError(f"Username '{username}' already exists")
    finally:
        conn.close()


def authenticate(username, password):
    """Returns the user dict (without password fields) if valid + active, else None."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, username, password_hash, salt, role, full_name, active FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if row is None:
            return None

        user_id, uname, stored_hash, salt, role, full_name, active = row
        if not active:
            return None

        check_hash, _ = _hash_password(password, salt)
        if check_hash != stored_hash:
            return None

        return {"user_id": user_id, "username": uname, "role": role, "full_name": full_name}
    finally:
        conn.close()


def change_password(username, new_password):
    pwd_hash, salt = _hash_password(new_password)
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
            (pwd_hash, salt, username),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"No user found with username '{username}'")
    finally:
        conn.close()


def set_active(username, active: bool):
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET active = ? WHERE username = ?", (int(active), username))
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"No user found with username '{username}'")
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Returns the user dict (role included) for a given user_id, or None."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, username, role, full_name, active FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        user_id, username, role, full_name, active = row
        return {"user_id": user_id, "username": username, "role": role, "full_name": full_name, "active": bool(active)}
    finally:
        conn.close()


def list_users():
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id, username, role, full_name, active, created_at FROM users ORDER BY user_id")
        cols = ["user_id", "username", "role", "full_name", "active", "created_at"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def has_permission(role, section):
    return section in PERMISSIONS.get(role, set())
