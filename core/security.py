# File: ~/Projects/local-llm-mcp/core/security.py
"""Security Module for Authentication and File Deployment

Responsibilities:
- RSA key pair generation and validation
- Authentication token management
- Secure file transfer authorization
- Audit logging for deployments
"""

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger(__name__)


@dataclass
class DeploymentLogEntry:
    """Deployment log entry data"""

    client: str
    agent_id: str
    source: str
    target: str
    authorized: bool
    error: str | None = None


class SecurityManager:
    """Manages authentication and secure deployment authorization

    Uses RSA key pairs for authentication and generates time-limited
    deployment tokens for secure file transfers.
    """

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.keys_dir = config_dir / "keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        # Server key paths
        self.server_private_key_path = self.keys_dir / "server_private.pem"
        self.server_public_key_path = self.keys_dir / "server_public.pem"

        # Authorized keys file (like SSH authorized_keys)
        self.authorized_keys_path = self.keys_dir / "authorized_keys.json"

        # Active sessions
        self.active_sessions: dict[str, dict[str, Any]] = {}

        # Deployment audit log
        self.audit_log_path = config_dir / "deployment_audit.log"

        # Initialize server keys
        self._initialize_server_keys()

    def _initialize_server_keys(self):
        """Initialize or load server RSA key pair"""
        if not self.server_private_key_path.exists():
            logger.info("Generating new server RSA key pair...")
            self.generate_server_keys()
        else:
            logger.info("Server keys already exist")

    def generate_server_keys(self) -> tuple[str, str]:
        """Generate new RSA key pair for server"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        # Save private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with open(self.server_private_key_path, "wb") as f:
            f.write(private_pem)

        # Save public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        with open(self.server_public_key_path, "wb") as f:
            f.write(public_pem)

        # Set appropriate permissions (readable only by owner)
        self.server_private_key_path.chmod(0o600)

        logger.info("Server RSA key pair generated successfully")
        return private_pem.decode(), public_pem.decode()

    def generate_client_keys(self, client_name: str) -> tuple[str, str]:
        """Generate RSA key pair for a client"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        # Generate PEM format keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        # Add to authorized keys
        self.add_authorized_key(client_name, public_pem.decode())

        logger.info(f"Generated client keys for: {client_name}")
        return private_pem.decode(), public_pem.decode()

    def add_authorized_key(self, client_name: str, public_key_pem: str):
        """Add a public key to authorized keys"""
        # Load existing authorized keys
        authorized_keys = self._load_authorized_keys()

        # Generate key fingerprint
        fingerprint = self._get_key_fingerprint(public_key_pem)

        # Add new key
        authorized_keys[fingerprint] = {
            "name": client_name,
            "public_key": public_key_pem,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "last_used": None,
            "deployment_count": 0,
        }

        # Save updated keys
        self._save_authorized_keys(authorized_keys)

        logger.info(f"Added authorized key for {client_name} (fingerprint: {fingerprint[:16]}...)")

    def authenticate_with_private_key(
        self, private_key_pem: str
    ) -> tuple[bool, str | None, str | None]:
        """Authenticate using a private key - simplified error handling"""
        try:
            # Validate and process private key
            validation_result = self._validate_and_process_private_key(private_key_pem)
            if validation_result.get("error"):
                return False, None, validation_result["error"]

            # Extract validated components
            private_key = validation_result["private_key"]
            public_pem = validation_result["public_pem"]
            fingerprint = validation_result["fingerprint"]

            # Perform challenge-response authentication
            auth_result = self._perform_authentication_challenge(private_key, public_pem)
            if auth_result.get("error"):
                return False, None, auth_result["error"]

            # Create session and update key usage
            session_token = self._create_authenticated_session(fingerprint)

            authorized_keys = self._load_authorized_keys()
            client_name = authorized_keys[fingerprint]["name"]
            logger.info(f"Authentication successful for {client_name}")

            return True, session_token, None

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False, None, str(e)

    def _validate_and_process_private_key(self, private_key_pem: str) -> dict:
        """Validate private key and check authorization"""
        try:
            # Load private key
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(), password=None, backend=default_backend()
            )

            # Get public key from private key
            public_key = private_key.public_key()
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode()

            # Check if public key is authorized
            fingerprint = self._get_key_fingerprint(public_pem)
            authorized_keys = self._load_authorized_keys()

            if fingerprint not in authorized_keys:
                return {"error": "Key not authorized"}

            return {
                "private_key": private_key,
                "public_pem": public_pem,
                "fingerprint": fingerprint,
            }

        except Exception as e:
            return {"error": f"Key validation failed: {e!s}"}

    def _perform_authentication_challenge(self, private_key, public_pem: str) -> dict:
        """Perform challenge-response authentication"""
        try:
            # Create challenge to verify key ownership
            challenge = secrets.token_bytes(32)

            # Sign challenge with private key
            signature = private_key.sign(
                challenge,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

            # Verify signature with public key
            public_key = serialization.load_pem_public_key(
                public_pem.encode(), backend=default_backend()
            )

            public_key.verify(
                signature,
                challenge,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

            return {"success": True}

        except InvalidSignature:
            return {"error": "Invalid key signature"}
        except Exception as e:
            return {"error": f"Challenge-response failed: {e!s}"}

    def _create_authenticated_session(self, fingerprint: str) -> str:
        """Create authenticated session and update key usage"""
        # Generate session token
        session_token = secrets.token_urlsafe(32)

        # Create session
        self.active_sessions[session_token] = {
            "fingerprint": fingerprint,
            "client_name": self._load_authorized_keys()[fingerprint]["name"],
            "authenticated_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
        }

        # Update last used time
        authorized_keys = self._load_authorized_keys()
        authorized_keys[fingerprint]["last_used"] = datetime.now(timezone.utc).isoformat()
        self._save_authorized_keys(authorized_keys)

        return session_token

    def validate_session(self, session_token: str) -> tuple[bool, dict[str, Any] | None]:
        """Validate a session token"""
        if session_token not in self.active_sessions:
            return False, None

        session = self.active_sessions[session_token]

        # Check expiration
        expires_at = datetime.fromisoformat(session["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            del self.active_sessions[session_token]
            return False, None

        return True, session

    def authorize_deployment(
        self,
        session_token: str,
        agent_id: str,
        source_path: Path,
        target_path: Path,
    ) -> tuple[bool, str | None]:
        """Authorize a file deployment"""
        # Validate session
        valid, session = self.validate_session(session_token)
        if not valid:
            return False, "Invalid or expired session"

        # Check if source file exists
        if not source_path.exists():
            return False, f"Source file not found: {source_path}"

        # Check if target directory is allowed
        # Add your custom validation logic here
        # For example, restrict to certain directories

        # Log deployment attempt
        self._log_deployment(
            client=session["client_name"],
            agent_id=agent_id,
            source=str(source_path),
            target=str(target_path),
            authorized=True,
        )

        # Update deployment count
        authorized_keys = self._load_authorized_keys()
        fingerprint = session["fingerprint"]
        if fingerprint in authorized_keys:
            authorized_keys[fingerprint]["deployment_count"] += 1
            self._save_authorized_keys(authorized_keys)

        return True, None

    def _get_key_fingerprint(self, public_key_pem: str) -> str:
        """Generate fingerprint from public key"""
        key_bytes = public_key_pem.encode()
        return hashlib.sha256(key_bytes).hexdigest()

    def _load_authorized_keys(self) -> dict[str, dict[str, Any]]:
        """Load authorized keys from file"""
        if not self.authorized_keys_path.exists():
            return {}

        try:
            with open(self.authorized_keys_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load authorized keys: {e}")
            return {}

    def _save_authorized_keys(self, authorized_keys: dict[str, dict[str, Any]]):
        """Save authorized keys to file"""
        try:
            with open(self.authorized_keys_path, "w") as f:
                json.dump(authorized_keys, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save authorized keys: {e}")

    def _log_deployment(
        self,
        client: str,
        agent_id: str,
        source: str,
        target: str,
        authorized: bool,
        error: str = None,
    ):
        """Log deployment attempt for audit"""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "client": client,
            "agent_id": agent_id,
            "source": source,
            "target": target,
            "authorized": authorized,
            "error": error,
        }

        try:
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def get_deployment_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent deployment history"""
        if not self.audit_log_path.exists():
            return []

        history = []
        try:
            with open(self.audit_log_path) as f:
                for line in f:
                    if line.strip():
                        history.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")

        return history[-limit:]

    def revoke_key(self, fingerprint: str) -> bool:
        """Revoke an authorized key"""
        authorized_keys = self._load_authorized_keys()

        if fingerprint in authorized_keys:
            client_name = authorized_keys[fingerprint]["name"]
            del authorized_keys[fingerprint]
            self._save_authorized_keys(authorized_keys)

            # Invalidate any active sessions for this key
            sessions_to_remove = [
                token
                for token, session in self.active_sessions.items()
                if session["fingerprint"] == fingerprint
            ]

            for token in sessions_to_remove:
                del self.active_sessions[token]

            logger.info(f"Revoked key for {client_name}")
            return True

        return False

    def get_security_status(self) -> dict[str, Any]:
        """Get current security status"""
        authorized_keys = self._load_authorized_keys()

        return {
            "server_keys_initialized": self.server_private_key_path.exists(),
            "authorized_keys_count": len(authorized_keys),
            "active_sessions": len(self.active_sessions),
            "recent_deployments": len(self.get_deployment_history(10)),
            "audit_log_size": (
                self.audit_log_path.stat().st_size if self.audit_log_path.exists() else 0
            ),
        }
