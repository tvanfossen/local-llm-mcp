#!/usr/bin/env python3
"""MCP Key Manager CLI
Save as: ~/Projects/local-llm-mcp/mcp_keys.py

Manages RSA keys for MCP orchestrator authentication
Following SSH-style conventions with enhanced security
"""

import argparse
import json
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


# Determine OS-specific paths
def get_key_directory() -> Path:
    """Get the appropriate directory for MCP keys based on OS"""
    system = platform.system()

    if system == "Linux" or system == "Darwin":  # Unix-like systems
        # Follow SSH convention: ~/.ssh/mcp/
        ssh_dir = Path.home() / ".ssh" / "mcp"
    elif system == "Windows":
        # Windows: %USERPROFILE%\.ssh\mcp\
        ssh_dir = Path.home() / ".ssh" / "mcp"
    else:
        # Fallback
        ssh_dir = Path.home() / ".mcp" / "keys"

    return ssh_dir


class MCPKeyManager:
    """Manages MCP RSA keys with secure storage"""

    def __init__(self):
        self.key_dir = get_key_directory()
        self.key_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        self.private_key_file = self.key_dir / "id_rsa_mcp"
        self.public_key_file = self.key_dir / "id_rsa_mcp.pub"
        self.config_file = self.key_dir / "config.json"

    def init(self, server_url: str = "http://localhost:8000", name: str | None = None):
        """Initialize MCP key storage"""
        if self.private_key_file.exists():
            print(f"⚠️  Keys already exist at {self.key_dir}")
            response = input("Overwrite existing keys? (y/N): ")
            if response.lower() != "y":
                print("Initialization cancelled")
                return False

        # Get user info
        if not name:
            name = input("Enter your name (for key identification): ")

        # Request keys from server
        print(f"\n🔑 Requesting new key pair from {server_url}...")

        try:
            import requests

            response = requests.post(
                f"{server_url}/api/orchestrator/generate-keys",
                json={"client_name": name},
                timeout=10,
            )

            return self._process_key_generation_response(response, name, server_url)

        except Exception as e:
            print(f"❌ Failed to generate keys: {e}")
            return False

    def show(self, private: bool = False):
        """Display stored keys"""
        if not self.private_key_file.exists():
            print("❌ No keys found. Run 'mcp-keys init' first")
            return

        config = self._load_config()
        self._print_key_info(config)
        self._show_public_key()

        if private:
            self._show_private_key()
        else:
            print("\n💡 Tip: Use --private flag to show private key")

    def _print_key_info(self, config: dict):
        """Print basic key information"""
        print("\n🔑 MCP Key Information")
        print("=" * 50)
        print(f"Name: {config.get('name', 'Unknown')}")
        print(f"Server: {config.get('server', 'Unknown')}")
        print(f"Created: {config.get('created', 'Unknown')}")
        print(f"Fingerprint: {config.get('fingerprint', 'Unknown')[:16]}...")
        print(f"\nKey Location: {self.key_dir}")

    def _show_public_key(self):
        """Display public key if it exists"""
        if self.public_key_file.exists():
            with open(self.public_key_file) as f:
                public_key = f.read()
            print("\n📄 Public Key:")
            print("-" * 50)
            print(public_key[:200] + "..." if len(public_key) > 200 else public_key)

    def _show_private_key(self):
        """Show private key with confirmation"""
        print("\n⚠️  WARNING: Displaying private key!")
        confirm = input("Are you sure? (yes/no): ")
        if confirm.lower() == "yes":
            with open(self.private_key_file) as f:
                private_key = f.read()
            print("\n🔐 Private Key:")
            print("-" * 50)
            print(private_key)

    def get_private_key(self) -> str | None:
        """Retrieve private key for authentication"""
        if not self.private_key_file.exists():
            return None

        try:
            with open(self.private_key_file) as f:
                return f.read()
        except Exception as e:
            print(f"❌ Error reading private key: {e}")
            return None

    def copy_to_clipboard(self) -> bool:
        """Copy private key to clipboard - simplified to reduce returns"""
        private_key = self.get_private_key()
        if not private_key:
            print("❌ No private key found")
            return False

        # Determine copy method based on OS and execute
        copy_result = self._copy_by_os(private_key)

        if copy_result["success"]:
            print(f"✅ Private key copied to clipboard ({copy_result['method']})")
            print("📋 You can now paste it in the orchestrator")
        else:
            print(f"❌ {copy_result['error']}")
            print("💡 You can manually copy from: mcp-keys show --private")

        return copy_result["success"]

    def _copy_by_os(self, private_key: str) -> dict:
        """Copy to clipboard by OS - consolidated to reduce returns"""
        system = platform.system()

        try:
            result = self._attempt_clipboard_copy(system, private_key)
            return result
        except Exception as e:
            return {"success": False, "error": f"Failed to copy to clipboard: {e}"}

    def _attempt_clipboard_copy(self, system: str, private_key: str) -> dict:
        """Attempt clipboard copy based on system - single return path"""
        try:
            copy_result = self._execute_system_specific_copy(system, private_key)
            return copy_result
        except Exception as e:
            return {"success": False, "error": f"Clipboard copy failed: {e}"}

    def _execute_system_specific_copy(self, system: str, private_key: str) -> dict:
        """Execute system-specific clipboard copy"""
        copy_handlers = {
            "Darwin": lambda: self._copy_macos(private_key),
            "Windows": lambda: self._copy_windows(private_key),
            "Linux": lambda: self._copy_to_linux_clipboard(private_key),
        }

        handler = copy_handlers.get(system)
        if handler:
            return handler()
        else:
            return {"success": False, "error": f"Clipboard not supported on {system}"}

    def _copy_macos(self, private_key: str) -> dict:
        """Copy to macOS clipboard"""
        subprocess.run("pbcopy", input=private_key.encode(), check=True)
        return {"success": True, "method": "macOS"}

    def _copy_windows(self, private_key: str) -> dict:
        """Copy to Windows clipboard"""
        subprocess.run("clip", input=private_key.encode(), check=True)
        return {"success": True, "method": "Windows"}

    def _copy_to_linux_clipboard(self, private_key: str) -> dict:
        """Copy to Linux clipboard using available tools - single return"""
        try:
            return self._try_linux_clipboard_tools(private_key)
        except Exception as e:
            return {"success": False, "error": f"Linux clipboard error: {e}"}

    def _try_linux_clipboard_tools(self, private_key: str) -> dict:
        """Try Linux clipboard tools in order of preference"""
        # Try xclip first, then xsel
        tools = [
            ("xclip", ["xclip", "-selection", "clipboard"], "Linux/xclip"),
            ("xsel", ["xsel", "--clipboard", "--input"], "Linux/xsel"),
        ]

        for _tool_name, cmd, method_name in tools:
            try:
                subprocess.run(cmd, input=private_key.encode(), check=True)
                return {"success": True, "method": method_name}
            except Exception:
                continue

        return {"success": False, "error": "No Linux clipboard tools available (xclip/xsel)"}

    def export(self, output_file: str | None = None, format: str = "pem"):
        """Export keys to file"""
        if not output_file:
            output_file = f"mcp_keys_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"

        output_path = Path(output_file)

        if format == "pem":
            # Export just private key (public can be derived)
            private_key = self.get_private_key()
            if private_key:
                with open(output_path, "w") as f:
                    f.write(private_key)
                output_path.chmod(0o600)
                print(f"✅ Private key exported to: {output_path}")

        elif format == "json":
            # Export both keys and metadata
            config = self._load_config()
            with open(self.private_key_file) as f:
                private_key = f.read()
            with open(self.public_key_file) as f:
                public_key = f.read()

            export_data = {
                "config": config,
                "private_key": private_key,
                "public_key": public_key,
                "exported_at": datetime.now().isoformat(),
            }

            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2)
            output_path.chmod(0o600)
            print(f"✅ Keys exported to: {output_path}")

        else:
            print(f"❌ Unknown format: {format}")

    def import_keys(self, input_file: str):
        """Import keys from file"""
        input_path = Path(input_file)

        if not input_path.exists():
            print(f"❌ File not found: {input_file}")
            return False

        try:
            # Check if JSON format
            if input_path.suffix == ".json":
                with open(input_path) as f:
                    data = json.load(f)

                self._save_keys(data["private_key"], data["public_key"])
                self._save_config(data["config"])
                print(f"✅ Keys imported from JSON: {input_file}")

            else:
                # Assume PEM format (private key only)
                with open(input_path) as f:
                    private_key = f.read()

                # Derive public key (would need cryptography library)
                print("⚠️  Importing PEM private key only")
                print("You'll need to regenerate the public key")

                with open(self.private_key_file, "w") as f:
                    f.write(private_key)
                self.private_key_file.chmod(0o600)

                print(f"✅ Private key imported from: {input_file}")

            return True

        except Exception as e:
            print(f"❌ Import failed: {e}")
            return False

    def backup(self):
        """Create encrypted backup of keys"""
        backup_dir = self.key_dir / "backups"
        backup_dir.mkdir(exist_ok=True, mode=0o700)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"mcp_keys_backup_{timestamp}.tar.gz"

        try:
            # Create tar archive
            import tarfile

            with tarfile.open(backup_file, "w:gz") as tar:
                tar.add(self.private_key_file, arcname="id_rsa_mcp")
                tar.add(self.public_key_file, arcname="id_rsa_mcp.pub")
                tar.add(self.config_file, arcname="config.json")

            backup_file.chmod(0o600)
            print(f"✅ Backup created: {backup_file}")

            # Optional: encrypt with GPG if available
            try:
                subprocess.run(["gpg", "--version"], capture_output=True, check=True)
                response = input("Encrypt backup with GPG? (y/N): ")
                if response.lower() == "y":
                    subprocess.run(
                        [
                            "gpg",
                            "--cipher-algo",
                            "AES256",
                            "--symmetric",
                            str(backup_file),
                        ],
                        check=True,
                    )
                    backup_file.unlink()  # Remove unencrypted version
                    print(f"🔒 Encrypted backup: {backup_file}.gpg")
            except Exception:
                pass

            return True

        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False

    def authenticate(self, server_url: str | None = None) -> bool:
        """Test authentication with server - simplified to reduce returns"""
        if not server_url:
            config = self._load_config()
            server_url = config.get("server", "http://localhost:8000")

        private_key = self.get_private_key()
        if not private_key:
            print("❌ No private key found")
            return False

        # Perform authentication request
        auth_result = self._perform_auth_request(server_url, private_key)

        if auth_result["success"]:
            data = auth_result["data"]
            print("✅ Authentication successful!")
            print(f"🎫 Session token: {data['session_token'][:20]}...")
            print(f"⏱️  Expires in: {data['expires_in']} seconds")
        else:
            print(f"❌ Authentication failed: {auth_result['error']}")

        return auth_result["success"]

    def _perform_auth_request(self, server_url: str, private_key: str) -> dict:
        """Perform authentication request"""
        try:
            import requests

            response = requests.post(
                f"{server_url}/api/orchestrator/authenticate",
                json={"private_key": private_key},
                timeout=10,
            )

            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": f"Connection failed: {e}"}

    def _save_keys(self, private_key: str, public_key: str):
        """Save keys with proper permissions"""
        # Save private key (mode 600 - owner read/write only)
        with open(self.private_key_file, "w") as f:
            f.write(private_key)
        self.private_key_file.chmod(0o600)

        # Save public key (mode 644 - owner write, others read)
        with open(self.public_key_file, "w") as f:
            f.write(public_key)
        self.public_key_file.chmod(0o644)

    def _save_config(self, config: dict[str, Any]):
        """Save configuration"""
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)
        self.config_file.chmod(0o600)

    def _load_config(self) -> dict[str, Any]:
        """Load configuration"""
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file) as f:
                return json.load(f)
        except Exception:
            return {}

    def _calculate_fingerprint(self, public_key: str) -> str:
        """Calculate key fingerprint"""
        import hashlib

        return hashlib.sha256(public_key.encode()).hexdigest()

    def _process_key_generation_response(self, response, name: str, server_url: str) -> bool:
        """Process the key generation response"""
        if response.status_code == 200:
            data = response.json()

            # Save keys with proper permissions
            self._save_keys(data["private_key"], data["public_key"])

            # Save configuration
            config = {
                "name": name,
                "server": server_url,
                "created": datetime.now().isoformat(),
                "fingerprint": self._calculate_fingerprint(data["public_key"]),
            }
            self._save_config(config)

            print("\n✅ Keys successfully initialized!")
            print(f"📁 Location: {self.key_dir}")
            print(f"🔐 Private key: {self.private_key_file}")
            print(f"🔓 Public key: {self.public_key_file}")
            print("\n🛡️  Your keys are ready for use with MCP orchestrator")

            return True
        else:
            print(f"❌ Server error: {response.status_code}")
            return False


def main():
    parser = _create_argument_parser()
    args = parser.parse_args()

    # Initialize manager
    manager = MCPKeyManager()

    # Execute command
    _execute_command(manager, args, parser)


def _create_argument_parser():
    """Create and configure argument parser"""
    parser = argparse.ArgumentParser(
        description="MCP Key Manager - Manage RSA keys for MCP orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcp-keys init                    # Initialize new keys
  mcp-keys show                    # Show key information
  mcp-keys copy                    # Copy private key to clipboard
  mcp-keys auth                    # Test authentication
  mcp-keys backup                  # Create encrypted backup
  mcp-keys export -o keys.json    # Export keys to file
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")
    _add_subcommands(subparsers)
    return parser


def _add_subcommands(subparsers):
    """Add all subcommands to parser"""
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize new key pair")
    init_parser.add_argument("--server", default="http://localhost:8000", help="MCP server URL")
    init_parser.add_argument("--name", help="Your name for key identification")

    # Show command
    show_parser = subparsers.add_parser("show", help="Display key information")
    show_parser.add_argument("--private", action="store_true", help="Also show private key")

    # Copy command
    subparsers.add_parser("copy", help="Copy private key to clipboard")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export keys to file")
    export_parser.add_argument("-o", "--output", help="Output file")
    export_parser.add_argument("-f", "--format", choices=["pem", "json"], default="json", help="Export format")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import keys from file")
    import_parser.add_argument("file", help="Input file")

    # Backup command
    subparsers.add_parser("backup", help="Create encrypted backup")

    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Test authentication")
    auth_parser.add_argument("--server", help="MCP server URL")


def _execute_command(manager, args, parser):
    """Execute the specified command"""
    command_map = {
        "init": lambda: manager.init(args.server, args.name),
        "show": lambda: manager.show(args.private),
        "copy": manager.copy_to_clipboard,
        "export": lambda: manager.export(args.output, args.format),
        "import": lambda: manager.import_keys(args.file),
        "backup": manager.backup,
        "auth": lambda: manager.authenticate(args.server),
    }

    command_func = command_map.get(args.command)
    if command_func:
        command_func()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
