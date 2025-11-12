# Trading Engine

A Python-based trading engine API built with FastAPI.

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

Install dependencies using uv:

```bash
uv sync
```

### Running the API

You can run the API server in several ways:

**Option 1: Using the CLI entry point**
```bash
uv run trading-engine
```

**Option 2: Using uvicorn directly**
```bash
uv run uvicorn trading_engine.main:app --reload
```

The API will be available at `http://localhost:8000`

### API Endpoints

- `GET /` - Hello world endpoint
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

## Deployment

### Prerequisites

**Need a server first?**

**Option 1: Command Line (Easiest)**
```bash
# Get API key from https://console.hetzner.cloud/ → Security → API Tokens
export HETZNER_API_KEY="your_token_here"

# Create server automatically
uv run hetzner-setup --name trading-engine --type cpx21
```
See [deployment/HETZNER_CLI.md](deployment/HETZNER_CLI.md) for full guide.

**Option 2: Web Console**
See [deployment/HETZNER_SETUP.md](deployment/HETZNER_SETUP.md) for manual setup via Hetzner web interface.

### Deploy to Hetzner VPS

Automated deployment using `uv`:

```bash
# Initial deployment to Hetzner
uv run deploy --server YOUR_SERVER_IP

# Or just:
uv run deploy
# (will prompt for server IP)

# Save server as default for future deployments
uv run deploy --server YOUR_SERVER_IP --save
```

### Quick Update

To deploy code changes to an existing server:

```bash
# Update deployment (faster, only copies files and restarts)
uv run update --server YOUR_SERVER_IP

# Or use saved default server:
uv run update
```

### Configuration

The deployment system saves configuration in `deploy.config.json` (auto-generated):

```json
{
  "servers": {
    "production": "95.216.123.456",
    "staging": "95.216.123.457"
  },
  "default_server": "95.216.123.456",
  "app_user": "algoengine",
  "app_dir": "/home/algoengine/trading_engine"
}
```

**Full deployment guide:** See [deployment/DEPLOYMENT.md](deployment/DEPLOYMENT.md)

## Development

The project uses a `src` layout with the following structure:

```
trading_engine/
├── src/
│   └── trading_engine/
│       ├── __init__.py
│       ├── main.py           # FastAPI application
│       └── deploy.py         # Deployment automation
├── deployment/
│   ├── scripts/              # Legacy bash scripts (optional)
│   ├── systemd/
│   │   └── trading-engine.service
│   └── DEPLOYMENT.md         # Detailed deployment guide
├── pyproject.toml            # Project config with uv commands
├── .env.example              # Environment template
├── .gitignore
└── README.md
```

### Available Commands

The project exposes these `uv` commands:

```bash
uv run trading-engine   # Run the API server
uv run deploy          # Deploy to Hetzner VPS
uv run update          # Update existing deployment
```
