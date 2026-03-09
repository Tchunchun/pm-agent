"""
Google OAuth2 Authorization Code Flow helpers.

Handles:
  1. Building the Google consent URL
  2. Exchanging the authorization code for tokens
  3. Fetching user profile info from Google
"""

import secrets
import urllib.parse
import requests

# Google OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Scopes: basic profile + email
SCOPES = "openid email profile"


def generate_state_token() -> str:
    """Generate a cryptographically secure random state token for CSRF protection."""
    return secrets.token_urlsafe(32)


def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """
    Build the Google OAuth2 consent screen URL.

    Args:
        client_id: Google OAuth2 Client ID
        redirect_uri: Where Google redirects after consent
        state: CSRF protection token

    Returns:
        Full URL to redirect the user to
    """
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",  # Always show account chooser
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """
    Exchange an authorization code for access + ID tokens.

    Args:
        code: The authorization code from Google's callback
        client_id: Google OAuth2 Client ID
        client_secret: Google OAuth2 Client Secret
        redirect_uri: Must match the redirect_uri used in the auth URL

    Returns:
        Token response dict with keys: access_token, id_token, refresh_token, etc.

    Raises:
        requests.HTTPError: If the token exchange fails
    """
    resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_user_info(access_token: str) -> dict:
    """
    Fetch the authenticated user's profile from Google.

    Args:
        access_token: A valid Google OAuth2 access token

    Returns:
        Dict with keys: sub, email, email_verified, name, picture, given_name, family_name

    Raises:
        requests.HTTPError: If the userinfo request fails
    """
    resp = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
