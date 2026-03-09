"""
Authentication module — Google OAuth2 for PM Agent.

Usage in app.py:
    from auth import require_auth, get_current_user, logout

    user = require_auth()   # blocks with login page if not authenticated
    logout()                # clears session
"""

from auth.session import require_auth, get_current_user, logout, is_auth_enabled

__all__ = ["require_auth", "get_current_user", "logout", "is_auth_enabled"]
