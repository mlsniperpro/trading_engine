"""
Docker-based deployment for Trading Engine.
Deploys using Docker and Docker Compose for easy, reliable deployment.

Usage:
    uv run deploy-docker              # Deploy to server from config
    uv run deploy-docker --server IP  # Deploy to specific server
"""

import subprocess
import sys
import os
from pathlib import Path
import argparse
import json
import time

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Colors:
    """Terminal colors for pretty output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(message: str):
    """Print a header message."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")


def print_step(step: int, message: str):
    """Print a step message."""
    print(f"{Colors.CYAN}[Step {step}]{Colors.END} {message}")


def print_success(message: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓{Colors.END} {message}")


def print_error(message: str):
    """Print an error message."""
    print(f"{Colors.RED}✗{Colors.END} {message}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.END} {message}")


def run_command(cmd: str, description: str, check: bool = True) -> tuple[bool, str]:
    """Run a shell command and return success status and output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=check
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        if check:
            print_error(f"{description} failed: {e.stderr}")
        return False, e.stderr


def load_config() -> dict:
    """Load deployment configuration."""
    config_path = Path("deploy.config.json")

    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)

    # Try to load from .env if config doesn't exist
    default_server = os.getenv("DEPLOY_SERVER_IP")

    return {
        "servers": {},
        "default_server": default_server,
        "app_user": "root",
        "app_dir": "/opt/trading_engine",
    }


def test_ssh_connection(server_ip: str) -> bool:
    """Test SSH connection to server."""
    print_step("*", f"Testing SSH connection to {server_ip}...")

    success, _ = run_command(
        f'ssh -o ConnectTimeout=10 -o BatchMode=yes root@{server_ip} "echo OK"',
        "SSH connection test",
        check=False
    )

    if success:
        print_success(f"SSH connection to {server_ip} successful")
    else:
        print_error(f"Cannot connect to {server_ip}")
        print_warning("Make sure:")
        print("  1. Your SSH key is added to the server")
        print("  2. The server IP is correct")
        print("  3. Port 22 is open in the firewall")

    return success


def deploy_with_docker(server_ip: str, config: dict):
    """Deploy the application using Docker."""
    print_header("Trading Engine Docker Deployment")

    app_dir = config.get("app_dir", "/opt/trading_engine")

    print(f"{Colors.BOLD}Server:{Colors.END} {server_ip}")
    print(f"{Colors.BOLD}App Directory:{Colors.END} {app_dir}")
    print(f"{Colors.BOLD}Method:{Colors.END} Docker + Docker Compose")
    print()

    # Confirm deployment
    response = input(f"{Colors.YELLOW}Continue with deployment? [y/N]:{Colors.END} ")
    if response.lower() != 'y':
        print("Deployment cancelled.")
        return

    # Test SSH connection
    if not test_ssh_connection(server_ip):
        return

    # Step 1: Install Docker
    print_step(1, "Installing Docker and Docker Compose...")
    run_command(
        f'''ssh root@{server_ip} "
            apt-get update &&
            apt-get install -y ca-certificates curl &&
            install -m 0755 -d /etc/apt/keyrings &&
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc &&
            chmod a+r /etc/apt/keyrings/docker.asc &&
            echo \\"deb [arch=\\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \\$(. /etc/os-release && echo \\$VERSION_CODENAME) stable\\" | tee /etc/apt/sources.list.d/docker.list > /dev/null &&
            apt-get update &&
            apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        "''',
        "Docker installation"
    )
    print_success("Docker installed")

    # Step 2: Create app directory
    print_step(2, "Setting up application directory...")
    run_command(
        f'ssh root@{server_ip} "mkdir -p {app_dir}"',
        "Directory creation"
    )
    # Also update the config to use the correct directory
    config["app_dir"] = app_dir
    print_success(f"Directory '{app_dir}' ready")

    # Step 3: Copy project files
    print_step(3, "Copying project files...")
    project_root = Path(__file__).parent.parent.parent.parent

    # Copy files with proper structure - use trailing slash on source to copy contents, not directory
    run_command(
        f'''rsync -avz --delete \
               --exclude='.git' \
               --exclude='__pycache__' \
               --exclude='*.pyc' \
               --exclude='.venv' \
               --exclude='logs/' \
               --exclude='.env' \
               --exclude='deploy.config.json' \
               --exclude='.codespaces' \
               --exclude='.oryx' \
               {project_root}/ root@{server_ip}:{app_dir}/''',
        "File copy"
    )
    print_success("Files copied")

    # Check if files are in root or nested
    success, output = run_command(
        f'ssh root@{server_ip} "cd {app_dir} && ls -1 Dockerfile 2>/dev/null || echo NOT_FOUND"',
        "Check Dockerfile location",
        check=False
    )

    if "NOT_FOUND" in output:
        # Files are nested - need to move them up
        print("  Files are nested, fixing structure...")
        run_command(
            f'''ssh root@{server_ip} "
                cd {app_dir} &&
                if [ -d trading_engine ]; then
                    mv trading_engine/* . 2>/dev/null || true
                    mv trading_engine/.* . 2>/dev/null || true
                    rmdir trading_engine 2>/dev/null || true
                fi
            "''',
            "Fix nested structure",
            check=False
        )

    # Final verification
    success, output = run_command(
        f'ssh root@{server_ip} "cd {app_dir} && ls -1 Dockerfile docker-compose.yml pyproject.toml 2>&1"',
        "Verify files",
        check=False
    )
    if not success or "Dockerfile" not in output:
        print_error("Critical files still not found after fix!")
        print(f"Output: {output}")
        sys.exit(1)

    print_success("File structure verified")

    # Step 4: Copy .env file
    print_step(4, "Configuring environment variables...")

    # Look for .env in project root
    env_file = project_root / ".env"

    # If not found, try current directory
    if not env_file.exists():
        env_file = Path(".env")

    if env_file.exists():
        print(f"  Found .env at: {env_file.absolute()}")
        run_command(
            f'scp {env_file.absolute()} root@{server_ip}:{app_dir}/.env',
            ".env file upload"
        )
        run_command(
            f'ssh root@{server_ip} "chmod 600 {app_dir}/.env"',
            ".env permissions"
        )
        print_success(".env file uploaded")
    else:
        print_warning("No .env file found locally")
        print_warning(f"  Looked in: {project_root / '.env'}")
        print_warning(f"  Looked in: {Path('.env').absolute()}")
        # Create minimal .env on server
        run_command(
            f'''ssh root@{server_ip} "cat > {app_dir}/.env << 'EOF'
ENVIRONMENT=production
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
EOF
"''',
            ".env template creation"
        )
        print_warning("Created minimal .env - add your API keys manually!")

    # Step 5: Build Docker image
    print_step(5, "Building Docker image (this may take a few minutes)...")
    success, output = run_command(
        f'ssh root@{server_ip} "cd {app_dir} && docker compose build"',
        "Docker build",
        check=False
    )
    if not success:
        print_error("Docker build failed!")
        print(output)
        sys.exit(1)
    print_success("Docker image built")

    # Step 6: Configure firewall
    print_step(6, "Configuring firewall...")
    run_command(
        f'''ssh root@{server_ip} "
            apt-get install -y ufw &&
            ufw --force enable &&
            ufw allow 22/tcp &&
            ufw allow 8000/tcp
        "''',
        "Firewall configuration"
    )
    print_success("Firewall configured")

    # Step 7: Start containers
    print_step(7, "Starting Docker containers...")
    # Stop any existing containers first
    run_command(
        f'ssh root@{server_ip} "cd {app_dir} && docker compose down"',
        "Stop existing containers",
        check=False
    )

    success, output = run_command(
        f'ssh root@{server_ip} "cd {app_dir} && docker compose up -d"',
        "Container start",
        check=False
    )
    if not success:
        print_error("Failed to start containers!")
        print(output)
        sys.exit(1)
    print_success("Containers started")

    # Wait for service to be ready
    print("Waiting for service to start...")
    time.sleep(5)

    # Final summary
    print_header("Deployment Complete!")
    print(f"{Colors.GREEN}✓{Colors.END} API Endpoint:   http://{server_ip}:8000")
    print(f"{Colors.GREEN}✓{Colors.END} Health Check:   http://{server_ip}:8000/health")
    print(f"{Colors.GREEN}✓{Colors.END} API Docs:       http://{server_ip}:8000/docs")
    print()
    print(f"{Colors.BOLD}Useful Commands:{Colors.END}")
    print(f"  Check status:   ssh root@{server_ip} 'cd {app_dir} && docker compose ps'")
    print(f"  View logs:      ssh root@{server_ip} 'cd {app_dir} && docker compose logs -f'")
    print(f"  Restart:        ssh root@{server_ip} 'cd {app_dir} && docker compose restart'")
    print(f"  Stop:           ssh root@{server_ip} 'cd {app_dir} && docker compose down'")
    print()

    # Test the API
    print("Testing API endpoint...")
    time.sleep(3)
    success, output = run_command(
        f'curl -s http://{server_ip}:8000/health',
        "API health check",
        check=False
    )

    if success and output:
        print_success("API is responding!")
        print(f"  Response: {output.strip()}")
    else:
        print_warning("API not responding yet, give it a moment")
        print(f"  Check logs: ssh root@{server_ip} 'cd {app_dir} && docker compose logs'")


def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description="Deploy Trading Engine with Docker")
    parser.add_argument("--server", "-s", help="Server IP address")

    args = parser.parse_args()
    config = load_config()

    # Get server IP
    server_ip = args.server

    if not server_ip and config.get("default_server"):
        server_ip = config["default_server"]
        print(f"Using default server: {server_ip}")

    if not server_ip:
        print_header("Trading Engine Docker Deployment")
        server_ip = input(f"{Colors.BOLD}Enter Hetzner server IP:{Colors.END} ").strip()

    if not server_ip:
        print_error("Server IP is required")
        sys.exit(1)

    # Run deployment
    deploy_with_docker(server_ip, config)


if __name__ == "__main__":
    main()
