.PHONY: start stop install clean deploy logs help

start:
	@uv run start

stop:
	@pkill -f "trading-engine" || true

install:
	@uv sync

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true

deploy:
	@uv run python scripts/deploy_docker.py

logs:
	@uv run python scripts/logs.py

hetzner-setup:
	@uv run python scripts/hetzner.py

help:
	@echo "Trading Engine - Available Commands:"
	@echo ""
	@echo "  make start          - Start the trading engine"
	@echo "  make stop           - Stop the trading engine"
	@echo "  make install        - Install dependencies"
	@echo "  make clean          - Clean Python cache files"
	@echo "  make deploy         - Deploy to Hetzner with Docker"
	@echo "  make logs           - View logs from Hetzner server"
	@echo "  make hetzner-setup  - Create Hetzner Cloud server"
	@echo ""
	@echo "Direct commands:"
	@echo "  uv run start                      - Start the engine"
	@echo "  uv run python scripts/deploy_docker.py  - Deploy"
	@echo "  uv run python scripts/logs.py           - View logs"
