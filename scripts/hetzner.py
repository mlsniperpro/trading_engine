"""
Hetzner Cloud server setup automation.
Creates and configures a Hetzner VPS from the command line using Hetzner Cloud API.

Usage:
    uv run hetzner-setup              # Interactive setup
    uv run hetzner-setup --api-key XXX --name my-server
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Optional
import time

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system env vars only

try:
    from hcloud import Client
    from hcloud.images import Image
    from hcloud.server_types import ServerType
    from hcloud.locations import Location
    from hcloud.ssh_keys import SSHKey
    from hcloud.firewalls import Firewall, FirewallRule
except ImportError:
    print("ERROR: hcloud library not found. Installing...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "hcloud"], check=True)
    from hcloud import Client
    from hcloud.images import Image
    from hcloud.server_types import ServerType
    from hcloud.locations import Location
    from hcloud.ssh_keys import SSHKey
    from hcloud.firewalls import Firewall, FirewallRule


class Colors:
    """Terminal colors."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(message: str):
    """Print header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message:^70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")


def print_step(step: str, message: str):
    """Print step."""
    print(f"{Colors.CYAN}[{step}]{Colors.END} {message}")


def print_success(message: str):
    """Print success."""
    print(f"{Colors.GREEN}✓{Colors.END} {message}")


def print_error(message: str):
    """Print error."""
    print(f"{Colors.RED}✗{Colors.END} {message}")


def print_warning(message: str):
    """Print warning."""
    print(f"{Colors.YELLOW}⚠{Colors.END} {message}")


def get_ssh_public_key() -> Optional[str]:
    """Get SSH public key from user's .ssh directory."""
    ssh_dir = Path.home() / ".ssh"

    # Look for common key files
    key_files = [
        "id_ed25519.pub",
        "id_rsa.pub",
        "id_ecdsa.pub",
    ]

    for key_file in key_files:
        key_path = ssh_dir / key_file
        if key_path.exists():
            return key_path.read_text().strip()

    return None


def create_server(
    api_key: str,
    server_name: str,
    server_type: str = "cpx21",
    location: str = "nbg1",
    ssh_key_name: str = "trading-engine-key"
) -> dict:
    """Create a Hetzner Cloud server."""

    print_header("Hetzner Cloud Server Setup")

    # Initialize client
    print_step("1/7", "Connecting to Hetzner Cloud API...")
    client = Client(token=api_key)
    print_success("Connected to Hetzner Cloud")

    # Get or create SSH key
    print_step("2/7", "Setting up SSH key...")

    ssh_pub_key = get_ssh_public_key()
    if not ssh_pub_key:
        print_error("No SSH public key found in ~/.ssh/")
        print("Please generate one with: ssh-keygen -t ed25519")
        sys.exit(1)

    # Check if SSH key already exists
    existing_keys = client.ssh_keys.get_all(name=ssh_key_name)

    if existing_keys:
        ssh_key = existing_keys[0]
        print_success(f"Using existing SSH key: {ssh_key_name}")
    else:
        ssh_key = client.ssh_keys.create(
            name=ssh_key_name,
            public_key=ssh_pub_key
        )
        print_success(f"SSH key created: {ssh_key_name}")

    # Create firewall
    print_step("3/7", "Creating firewall rules...")

    firewall_name = f"{server_name}-firewall"
    existing_firewalls = client.firewalls.get_all(name=firewall_name)

    if existing_firewalls:
        firewall = existing_firewalls[0]
        print_success(f"Using existing firewall: {firewall_name}")
    else:
        firewall_response = client.firewalls.create(
            name=firewall_name,
            rules=[
                FirewallRule(
                    direction=FirewallRule.DIRECTION_IN,
                    protocol=FirewallRule.PROTOCOL_TCP,
                    source_ips=["0.0.0.0/0", "::/0"],
                    port="22",
                    description="SSH"
                ),
                FirewallRule(
                    direction=FirewallRule.DIRECTION_IN,
                    protocol=FirewallRule.PROTOCOL_TCP,
                    source_ips=["0.0.0.0/0", "::/0"],
                    port="8000",
                    description="API"
                ),
            ]
        )
        firewall = firewall_response.firewall
        print_success("Firewall created with SSH (22) and API (8000) ports")

    # Check if server already exists
    print_step("4/7", "Checking if server already exists...")
    existing_servers = client.servers.get_all(name=server_name)

    if existing_servers:
        server = existing_servers[0]
        print_warning(f"Server '{server_name}' already exists!")
        print(f"  Status: {server.status}")
        print(f"  IP: {server.public_net.ipv4.ip}")

        response = input(f"\n{Colors.YELLOW}Use existing server? [y/N]:{Colors.END} ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(0)

        return {
            "server_name": server.name,
            "server_ip": server.public_net.ipv4.ip,
            "server_type": server.server_type.name,
            "location": server.datacenter.location.name,
            "status": server.status,
            "existing": True
        }

    # Get server type
    print_step("5/7", f"Configuring server type: {server_type}...")
    try:
        server_type_obj = client.server_types.get_by_name(server_type)
    except Exception as e:
        print_error(f"Invalid server type: {server_type}")
        print("Available types: cx11, cx21, cpx11, cpx21, cpx31, cpx41")
        sys.exit(1)

    print(f"  CPU: {server_type_obj.cores} cores")
    print(f"  RAM: {server_type_obj.memory} GB")
    print(f"  Disk: {server_type_obj.disk} GB")
    # Price formatting - handle both dict and object formats
    try:
        if hasattr(server_type_obj.prices[0], 'price_monthly'):
            price = server_type_obj.prices[0].price_monthly.gross
        else:
            price = server_type_obj.prices[0]['price_monthly']['gross']
        print(f"  Price: €{price}/month")
    except (KeyError, AttributeError, IndexError):
        pass  # Skip price display if format is unexpected

    # Get image
    image = client.images.get_by_name_and_architecture("ubuntu-22.04", "x86")
    print_success(f"Image: Ubuntu 22.04 LTS")

    # Get location
    location_obj = client.locations.get_by_name(location)
    print_success(f"Location: {location_obj.city}, {location_obj.country}")

    # Create server
    print_step("6/7", f"Creating server '{server_name}'...")
    # Show billing warning if price is available
    try:
        if hasattr(server_type_obj.prices[0], 'price_hourly'):
            hourly_price = server_type_obj.prices[0].price_hourly.gross
        else:
            hourly_price = server_type_obj.prices[0]['price_hourly']['gross']
        print(f"{Colors.YELLOW}This will start billing at €{hourly_price}/hour{Colors.END}")
    except (KeyError, AttributeError, IndexError):
        print(f"{Colors.YELLOW}This will start billing immediately{Colors.END}")

    response = client.servers.create(
        name=server_name,
        server_type=server_type_obj,
        image=image,
        ssh_keys=[ssh_key],
        location=location_obj,
        firewalls=[firewall]
    )

    server = response.server
    action = response.action

    print(f"  Server ID: {server.id}")
    print("  Waiting for server to be ready...", end="", flush=True)

    # Wait for server to be ready
    while action.status == "running":
        time.sleep(2)
        action = client.actions.get_by_id(action.id)
        print(".", end="", flush=True)

    print(" Done!")

    if action.status == "success":
        print_success("Server created successfully!")
    else:
        print_error(f"Server creation failed: {action.error}")
        sys.exit(1)

    # Refresh server data to get IP
    server = client.servers.get_by_id(server.id)
    server_ip = server.public_net.ipv4.ip

    print_step("7/7", "Server is ready!")
    print()

    return {
        "server_name": server.name,
        "server_ip": server_ip,
        "server_type": server_type,
        "location": location,
        "status": server.status,
        "existing": False
    }


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Create and configure Hetzner Cloud server for Trading Engine"
    )
    parser.add_argument(
        "--api-key",
        help="Hetzner Cloud API key (or set HETZNER_API_KEY env var)"
    )
    parser.add_argument(
        "--name",
        default="trading-engine",
        help="Server name (default: trading-engine)"
    )
    parser.add_argument(
        "--type",
        default="cpx21",
        help="Server type (default: cpx21). Options: cx11, cx21, cpx11, cpx21, cpx31, cpx41"
    )
    parser.add_argument(
        "--location",
        default="nbg1",
        help="Location (default: nbg1 - Nuremberg). Options: nbg1, fsn1, hel1, ash"
    )

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or os.getenv("HETZNER_API_KEY")

    if not api_key:
        print_header("Hetzner Cloud API Key Required")
        print("To get your API key:")
        print("1. Go to https://console.hetzner.cloud/")
        print("2. Select your project (or create one)")
        print("3. Go to 'Security' → 'API Tokens'")
        print("4. Click 'Generate API Token'")
        print("5. Give it a name and select 'Read & Write' permissions")
        print("6. Copy the token")
        print()
        print("Then either:")
        print(f"  • Set environment variable: export HETZNER_API_KEY=your_token")
        print(f"  • Use --api-key flag: uv run hetzner-setup --api-key your_token")
        print()

        api_key = input(f"{Colors.BOLD}Enter your Hetzner API key:{Colors.END} ").strip()

        if not api_key:
            print_error("API key is required")
            sys.exit(1)

    # Create server
    try:
        result = create_server(
            api_key=api_key,
            server_name=args.name,
            server_type=args.type,
            location=args.location
        )

        # Print summary
        print_header("Setup Complete!")
        print(f"{Colors.BOLD}Server Details:{Colors.END}")
        print(f"  Name:     {result['server_name']}")
        print(f"  IP:       {Colors.GREEN}{result['server_ip']}{Colors.END}")
        print(f"  Type:     {result['server_type']}")
        print(f"  Location: {result['location']}")
        print(f"  Status:   {result['status']}")
        print()

        if result['existing']:
            print(f"{Colors.YELLOW}Using existing server{Colors.END}")
        else:
            print(f"{Colors.GREEN}New server created!{Colors.END}")

        print()
        print(f"{Colors.BOLD}Next Steps:{Colors.END}")
        print()
        print("1. Test SSH connection:")
        print(f"   ssh root@{result['server_ip']}")
        print()
        print("2. Deploy your application:")
        print(f"   uv run deploy --server {result['server_ip']} --save")
        print()
        print("3. Access your API:")
        print(f"   http://{result['server_ip']}:8000")
        print()

        # Save to config
        try:
            import json
            config_path = Path("deploy.config.json")

            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
            else:
                config = {
                    "servers": {},
                    "default_server": None,
                    "app_user": "algoengine",
                    "app_dir": "/home/algoengine/trading_engine",
                    "python_version": "3.12"
                }

            config["servers"][args.name] = result['server_ip']
            if not config.get("default_server"):
                config["default_server"] = result['server_ip']

            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            print_success(f"Server IP saved to deploy.config.json")

        except Exception as e:
            print_warning(f"Could not save config: {e}")

    except Exception as e:
        print_error(f"Setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
