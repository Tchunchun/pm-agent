"""
User store — JSON-backed persistence for user accounts.

File: data/users.json
Uses atomic writes consistent with StorageManager patterns.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import DATA_DIR


USERS_FILE = DATA_DIR / "users.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, data: list[dict]) -> None:
    """Write JSON to a temp file then atomically rename to target."""
    dir_ = path.parent
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _load_users() -> list[dict]:
    """Load all users from the JSON file."""
    if not USERS_FILE.exists():
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_users(users: list[dict]) -> None:
    """Persist users list to disk."""
    _atomic_write(USERS_FILE, users)


def find_user_by_email(email: str) -> Optional[dict]:
    """Look up a user by email address. Returns None if not found."""
    email_lower = email.lower()
    for user in _load_users():
        if user.get("email", "").lower() == email_lower:
            return user
    return None


def find_user_by_google_id(google_id: str) -> Optional[dict]:
    """Look up a user by Google sub (subject) ID. Returns None if not found."""
    for user in _load_users():
        if user.get("google_id") == google_id:
            return user
    return None


def upsert_user(google_info: dict) -> dict:
    """
    Create or update a user from Google profile info.

    Args:
        google_info: Dict from Google userinfo endpoint with keys:
                     sub, email, name, picture, given_name, family_name

    Returns:
        The created or updated user dict.
    """
    users = _load_users()
    google_id = google_info.get("sub", "")
    email = google_info.get("email", "").lower()
    now = _now_iso()

    # Find existing user by Google ID or email
    existing_idx = None
    for i, u in enumerate(users):
        if u.get("google_id") == google_id or u.get("email", "").lower() == email:
            existing_idx = i
            break

    user_data = {
        "google_id": google_id,
        "email": email,
        "name": google_info.get("name", ""),
        "given_name": google_info.get("given_name", ""),
        "family_name": google_info.get("family_name", ""),
        "picture": google_info.get("picture", ""),
        "email_verified": google_info.get("email_verified", False),
        "last_login": now,
    }

    if existing_idx is not None:
        # Update existing user, preserve created_at
        user_data["created_at"] = users[existing_idx].get("created_at", now)
        users[existing_idx] = user_data
    else:
        # New user
        user_data["created_at"] = now
        users.append(user_data)

    _save_users(users)
    return user_data


def list_users() -> list[dict]:
    """Return all registered users."""
    return _load_users()


def get_user_count() -> int:
    """Return the number of registered users."""
    return len(_load_users())
