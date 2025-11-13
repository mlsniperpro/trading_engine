"""
View logs from Hetzner deployment - similar to 'flyctl logs'

Usage:
    uv run logs              # Follow logs in real-time (like flyctl logs)
    uv run logs --tail 100   # Last 100 lines
    uv run logs --errors     # Only errors
    uv run logs --since 1h   # Last hour
"""

import subprocess
import sys
import argparse
import os
from pathlib import Path

# Load environment or use default
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def get_server_ip():
    """Get server IP from environment or config."""
    # Try environment variable
    server_ip = os.getenv('HETZNER_SERVER_IP', '116.203.216.207')
    return server_ip


def print_header(message):
    """Print colored header."""
    print(f"{Colors.CYAN}{Colors.BOLD}{message}{Colors.ENDC}")


def print_info(message):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {message}{Colors.ENDC}")


def print_error(message):
    """Print error message."""
    print(f"{Colors.RED}✗ {message}{Colors.ENDC}")


def run_ssh_command(server_ip, command, stream=False):
    """Run command via SSH."""
    ssh_cmd = f'ssh -o StrictHostKeyChecking=no root@{server_ip} "{command}"'

    if stream:
        # Stream output in real-time
        try:
            process = subprocess.Popen(
                ssh_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in process.stdout:
                print(line, end='')

            process.wait()
            return process.returncode == 0
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Stopped monitoring logs{Colors.ENDC}")
            return True
    else:
        # Run and capture output
        result = subprocess.run(
            ssh_cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print_error(f"Command failed: {result.stderr}")
            return False
        print(result.stdout)
        return True


def follow_logs(server_ip, tail=None):
    """Follow logs in real-time (like flyctl logs)."""
    tail_arg = f"--tail {tail}" if tail else "--tail 100"
    command = f"docker logs -f {tail_arg} --timestamps trading-engine"

    print_header("📊 Following logs from Hetzner server...")
    print_info(f"Server: {server_ip}")
    print_info("Press Ctrl+C to stop")
    print()

    return run_ssh_command(server_ip, command, stream=True)


def view_logs(server_ip, tail=None, since=None, errors_only=False, grep=None):
    """View logs with options."""
    command = "docker logs trading-engine"

    if tail:
        command += f" --tail {tail}"

    if since:
        command += f" --since {since}"

    if not tail and not since:
        command += " --tail 200"

    command += " --timestamps"
    command += " 2>&1"  # Capture both stdout and stderr

    if errors_only:
        command += ' | grep -E "(ERROR|CRITICAL)"'
    elif grep:
        command += f' | grep "{grep}"'

    print_header(f"📄 Viewing logs from Hetzner server...")
    print_info(f"Server: {server_ip}")
    print()

    return run_ssh_command(server_ip, command, stream=False)


def show_stats(server_ip):
    """Show log statistics."""
    print_header("📈 Log Statistics")
    print_info(f"Server: {server_ip}")
    print()

    commands = {
        "Total entries": "docker logs trading-engine 2>&1 | wc -l",
        "Errors": "docker logs trading-engine 2>&1 | grep -c ERROR || echo 0",
        "Warnings": "docker logs trading-engine 2>&1 | grep -c WARNING || echo 0",
        "DEX Swaps": "docker logs trading-engine 2>&1 | grep -c 'Swap #' || echo 0",
        "Arbitrage": "docker logs trading-engine 2>&1 | grep -c ARBITRAGE || echo 0",
    }

    for label, cmd in commands.items():
        result = subprocess.run(
            f'ssh root@{server_ip} "{cmd}"',
            shell=True,
            capture_output=True,
            text=True
        )
        count = result.stdout.strip()
        print(f"  {label}: {Colors.GREEN}{count}{Colors.ENDC}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='View logs from Hetzner deployment (like flyctl logs)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run logs                    # Follow logs in real-time
  uv run logs --tail 200         # Show last 200 lines
  uv run logs --since 1h         # Show last hour
  uv run logs --errors           # Show only errors
  uv run logs --grep ARBITRAGE   # Filter for specific text
  uv run logs --stats            # Show statistics
        """
    )

    parser.add_argument(
        '--tail', '-n',
        type=int,
        help='Number of lines to show'
    )

    parser.add_argument(
        '--since',
        type=str,
        help='Show logs since timestamp (e.g., 1h, 30m, 2024-01-15)'
    )

    parser.add_argument(
        '--errors',
        action='store_true',
        help='Show only errors'
    )

    parser.add_argument(
        '--grep',
        type=str,
        help='Filter logs by text'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show log statistics'
    )

    parser.add_argument(
        '--server',
        type=str,
        help='Server IP address (default: from env or 116.203.216.207)'
    )

    parser.add_argument(
        '--follow', '-f',
        action='store_true',
        help='Follow logs in real-time (default behavior)'
    )

    args = parser.parse_args()

    # Get server IP
    server_ip = args.server or get_server_ip()

    try:
        if args.stats:
            # Show statistics
            show_stats(server_ip)
        elif args.tail or args.since or args.errors or args.grep:
            # View logs with options
            view_logs(
                server_ip,
                tail=args.tail,
                since=args.since,
                errors_only=args.errors,
                grep=args.grep
            )
        else:
            # Default: follow logs (like flyctl logs)
            follow_logs(server_ip, tail=args.tail)

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}✓ Stopped{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
