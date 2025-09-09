"""Security Manager - Authentication and Authorization

Responsibilities:
- Manage authentication tokens and sessions
- Handle security validation
- Track active sessions
- Provide security status information
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SecurityManager:
    """Core security and authentication manager"""

    def __init__(self, state_dir=None):
        self.state_dir = state_dir
        self.active_sessions = {}
        self.authorized_keys = []

    def create_session(self, client_name: str, private_key: str = None) -> dict[str, Any]:
        """Create a new authentication session"""
        # Generate session token (in production, this would be cryptographically secure)
        session_token = f"session_{datetime.now().timestamp():.0f}_{client_name.replace(' ', '_')}"

        # Create session data
        session_data = {
            "client_name": client_name,
            "token": session_token,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
            "private_key_hash": hash(private_key) if private_key else None,
        }

        # Store session
        self.active_sessions[session_token] = session_data

        logger.info(f"Created session for {client_name}: {session_token[:20]}...")

        return {
            "session_token": session_token,
            "expires_in": 3600,  # 1 hour in seconds
            "client_name": client_name,
        }

    def validate_session(self, token: str) -> tuple[bool, Optional[dict[str, Any]]]:
        """Validate authentication session"""
        # Remove "Bearer " prefix if present
        if token and token.startswith("Bearer "):
            token = token[7:]

        # Try to validate existing session
        valid_session = self._check_existing_session(token)
        if valid_session is not None:
            return True, valid_session

        # Try mock session for development
        mock_session = self._check_mock_session(token)
        if mock_session is not None:
            return True, mock_session

        logger.debug(f"Invalid session token: {token[:20] if token else 'None'}...")
        return False, None

    def _check_existing_session(self, token: str) -> Optional[dict[str, Any]]:
        """Check if token corresponds to valid existing session"""
        if token not in self.active_sessions:
            return None

        session = self.active_sessions[token]
        expires_at = datetime.fromisoformat(session["expires_at"])

        if datetime.now() < expires_at:
            logger.debug(f"Session validated for {session['client_name']}")
            return session
        else:
            logger.warning(f"Session expired for {session['client_name']}")
            del self.active_sessions[token]
            return None

    def _check_mock_session(self, token: str) -> Optional[dict[str, Any]]:
        """Check if token is a valid mock session for development"""
        if not token or not token.startswith("mock_session_token"):
            return None

        mock_session = {
            "client_name": "Mock User",
            "token": token,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        logger.debug("Accepting mock session token for development")
        return mock_session

    def get_security_status(self) -> dict[str, Any]:
        """Get security status information"""
        return {
            "authorized_keys_count": len(self.authorized_keys),
            "active_sessions": len(self.active_sessions),
            "recent_deployments": 0,
        }

    def clear_expired_sessions(self):
        """Remove expired sessions from active sessions"""
        expired = []
        for token, session in self.active_sessions.items():
            expires_at = datetime.fromisoformat(session["expires_at"])
            if datetime.now() >= expires_at:
                expired.append(token)

        for token in expired:
            del self.active_sessions[token]
            logger.info(f"Cleared expired session: {token[:20]}...")

        return len(expired)
