"""
Session management — ties together OAuth flow, user store, and Streamlit session.

Core API:
    require_auth()       → dict   Blocks with login page if not authenticated; returns user dict
    get_current_user()   → dict | None   Returns current user or None
    logout()             → None   Clears auth session state
    is_auth_enabled()    → bool   True if Google OAuth credentials are configured
"""

import logging
import streamlit as st

from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, APP_URL
from auth.google_oauth import (
    build_auth_url,
    exchange_code_for_tokens,
    fetch_user_info,
    generate_state_token,
)
from auth.user_store import upsert_user
from auth.login_page import render_login_page


logger = logging.getLogger(__name__)

# Session state keys
_USER_KEY = "_auth_user"
_STATE_KEY = "_auth_state"


def is_auth_enabled() -> bool:
    """Return True if Google OAuth credentials are configured."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def get_current_user() -> dict | None:
    """Return the authenticated user dict, or None if not logged in."""
    return st.session_state.get(_USER_KEY)


def logout() -> None:
    """Clear authentication from session state."""
    st.session_state.pop(_USER_KEY, None)
    st.session_state.pop(_STATE_KEY, None)


def _get_redirect_uri() -> str:
    """Build the OAuth redirect URI from APP_URL."""
    url = APP_URL.rstrip("/")
    return url


def _handle_oauth_callback() -> bool:
    """
    Check for OAuth callback parameters and complete the auth flow.

    Returns True if callback was handled (user is now authenticated).
    Returns False if no callback parameters present.
    """
    params = st.query_params

    code = params.get("code")
    state = params.get("state")

    if not code:
        return False

    # Verify state token for CSRF protection
    expected_state = st.session_state.get(_STATE_KEY)
    if not expected_state or state != expected_state:
        logger.warning("OAuth state mismatch: expected=%s, got=%s", expected_state, state)
        st.query_params.clear()
        return False

    try:
        # Exchange code for tokens
        redirect_uri = _get_redirect_uri()
        tokens = exchange_code_for_tokens(
            code=code,
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            redirect_uri=redirect_uri,
        )

        # Fetch user profile
        access_token = tokens.get("access_token")
        if not access_token:
            logger.error("No access_token in token response")
            st.query_params.clear()
            return False

        google_info = fetch_user_info(access_token)

        # Upsert user in local store
        user = upsert_user(google_info)

        # Store in session
        st.session_state[_USER_KEY] = user

        # Clear query params (removes ?code=...&state=... from URL)
        st.query_params.clear()

        logger.info("User authenticated: %s", user.get("email"))
        return True

    except Exception as e:
        logger.error("OAuth callback error: %s", e, exc_info=True)
        st.query_params.clear()
        return False


def require_auth() -> dict:
    """
    Gate the app behind authentication.

    - If auth is not enabled (no Google credentials), returns a placeholder user.
    - If user is already authenticated, returns user dict.
    - If OAuth callback is in progress, completes it and reruns.
    - Otherwise, shows the login page and calls st.stop().

    Returns:
        User dict with keys: google_id, email, name, picture, etc.
    """
    # Auth disabled — return anonymous placeholder
    if not is_auth_enabled():
        return {
            "email": "local@pm-agent.dev",
            "name": "Local User",
            "picture": "",
            "google_id": "local",
        }

    # Already authenticated
    user = get_current_user()
    if user:
        return user

    # Check for OAuth callback
    if _handle_oauth_callback():
        st.rerun()

    # Not authenticated — show login page
    # Generate and store CSRF state token
    if _STATE_KEY not in st.session_state:
        st.session_state[_STATE_KEY] = generate_state_token()

    auth_url = build_auth_url(
        client_id=GOOGLE_CLIENT_ID,
        redirect_uri=_get_redirect_uri(),
        state=st.session_state[_STATE_KEY],
    )

    # Check if there was an error parameter
    error = st.query_params.get("error", "")
    error_msg = ""
    if error:
        error_msg = f"Authentication failed: {error}"
        st.query_params.clear()

    render_login_page(auth_url=auth_url, error=error_msg)
    st.stop()
