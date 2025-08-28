"""
Unit Tests for CLI Authentication Module

Comprehensive tests for the CLI authentication system including:
- JWT token generation and validation
- Token revocation and tracking
- Session management
- Security features and edge cases
"""

import time
import uuid
from unittest.mock import patch

import jwt
import pytest

from orchestrator.auth import (
    JWT_ALGORITHM,
    JWT_SECRET,
    AuthManager,
    pwd_context,
)


class TestAuthManager:
    """Test AuthManager functionality."""

    @pytest.fixture
    def auth_manager(self):
        """Create auth manager for testing."""
        return AuthManager()

    def test_auth_manager_initialization(self, auth_manager):
        """Test auth manager initialization."""
        assert len(auth_manager.active_tokens) == 0
        assert len(auth_manager.user_sessions) == 0

    def test_generate_jwt_token(self, auth_manager):
        """Test JWT token generation."""
        user_id = "test_user"
        session_id = "test_session"

        token = auth_manager.generate_jwt_token(user_id, session_id)

        assert token is not None
        assert isinstance(token, str)

        # Decode token to verify contents
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["user_id"] == user_id
        assert payload["session_id"] == session_id
        assert "iat" in payload
        assert "exp" in payload
        assert "jti" in payload

        # Verify token is tracked
        jti = payload["jti"]
        assert jti in auth_manager.active_tokens
        assert auth_manager.active_tokens[jti]["user_id"] == user_id
        assert auth_manager.active_tokens[jti]["session_id"] == session_id

        # Verify user session tracking
        assert user_id in auth_manager.user_sessions
        assert jti in auth_manager.user_sessions[user_id]

    def test_generate_jwt_token_without_session(self, auth_manager):
        """Test JWT token generation without explicit session ID."""
        user_id = "test_user"

        token = auth_manager.generate_jwt_token(user_id)

        # Decode token
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["user_id"] == user_id
        assert payload["session_id"] is not None  # Should generate UUID
        assert len(payload["session_id"]) > 0

    def test_generate_jwt_token_custom_expiration(self, auth_manager):
        """Test JWT token generation with custom expiration."""
        user_id = "test_user"
        expires_hours = 48

        token = auth_manager.generate_jwt_token(user_id, expires_hours=expires_hours)

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Check expiration is roughly correct (within 1 minute tolerance)
        expected_exp = int(time.time()) + (expires_hours * 3600)
        assert abs(payload["exp"] - expected_exp) < 60

    def test_verify_jwt_token_valid(self, auth_manager):
        """Test verifying valid JWT token."""
        user_id = "test_user"
        token = auth_manager.generate_jwt_token(user_id)

        payload = auth_manager.verify_jwt_token(token)

        assert payload is not None
        assert payload["user_id"] == user_id
        assert "jti" in payload

    def test_verify_jwt_token_expired(self, auth_manager):
        """Test verifying expired JWT token."""
        # Create an expired token manually
        payload = {
            "user_id": "test_user",
            "session_id": "test_session",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "jti": str(uuid.uuid4()),
        }

        expired_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        result = auth_manager.verify_jwt_token(expired_token)
        assert result is None

    def test_verify_jwt_token_invalid_signature(self, auth_manager):
        """Test verifying token with invalid signature."""
        # Create token with different secret
        payload = {"user_id": "test_user", "exp": int(time.time()) + 3600, "jti": str(uuid.uuid4())}

        invalid_token = jwt.encode(payload, "wrong_secret", algorithm=JWT_ALGORITHM)

        result = auth_manager.verify_jwt_token(invalid_token)
        assert result is None

    def test_verify_jwt_token_revoked(self, auth_manager):
        """Test verifying revoked JWT token."""
        user_id = "test_user"
        token = auth_manager.generate_jwt_token(user_id)

        # Verify token works initially
        assert auth_manager.verify_jwt_token(token) is not None

        # Revoke the token
        auth_manager.revoke_token(token)

        # Token should no longer verify
        assert auth_manager.verify_jwt_token(token) is None

    def test_verify_jwt_token_malformed(self, auth_manager):
        """Test verifying malformed token."""
        assert auth_manager.verify_jwt_token("not.a.jwt") is None
        assert auth_manager.verify_jwt_token("") is None
        assert auth_manager.verify_jwt_token("invalid") is None

    def test_revoke_token_success(self, auth_manager):
        """Test successful token revocation."""
        user_id = "test_user"
        token = auth_manager.generate_jwt_token(user_id)

        # Get JTI for verification
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        jti = payload["jti"]

        # Verify token is active
        assert jti in auth_manager.active_tokens
        assert user_id in auth_manager.user_sessions
        assert jti in auth_manager.user_sessions[user_id]

        # Revoke the token
        result = auth_manager.revoke_token(token)
        assert result is True

        # Verify token is removed
        assert jti not in auth_manager.active_tokens
        assert user_id not in auth_manager.user_sessions  # User has no more sessions

    def test_revoke_token_invalid(self, auth_manager):
        """Test revoking invalid token."""
        result = auth_manager.revoke_token("invalid.token")
        assert result is False

    def test_revoke_token_already_revoked(self, auth_manager):
        """Test revoking already revoked token."""
        user_id = "test_user"
        token = auth_manager.generate_jwt_token(user_id)

        # Revoke once
        result1 = auth_manager.revoke_token(token)
        assert result1 is True

        # Try to revoke again
        result2 = auth_manager.revoke_token(token)
        assert result2 is False  # Already revoked

    def test_multiple_user_sessions(self, auth_manager):
        """Test managing multiple sessions for same user."""
        user_id = "test_user"

        # Generate multiple tokens for same user
        token1 = auth_manager.generate_jwt_token(user_id, "session1")
        token2 = auth_manager.generate_jwt_token(user_id, "session2")
        token3 = auth_manager.generate_jwt_token(user_id, "session3")

        # User should have 3 sessions
        assert user_id in auth_manager.user_sessions
        assert len(auth_manager.user_sessions[user_id]) == 3

        # Revoke one token
        auth_manager.revoke_token(token1)

        # User should still have 2 sessions
        assert len(auth_manager.user_sessions[user_id]) == 2

        # Other tokens should still be valid
        assert auth_manager.verify_jwt_token(token2) is not None
        assert auth_manager.verify_jwt_token(token3) is not None

    def test_multiple_users(self, auth_manager):
        """Test managing tokens for multiple users."""
        # Generate tokens for different users
        token1 = auth_manager.generate_jwt_token("user1")
        token2 = auth_manager.generate_jwt_token("user2")
        token3 = auth_manager.generate_jwt_token("user3")

        # All users should be tracked
        assert "user1" in auth_manager.user_sessions
        assert "user2" in auth_manager.user_sessions
        assert "user3" in auth_manager.user_sessions

        # Revoking one user's token shouldn't affect others
        auth_manager.revoke_token(token1)

        assert "user1" not in auth_manager.user_sessions
        assert auth_manager.verify_jwt_token(token2) is not None
        assert auth_manager.verify_jwt_token(token3) is not None

    def test_token_cleanup_after_all_revoked(self, auth_manager):
        """Test cleanup when all user tokens are revoked."""
        user_id = "test_user"

        token1 = auth_manager.generate_jwt_token(user_id)
        token2 = auth_manager.generate_jwt_token(user_id)

        # Revoke all tokens
        auth_manager.revoke_token(token1)
        auth_manager.revoke_token(token2)

        # User should be completely removed
        assert user_id not in auth_manager.user_sessions

    def test_jti_uniqueness(self, auth_manager):
        """Test that JTI (JWT ID) is unique for each token."""
        jtis = set()

        # Generate multiple tokens
        for i in range(100):
            token = auth_manager.generate_jwt_token(f"user_{i}")
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            jti = payload["jti"]

            # JTI should be unique
            assert jti not in jtis
            jtis.add(jti)


class TestPasswordHashing:
    """Test password hashing utilities."""

    def test_password_hash_verify(self):
        """Test password hashing and verification."""
        password = "test_password_123"

        # Hash password
        hashed = pwd_context.hash(password)

        assert hashed != password  # Should be hashed
        assert len(hashed) > 0

        # Verify correct password
        assert pwd_context.verify(password, hashed) is True

        # Verify incorrect password
        assert pwd_context.verify("wrong_password", hashed) is False

    def test_different_hashes_same_password(self):
        """Test that same password generates different hashes."""
        password = "test_password"

        hash1 = pwd_context.hash(password)
        hash2 = pwd_context.hash(password)

        # Hashes should be different due to salting
        assert hash1 != hash2

        # But both should verify the same password
        assert pwd_context.verify(password, hash1) is True
        assert pwd_context.verify(password, hash2) is True


class TestSecurityFeatures:
    """Test security features and edge cases."""

    @pytest.fixture
    def auth_manager(self):
        """Create auth manager for security testing."""
        return AuthManager()

    def test_token_tampering_detection(self, auth_manager):
        """Test that tampered tokens are rejected."""
        token = auth_manager.generate_jwt_token("test_user")

        # Tamper with token
        if isinstance(token, bytes):
            token = token.decode("utf-8")

        # Change last character
        tampered_token = token[:-1] + ("A" if token[-1] != "A" else "B")

        # Should not verify
        assert auth_manager.verify_jwt_token(tampered_token) is None

    def test_token_algorithm_confusion(self, auth_manager):
        """Test protection against algorithm confusion attacks."""
        # Try to create token with 'none' algorithm
        payload = {"user_id": "attacker", "exp": int(time.time()) + 3600, "jti": str(uuid.uuid4())}

        # Create token with 'none' algorithm (unsigned)
        header = {"alg": "none", "typ": "JWT"}
        import base64
        import json

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")

        malicious_token = f"{header_b64.decode()}.{payload_b64.decode()}."

        # Should not verify
        assert auth_manager.verify_jwt_token(malicious_token) is None

    def test_expired_token_not_accepted(self, auth_manager):
        """Test that expired tokens are properly rejected."""
        with patch("time.time") as mock_time:
            # Set current time
            current_time = 1000000
            mock_time.return_value = current_time

            # Generate token
            token = auth_manager.generate_jwt_token("test_user", expires_hours=1)

            # Advance time by 2 hours
            mock_time.return_value = current_time + 7200

            # Token should be expired
            assert auth_manager.verify_jwt_token(token) is None

    def test_token_without_jti_tracking(self, auth_manager):
        """Test that tokens without JTI are not tracked in active_tokens."""
        # Create token without JTI (manually)
        payload = {
            "user_id": "test_user",
            "exp": int(time.time()) + 3600,
            # Missing "jti"
        }

        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        # Token may verify but won't be in active_tokens tracking
        result = auth_manager.verify_jwt_token(token)

        # Since there's no JTI, it won't be tracked for revocation
        if result:
            # Token verifies but can't be revoked without JTI
            assert auth_manager.revoke_token(token) is False

    def test_concurrent_token_generation(self, auth_manager):
        """Test concurrent token generation doesn't cause issues."""
        import threading

        tokens = []
        errors = []

        def generate_token(user_id):
            try:
                token = auth_manager.generate_jwt_token(user_id)
                tokens.append(token)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=generate_token, args=(f"user_{i}",))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0
        assert len(tokens) == 10

        # All tokens should be valid
        for token in tokens:
            assert auth_manager.verify_jwt_token(token) is not None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def auth_manager(self):
        """Create auth manager for testing."""
        return AuthManager()

    def test_empty_user_id(self, auth_manager):
        """Test token generation with empty user ID."""
        token = auth_manager.generate_jwt_token("")

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["user_id"] == ""

        # Should still track properly
        assert auth_manager.verify_jwt_token(token) is not None

    def test_special_characters_in_user_id(self, auth_manager):
        """Test token generation with special characters in user ID."""
        special_user_ids = [
            "user@example.com",
            "user+test",
            "user/slash",
            "user\\backslash",
            "user'quote",
            'user"doublequote',
            "user with spaces",
            "用户",  # Unicode
            "🎭",  # Emoji
        ]

        for user_id in special_user_ids:
            token = auth_manager.generate_jwt_token(user_id)
            payload = auth_manager.verify_jwt_token(token)
            assert payload is not None
            assert payload["user_id"] == user_id

    def test_very_long_user_id(self, auth_manager):
        """Test token generation with very long user ID."""
        long_user_id = "u" * 10000

        token = auth_manager.generate_jwt_token(long_user_id)
        payload = auth_manager.verify_jwt_token(token)

        assert payload is not None
        assert payload["user_id"] == long_user_id

    def test_null_session_id(self, auth_manager):
        """Test token generation with None session ID."""
        token = auth_manager.generate_jwt_token("user", session_id=None)

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["session_id"] is not None  # Should generate UUID

    def test_token_size_limits(self, auth_manager):
        """Test token size with various payloads."""
        # Generate token with maximum reasonable data
        user_id = "u" * 1000
        session_id = "s" * 1000

        token = auth_manager.generate_jwt_token(user_id, session_id)

        # Token should still be manageable size (< 10KB)
        assert len(token) < 10000

        # Should still be valid
        assert auth_manager.verify_jwt_token(token) is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
