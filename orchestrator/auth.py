"""
Authentication utilities for CLI WebSocket integration.
Handles JWT token generation and validation.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime
from typing import Any

import jwt
from passlib.context import CryptContext

# JWT configuration (HS256 by default; RS256 supported if keys provided)
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_PRIVATE_KEY = os.getenv("JWT_PRIVATE_KEY")  # PEM string (optional)
JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY")  # PEM string (optional)
JWT_EXPIRATION_HOURS = 24


def _jwt_use_rs256() -> bool:
    """Return True if RS256 should be used (both keys provided)."""
    return bool(JWT_PRIVATE_KEY and JWT_PUBLIC_KEY)


def _jwt_encode(payload: dict) -> str:
    """Encode JWT with appropriate algorithm and key."""
    if _jwt_use_rs256():
        return jwt.encode(payload, JWT_PRIVATE_KEY, algorithm="RS256")
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _jwt_decode(token: str) -> dict | None:
    """Decode JWT with appropriate algorithm and key, or return None on error."""
    try:
        if _jwt_use_rs256():
            return jwt.decode(token, JWT_PUBLIC_KEY, algorithms=["RS256"])
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthManager:
    """Manages authentication for CLI WebSocket connections."""

    def __init__(self):
        self.active_tokens: dict[str, dict[str, Any]] = {}
        self.user_sessions: dict[str, list] = {}

    def generate_jwt_token(
        self, user_id: str, session_id: str = None, expires_hours: int = JWT_EXPIRATION_HOURS
    ) -> str:
        """Generate a JWT token for a user."""
        payload = {
            "user_id": user_id,
            "session_id": session_id or str(uuid.uuid4()),
            "iat": int(time.time()),
            "exp": int(time.time()) + (expires_hours * 3600),
            "jti": str(uuid.uuid4()),  # JWT ID for token tracking
        }

        token = _jwt_encode(payload)

        # Track active token
        self.active_tokens[payload["jti"]] = {
            "user_id": user_id,
            "session_id": payload["session_id"],
            "created_at": payload["iat"],
            "expires_at": payload["exp"],
        }

        # Track user sessions
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = []
        self.user_sessions[user_id].append(payload["jti"])

        return token

    def verify_jwt_token(self, token: str) -> dict[str, Any] | None:
        """Verify a JWT token and return the payload."""
        try:
            payload = _jwt_decode(token)
            if not payload:
                return None
            # Check if token is still active (not revoked)
            jti = payload.get("jti")
            if jti and jti not in self.active_tokens:
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None

    def revoke_token(self, token: str) -> bool:
        """Revoke a JWT token."""
        try:
            payload = _jwt_decode(token)
            jti = payload.get("jti")

            if jti and jti in self.active_tokens:
                # Remove from active tokens
                token_info = self.active_tokens.pop(jti)

                # Remove from user sessions
                user_id = token_info["user_id"]
                if user_id in self.user_sessions:
                    self.user_sessions[user_id] = [
                        t for t in self.user_sessions[user_id] if t != jti
                    ]
                    if not self.user_sessions[user_id]:
                        del self.user_sessions[user_id]

                return True

        except jwt.InvalidTokenError:
            pass

        return False

    def revoke_user_sessions(self, user_id: str) -> int:
        """Revoke all sessions for a user."""
        if user_id not in self.user_sessions:
            return 0

        token_ids = self.user_sessions[user_id].copy()
        revoked_count = 0

        for jti in token_ids:
            if jti in self.active_tokens:
                del self.active_tokens[jti]
                revoked_count += 1

        del self.user_sessions[user_id]
        return revoked_count

    def cleanup_expired_tokens(self):
        """Clean up expired tokens from memory."""
        current_time = int(time.time())
        expired_tokens = []

        for jti, token_info in self.active_tokens.items():
            if token_info["expires_at"] < current_time:
                expired_tokens.append(jti)

        for jti in expired_tokens:
            token_info = self.active_tokens.pop(jti)
            user_id = token_info["user_id"]

            if user_id in self.user_sessions:
                self.user_sessions[user_id] = [t for t in self.user_sessions[user_id] if t != jti]
                if not self.user_sessions[user_id]:
                    del self.user_sessions[user_id]

        return len(expired_tokens)

    def get_active_sessions(self) -> dict[str, Any]:
        """Get information about active sessions."""
        current_time = int(time.time())

        active_sessions = {}
        for user_id, token_ids in self.user_sessions.items():
            user_tokens = []
            for jti in token_ids:
                if jti in self.active_tokens:
                    token_info = self.active_tokens[jti]
                    if token_info["expires_at"] > current_time:
                        user_tokens.append(
                            {
                                "jti": jti,
                                "session_id": token_info["session_id"],
                                "created_at": datetime.fromtimestamp(
                                    token_info["created_at"]
                                ).isoformat(),
                                "expires_at": datetime.fromtimestamp(
                                    token_info["expires_at"]
                                ).isoformat(),
                            }
                        )

            if user_tokens:
                active_sessions[user_id] = user_tokens

        return active_sessions

    def hash_password(self, password: str) -> str:
        """Hash a password for storage."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)


# Global auth manager instance
_auth_manager = None


def get_auth_manager() -> AuthManager:
    """Get the global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


# Simple user database (in production, use a real database)
USERS_DB = {
    "admin": {
        "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "full_access": True,
        "roles": ["admin", "developer"],
    },
    "developer": {
        "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "full_access": True,
        "roles": ["developer"],
    },
    "user": {
        "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "full_access": False,
        "roles": ["user"],
    },
}


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    """Authenticate a user with username and password."""
    if username not in USERS_DB:
        return None

    user_info = USERS_DB[username]
    auth_manager = get_auth_manager()

    if auth_manager.verify_password(password, user_info["password_hash"]):
        return {
            "username": username,
            "full_access": user_info["full_access"],
            "roles": user_info["roles"],
        }

    return None


def create_access_token(user_info: dict[str, Any], session_id: str = None) -> str:
    """Create an access token for an authenticated user."""
    auth_manager = get_auth_manager()
    return auth_manager.generate_jwt_token(user_id=user_info["username"], session_id=session_id)


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT token and return user info."""
    auth_manager = get_auth_manager()
    payload = auth_manager.verify_jwt_token(token)

    if not payload:
        return None

    user_id = payload.get("user_id")
    if user_id not in USERS_DB:
        return None

    user_info = USERS_DB[user_id].copy()
    user_info["username"] = user_id
    user_info["session_id"] = payload.get("session_id")
    del user_info["password_hash"]  # Don't include password hash

    return user_info
