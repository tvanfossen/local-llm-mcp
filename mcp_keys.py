#!/usr/bin/env python3
"""
MCP Key Manager CLI
Save as: ~/Projects/local-llm-mcp/mcp_keys.py

Manages RSA keys for MCP orchestrator authentication
Following SSH-style conventions with enhanced security
"""

import os
import sys
import json
import argparse
import getpass
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

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
        
        # Key file paths (following SSH naming convention)
        self.private_key_file = self.key_dir / "id_rsa_mcp"
        self.public_key_file = self.key_dir / "id_rsa_mcp.pub"
        self.config_file = self.key_dir / "config.json"
        
        # Additional security files
        self.known_hosts_file = self.key_dir / "known_hosts"
        self.authorized_servers = self.key_dir / "authorized_servers.json"
        
    def init(self, server_url: str = "http://localhost:8000", name: Optional[str] = None):
        """Initialize MCP key storage"""
        if self.private_key_file.exists():
            print(f"⚠️  Keys already exist at {self.key_dir}")
            response = input("Overwrite existing keys? (y/N): ")
            if response.lower() != 'y':
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
                json={"client_name": name}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Save keys with proper permissions
                self._save_keys(data['private_key'], data['public_key'])
                
                # Save configuration
                config = {
                    "name": name,
                    "server": server_url,
                    "created": datetime.now().isoformat(),
                    "fingerprint": self._calculate_fingerprint(data['public_key'])
                }
                self._save_config(config)
                
                print(f"\n✅ Keys successfully initialized!")
                print(f"📁 Location: {self.key_dir}")
                print(f"🔐 Private key: {self.private_key_file}")
                print(f"🔓 Public key: {self.public_key_file}")
                print(f"\n🛡️  Your keys are ready for use with MCP orchestrator")
                
                return True
                
            else:
                print(f"❌ Server error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to generate keys: {e}")
            return False
    
    def show(self, private: bool = False):
        """Display stored keys"""
        if not self.private_key_file.exists():
            print("❌ No keys found. Run 'mcp-keys init' first")
            return
        
        config = self._load_config()
        
        print("\n🔑 MCP Key Information")
        print("=" * 50)
        print(f"Name: {config.get('name', 'Unknown')}")
        print(f"Server: {config.get('server', 'Unknown')}")
        print(f"Created: {config.get('created', 'Unknown')}")
        print(f"Fingerprint: {config.get('fingerprint', 'Unknown')[:16]}...")
        print(f"\nKey Location: {self.key_dir}")
        
        # Show public key
        if self.public_key_file.exists():
            with open(self.public_key_file, 'r') as f:
                public_key = f.read()
            print(f"\n📄 Public Key:")
            print("-" * 50)
            print(public_key[:200] + "..." if len(public_key) > 200 else public_key)
        
        # Show private key only if explicitly requested
        if private:
            print("\n⚠️  WARNING: Displaying private key!")
            confirm = input("Are you sure? (yes/no): ")
            if confirm.lower() == 'yes':
                with open(self.private_key_file, 'r') as f:
                    private_key = f.read()
                print(f"\n🔐 Private Key:")
                print("-" * 50)
                print(private_key)
        else:
            print("\n💡 Tip: Use --private flag to show private key")
    
    def get_private_key(self) -> Optional[str]:
        """Retrieve private key for authentication"""
        if not self.private_key_file.exists():
            return None
        
        try:
            with open(self.private_key_file, 'r') as f:
                return f.read()
        except Exception as e:
            print(f"❌ Error reading private key: {e}")
            return None
    
    def copy_to_clipboard(self):
        """Copy private key to clipboard"""
        private_key = self.get_private_key()
        if not private_key:
            print("❌ No private key found")
            return False
        
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                subprocess.run("pbcopy", input=private_key.encode(), check=True)
                print("✅ Private key copied to clipboard (macOS)")
            elif system == "Linux":
                # Try xclip first, then xsel
                try:
                    subprocess.run(["xclip", "-selection", "clipboard"], 
                                 input=private_key.encode(), check=True)
                    print("✅ Private key copied to clipboard (Linux/xclip)")
                except:
                    subprocess.run(["xsel", "--clipboard", "--input"], 
                                 input=private_key.encode(), check=True)
                    print("✅ Private key copied to clipboard (Linux/xsel)")
            elif system == "Windows":
                subprocess.run("clip", input=private_key.encode(), check=True)
                print("✅ Private key copied to clipboard (Windows)")
            else:
                print(f"❌ Clipboard not supported on {system}")
                return False
                
            print("📋 You can now paste it in the orchestrator")
            return True
            
        except Exception as e:
            print(f"❌ Failed to copy to clipboard: {e}")
            print("💡 You can manually copy from: mcp-keys show --private")
            return False
    
    def export(self, output_file: Optional[str] = None, format: str = "pem"):
        """Export keys to file"""
        if not output_file:
            output_file = f"mcp_keys_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        
        output_path = Path(output_file)
        
        if format == "pem":
            # Export just private key (public can be derived)
            private_key = self.get_private_key()
            if private_key:
                with open(output_path, 'w') as f:
                    f.write(private_key)
                output_path.chmod(0o600)
                print(f"✅ Private key exported to: {output_path}")
        
        elif format == "json":
            # Export both keys and metadata
            config = self._load_config()
            with open(self.private_key_file, 'r') as f:
                private_key = f.read()
            with open(self.public_key_file, 'r') as f:
                public_key = f.read()
            
            export_data = {
                "config": config,
                "private_key": private_key,
                "public_key": public_key,
                "exported_at": datetime.now().isoformat()
            }
            
            with open(output_path, 'w') as f:
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
            if input_path.suffix == '.json':
                with open(input_path, 'r') as f:
                    data = json.load(f)
                
                self._save_keys(data['private_key'], data['public_key'])
                self._save_config(data['config'])
                print(f"✅ Keys imported from JSON: {input_file}")
            
            else:
                # Assume PEM format (private key only)
                with open(input_path, 'r') as f:
                    private_key = f.read()
                
                # Derive public key (would need cryptography library)
                print("⚠️  Importing PEM private key only")
                print("You'll need to regenerate the public key")
                
                with open(self.private_key_file, 'w') as f:
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
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_dir / f"mcp_keys_backup_{timestamp}.tar.gz"
        
        try:
            # Create tar archive
            import tarfile
            with tarfile.open(backup_file, 'w:gz') as tar:
                tar.add(self.private_key_file, arcname='id_rsa_mcp')
                tar.add(self.public_key_file, arcname='id_rsa_mcp.pub')
                tar.add(self.config_file, arcname='config.json')
            
            backup_file.chmod(0o600)
            print(f"✅ Backup created: {backup_file}")
            
            # Optional: encrypt with GPG if available
            try:
                subprocess.run(['gpg', '--version'], capture_output=True, check=True)
                response = input("Encrypt backup with GPG? (y/N): ")
                if response.lower() == 'y':
                    subprocess.run([
                        'gpg', '--cipher-algo', 'AES256',
                        '--symmetric', str(backup_file)
                    ], check=True)
                    backup_file.unlink()  # Remove unencrypted version
                    print(f"🔒 Encrypted backup: {backup_file}.gpg")
            except:
                pass
            
            return True
            
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False
    
    def authenticate(self, server_url: Optional[str] = None):
        """Test authentication with server"""
        if not server_url:
            config = self._load_config()
            server_url = config.get('server', 'http://localhost:8000')
        
        private_key = self.get_private_key()
        if not private_key:
            print("❌ No private key found")
            return False
        
        try:
            import requests
            response = requests.post(
                f"{server_url}/api/orchestrator/authenticate",
                json={"private_key": private_key}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Authentication successful!")
                print(f"🎫 Session token: {data['session_token'][:20]}...")
                print(f"⏱️  Expires in: {data['expires_in']} seconds")
                return True
            else:
                print(f"❌ Authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def _save_keys(self, private_key: str, public_key: str):
        """Save keys with proper permissions"""
        # Save private key (mode 600 - owner read/write only)
        with open(self.private_key_file, 'w') as f:
            f.write(private_key)
        self.private_key_file.chmod(0o600)
        
        # Save public key (mode 644 - owner write, others read)
        with open(self.public_key_file, 'w') as f:
            f.write(public_key)
        self.public_key_file.chmod(0o644)
    
    def _save_config(self, config: Dict[str, Any]):
        """Save configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        self.config_file.chmod(0o600)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration"""
        if not self.config_file.exists():
            return {}
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _calculate_fingerprint(self, public_key: str) -> str:
        """Calculate key fingerprint"""
        import hashlib
        return hashlib.sha256(public_key.encode()).hexdigest()

def main():
    parser = argparse.ArgumentParser(
        description='MCP Key Manager - Manage RSA keys for MCP orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcp-keys init                    # Initialize new keys
  mcp-keys show                    # Show key information
  mcp-keys copy                    # Copy private key to clipboard
  mcp-keys auth                    # Test authentication
  mcp-keys backup                  # Create encrypted backup
  mcp-keys export -o keys.json    # Export keys to file
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize new key pair')
    init_parser.add_argument('--server', default='http://localhost:8000', 
                            help='MCP server URL')
    init_parser.add_argument('--name', help='Your name for key identification')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Display key information')
    show_parser.add_argument('--private', action='store_true', 
                            help='Also show private key')
    
    # Copy command
    copy_parser = subparsers.add_parser('copy', help='Copy private key to clipboard')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export keys to file')
    export_parser.add_argument('-o', '--output', help='Output file')
    export_parser.add_argument('-f', '--format', choices=['pem', 'json'], 
                              default='json', help='Export format')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import keys from file')
    import_parser.add_argument('file', help='Input file')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create encrypted backup')
    
    # Auth command
    auth_parser = subparsers.add_parser('auth', help='Test authentication')
    auth_parser.add_argument('--server', help='MCP server URL')
    
    args = parser.parse_args()
    
    # Initialize manager
    manager = MCPKeyManager()
    
    # Execute command
    if args.command == 'init':
        manager.init(args.server, args.name)
    elif args.command == 'show':
        manager.show(args.private)
    elif args.command == 'copy':
        manager.copy_to_clipboard()
    elif args.command == 'export':
        manager.export(args.output, args.format)
    elif args.command == 'import':
        manager.import_keys(args.file)
    elif args.command == 'backup':
        manager.backup()
    elif args.command == 'auth':
        manager.authenticate(args.server)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()