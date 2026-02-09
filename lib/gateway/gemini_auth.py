"""
Gemini OAuth Token Auto-Refresh Module.

Automatically refreshes expired Gemini OAuth tokens using the refresh_token.
"""
import json
import os
import time
from pathlib import Path
from typing import Optional, Tuple
import urllib.request
import urllib.parse

from lib.common.logging import get_logger

# Gemini CLI OAuth client credentials
# These are read from Gemini CLI installation at runtime
# See: /opt/homebrew/Cellar/gemini-cli/*/libexec/lib/node_modules/@google/gemini-cli/
#      node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js
_credentials_cache = {"client_id": None, "client_secret": None}


logger = get_logger("gateway.gemini_auth")


def _load_gemini_credentials():
    """Load Gemini OAuth credentials from CLI installation."""
    if _credentials_cache["client_id"] and _credentials_cache["client_secret"]:
        return True

    import subprocess
    import re
    import glob

    try:
        # Search for credentials in common Homebrew locations
        patterns = [
            "/opt/homebrew/Cellar/gemini-cli/*/libexec/lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js",
            "/usr/local/Cellar/gemini-cli/*/libexec/lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js",
        ]

        for pattern in patterns:
            files = glob.glob(pattern)
            if files:
                with open(files[0], 'r') as f:
                    content = f.read()

                # Extract credentials using regex
                client_id_match = re.search(r"OAUTH_CLIENT_ID\s*=\s*['\"]([^'\"]+)['\"]", content)
                client_secret_match = re.search(r"OAUTH_CLIENT_SECRET\s*=\s*['\"]([^'\"]+)['\"]", content)

                if client_id_match and client_secret_match:
                    _credentials_cache["client_id"] = client_id_match.group(1)
                    _credentials_cache["client_secret"] = client_secret_match.group(1)
                    return True

        return False
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        logger.error("Error loading credentials: %s", e)
        return False

OAUTH_CREDS_PATH = Path.home() / ".gemini" / "oauth_creds.json"
TOKEN_REFRESH_URL = "https://oauth2.googleapis.com/token"


def load_oauth_creds() -> Optional[dict]:
    """Load OAuth credentials from file."""
    if not OAUTH_CREDS_PATH.exists():
        return None
    try:
        with open(OAUTH_CREDS_PATH) as f:
            return json.load(f)
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
        return None


def save_oauth_creds(creds: dict) -> bool:
    """Save OAuth credentials to file."""
    try:
        with open(OAUTH_CREDS_PATH, "w") as f:
            json.dump(creds, f, indent=2)
        return True
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
        return False


def is_token_expired(creds: dict, buffer_seconds: int = 300) -> bool:
    """Check if token is expired or will expire soon."""
    expiry_ms = creds.get("expiry_date", 0)
    if not expiry_ms:
        return True
    
    expiry_time = expiry_ms / 1000
    current_time = time.time()
    
    # Consider expired if within buffer_seconds of expiry
    return current_time >= (expiry_time - buffer_seconds)


def refresh_token(refresh_token_str: str) -> Optional[dict]:
    """Refresh the OAuth token using refresh_token."""
    # Load credentials dynamically from Gemini CLI installation
    if not _load_gemini_credentials():
        logger.error("Failed to load OAuth credentials from Gemini CLI")
        return None

    data = urllib.parse.urlencode({
        "client_id": _credentials_cache["client_id"],
        "client_secret": _credentials_cache["client_secret"],
        "refresh_token": refresh_token_str,
        "grant_type": "refresh_token",
    }).encode()
    
    req = urllib.request.Request(
        TOKEN_REFRESH_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return result
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        logger.error("Token refresh failed: %s", e)
        return None


def ensure_valid_token() -> Tuple[bool, str]:
    """
    Ensure we have a valid OAuth token, refreshing if needed.
    
    Returns:
        Tuple of (success, message)
    """
    creds = load_oauth_creds()
    if not creds:
        return False, "No OAuth credentials found. Run 'gemini' to authenticate."
    
    refresh_token_str = creds.get("refresh_token")
    if not refresh_token_str:
        return False, "No refresh token. Run 'gemini' to re-authenticate."
    
    if not is_token_expired(creds):
        return True, "Token is valid"

    # Token expired, refresh it
    logger.info("Token expired, refreshing")
    new_tokens = refresh_token(refresh_token_str)
    
    if not new_tokens:
        return False, "Token refresh failed. Run 'gemini' to re-authenticate."
    
    # Update credentials
    creds["access_token"] = new_tokens.get("access_token", creds.get("access_token"))
    if new_tokens.get("refresh_token"):
        creds["refresh_token"] = new_tokens["refresh_token"]
    
    # Calculate new expiry (typically 1 hour)
    expires_in = new_tokens.get("expires_in", 3600)
    creds["expiry_date"] = int((time.time() + expires_in) * 1000)
    
    if new_tokens.get("id_token"):
        creds["id_token"] = new_tokens["id_token"]
    
    if save_oauth_creds(creds):
        logger.info("Token refreshed, valid for %ss", expires_in)
        return True, f"Token refreshed successfully"
    else:
        return False, "Failed to save refreshed token"


if __name__ == "__main__":
    success, msg = ensure_valid_token()
    logger.info("Result: %s, %s", success, msg)
