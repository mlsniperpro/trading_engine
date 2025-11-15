# Algo Engine - Hetzner Deployment Guide

Complete guide for deploying the Algorithmic Trading Engine on Hetzner VPS.

---

## Table of Contents
1. [Server Selection](#server-selection)
2. [Initial Server Setup](#initial-server-setup)
3. [System Requirements](#system-requirements)
4. [Installation Steps](#installation-steps)
5. [Configuration](#configuration)
6. [Running the Engine](#running-the-engine)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)
9. [Security Hardening](#security-hardening)

---

## 1. Server Selection

### Recommended Hetzner VPS Plans

**Option 1: CX21 (Development/Testing)**
- **vCPU**: 2 cores
- **RAM**: 4 GB
- **Storage**: 40 GB SSD
- **Price**: ~€5.83/month
- **Use Case**: Testing, backtesting, low-volume trading (1-5 pairs)

**Option 2: CPX31 (Production - Recommended)**
- **vCPU**: 4 cores (AMD EPYC)
- **RAM**: 8 GB
- **Storage**: 160 GB SSD
- **Price**: ~€13.90/month
- **Use Case**: Production trading, 50-100 pairs, full strategy suite

**Option 3: CPX41 (High Performance)**
- **vCPU**: 8 cores (AMD EPYC)
- **RAM**: 16 GB
- **Storage**: 240 GB SSD
- **Price**: ~€26.90/month
- **Use Case**: 100+ pairs, multiple strategies, high-frequency scanning

### Why Hetzner?
- ✅ **Low Latency**: European data centers (close to major exchanges)
- ✅ **Cost-Effective**: Best price/performance ratio
- ✅ **High Uptime**: 99.9% SLA
- ✅ **Fast SSD**: NVMe storage for DuckDB performance
- ✅ **DDoS Protection**: Built-in protection

---

## 2. Initial Server Setup

### Step 1: Create Hetzner VPS

1. Go to [Hetzner Cloud Console](https://console.hetzner.cloud/)
2. Click **New Project** → Name it `algo-engine`
3. Click **Add Server**:
   - **Location**: Nuremberg (eu-central, lowest latency to exchanges)
   - **Image**: Ubuntu 22.04 LTS
   - **Type**: CPX31 (recommended)
   - **SSH Key**: Add your public SSH key
   - **Firewall**: Create firewall (details below)
4. Click **Create & Buy Now**

### Step 2: Configure Firewall

Create a firewall in Hetzner Cloud Console:

**Inbound Rules**:
```
SSH (22)        → Your IP only (e.g., 203.0.113.0/32)
HTTPS (443)     → 0.0.0.0/0 (for API access, optional)
Custom (8000)   → 0.0.0.0/0 (for FastAPI monitoring, optional)
```

**Outbound Rules**:
```
All protocols   → 0.0.0.0/0 (required for exchange connections)
```

### Step 3: Initial SSH Connection

```bash
# SSH into your new server
ssh root@<your-server-ip>

# Update system packages
apt update && apt upgrade -y

# Set timezone to UTC (important for trading)
timedatectl set-timezone UTC

# Verify time is correct
date
```

---

## 3. System Requirements

### Software Stack
- **OS**: Ubuntu 22.04 LTS
- **Python**: 3.12+
- **Database**: DuckDB (embedded, no separate installation)
- **Reverse Proxy**: Nginx (optional, for API)
- **Process Manager**: systemd (built-in)

### Resource Usage (CPX31)
```
CPU:      ~30-50% (scanning 100 pairs)
RAM:      ~3-4 GB (DuckDB + Python + caching)
Disk:     ~500 MB (databases) + 200 MB (logs)
Network:  ~10-50 Mbps (WebSocket streams)
```

---

## 4. Installation Steps

### Step 1: Install Python 3.12

```bash
# Add deadsnakes PPA for Python 3.12
apt install -y software-properties-common
add-apt-repository ppa:deadsnakes/ppa -y
apt update

# Install Python 3.12 and dependencies
apt install -y python3.12 python3.12-venv python3.12-dev
apt install -y python3-pip git curl build-essential

# Verify installation
python3.12 --version
```

### Step 2: Create System User (Security Best Practice)

```bash
# Create dedicated user for algo engine
useradd -m -s /bin/bash algoengine

# Add to necessary groups
usermod -aG sudo algoengine

# Switch to algoengine user
su - algoengine
```

### Step 3: Clone Repository & Setup

```bash
# Create project directory
mkdir -p /home/algoengine/algo-engine
cd /home/algoengine/algo-engine

# Initialize git (if deploying from git)
git init
git remote add origin <your-repo-url>
git pull origin main

# OR: Upload code via SCP from local machine
# scp -r /path/to/algo-engine root@<server-ip>:/home/algoengine/
```

### Step 4: Create Virtual Environment

```bash
# Create venv
python3.12 -m venv venv

# Activate venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Step 5: Setup Data Directories

```bash
# Create data directories
mkdir -p /home/algoengine/algo-engine/data/{binance/spot,binance/futures,bybit/spot,dex/ethereum,dex/solana,logs}

# Set permissions
chmod 755 /home/algoengine/algo-engine/data
```

---

## 5. Configuration

### Step 1: Environment Variables

```bash
# Create .env file
cd /home/algoengine/algo-engine
nano .env
```

**`.env` File**:
```bash
# Exchange API Keys
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here
BYBIT_API_KEY=your_bybit_api_key_here
BYBIT_API_SECRET=your_bybit_api_secret_here

# Firebase (for config storage)
FIREBASE_CREDENTIALS_PATH=/home/algoengine/algo-engine/config/firebase-credentials.json
FIRESTORE_PROJECT_ID=your_firestore_project_id

# SendGrid (for email alerts)
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxx
ALERT_EMAIL=your_email@example.com
ALERT_FROM_EMAIL=algo-engine@yourdomain.com

# System Configuration
ENVIRONMENT=production
LOG_LEVEL=INFO
DATA_DIR=/home/algoengine/algo-engine/data

# MetaTrader 5 (if using Forex)
MT5_LOGIN=your_mt5_account_number
MT5_PASSWORD=your_mt5_password
MT5_SERVER=your_broker_server

# DEX/Web3 (if using DEX trading)
INFURA_API_KEY=your_infura_key
ALCHEMY_API_KEY=your_alchemy_key
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
```

```bash
# Set secure permissions
chmod 600 .env
```

### Step 2: Upload Firebase Credentials

```bash
# Upload firebase-credentials.json from local machine
# scp /path/to/firebase-credentials.json algoengine@<server-ip>:/home/algoengine/algo-engine/config/
```

### Step 3: Verify Configuration

```bash
# Test configuration loading
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('BINANCE_API_KEY'))"
```

---

## 6. Running the Engine

### Option 1: Run Manually (Testing)

```bash
# Activate venv
cd /home/algoengine/algo-engine
source venv/bin/activate

# Run engine
python main.py
```

### Option 2: Run with systemd (Production)

Create systemd service file:

```bash
sudo nano /etc/systemd/system/algo-engine.service
```

**Service File**:
```ini
[Unit]
Description=Algorithmic Trading Engine
After=network.target

[Service]
Type=simple
User=algoengine
Group=algoengine
WorkingDirectory=/home/algoengine/algo-engine
Environment="PATH=/home/algoengine/algo-engine/venv/bin"
ExecStart=/home/algoengine/algo-engine/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:/home/algoengine/algo-engine/data/logs/app.log
StandardError=append:/home/algoengine/algo-engine/data/logs/errors.log

# Resource limits
LimitNOFILE=65535
MemoryMax=6G
CPUQuota=300%

[Install]
WantedBy=multi-user.target
```

**Enable and Start Service**:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable algo-engine

# Start service
sudo systemctl start algo-engine

# Check status
sudo systemctl status algo-engine

# View logs
sudo journalctl -u algo-engine -f
```

### Option 3: Run with Screen (Alternative)

```bash
# Install screen
sudo apt install -y screen

# Start screen session
screen -S algo-engine

# Run engine
cd /home/algoengine/algo-engine
source venv/bin/activate
python main.py

# Detach: Press Ctrl+A, then D
# Reattach: screen -r algo-engine
```

---

## 7. Monitoring & Maintenance

### Real-Time Monitoring

**System Resources**:
```bash
# CPU and memory usage
htop

# Disk usage
df -h

# Network connections
netstat -an | grep ESTABLISHED

# DuckDB database size
du -sh /home/algoengine/algo-engine/data/
```

**Application Logs**:
```bash
# Live tail logs
tail -f /home/algoengine/algo-engine/data/logs/app.log

# Error logs
tail -f /home/algoengine/algo-engine/data/logs/errors.log

# Trades log
tail -f /home/algoengine/algo-engine/data/logs/trades.log

# Systemd logs
sudo journalctl -u algo-engine -f
```

### Automated Log Rotation

Create logrotate config:

```bash
sudo nano /etc/logrotate.d/algo-engine
```

**Logrotate Config**:
```
/home/algoengine/algo-engine/data/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 algoengine algoengine
    postrotate
        systemctl reload algo-engine > /dev/null 2>&1 || true
    endscript
}
```

### Health Checks

**Create Health Check Script**:

```bash
nano /home/algoengine/health_check.sh
```

```bash
#!/bin/bash

# Check if algo-engine is running
if ! systemctl is-active --quiet algo-engine; then
    echo "ERROR: algo-engine service is not running"
    systemctl restart algo-engine
    exit 1
fi

# Check if process is responding
if ! curl -sf http://localhost:8000/health > /dev/null; then
    echo "WARNING: Health check endpoint not responding"
fi

echo "OK: algo-engine is running"
```

```bash
chmod +x /home/algoengine/health_check.sh

# Add to crontab (check every 5 minutes)
crontab -e
*/5 * * * * /home/algoengine/health_check.sh >> /home/algoengine/health_check.log 2>&1
```

### Daily Maintenance Cron Jobs

```bash
# Edit crontab
crontab -e
```

**Add Jobs**:
```bash
# Clean old DuckDB data (every 5 minutes)
*/5 * * * * cd /home/algoengine/algo-engine && venv/bin/python scripts/cleanup_duckdb.py

# Vacuum DuckDB (daily at 3 AM)
0 3 * * * cd /home/algoengine/algo-engine && venv/bin/python scripts/vacuum_duckdb.py

# Backup trades database (daily at 4 AM)
0 4 * * * cp /home/algoengine/algo-engine/data/trades/*.duckdb /home/algoengine/backups/

# Check disk space (hourly)
0 * * * * df -h | grep "/dev/sda" | awk '{if ($5+0 > 80) print "WARNING: Disk usage is "$5}'
```

---

## 8. Troubleshooting

### Issue 1: Service Won't Start

```bash
# Check service status
sudo systemctl status algo-engine

# Check logs
sudo journalctl -u algo-engine -n 50

# Common fixes:
# 1. Check .env file exists and has correct permissions
ls -la /home/algoengine/algo-engine/.env

# 2. Verify Python path
which python3.12

# 3. Test manual run
cd /home/algoengine/algo-engine
source venv/bin/activate
python main.py
```

### Issue 2: High Memory Usage

```bash
# Check memory
free -h

# If DuckDB is using too much memory:
# 1. Reduce data retention in config/config.yaml
# 2. Reduce number of symbols being scanned
# 3. Run cleanup script manually
python scripts/cleanup_duckdb.py
```

### Issue 3: Exchange Connection Failures

```bash
# Test connectivity
curl https://api.binance.com/api/v3/ping

# Check firewall
sudo ufw status

# Verify API keys
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('BINANCE_API_KEY')[:10])"

# Check rate limits in logs
grep "rate limit" /home/algoengine/algo-engine/data/logs/errors.log
```

### Issue 4: Database Lock Errors

```bash
# Check if multiple instances are running
ps aux | grep python | grep main.py

# Kill duplicate processes
sudo systemctl stop algo-engine
pkill -f "python main.py"
sudo systemctl start algo-engine
```

---

## 9. Security Hardening

### SSH Security

```bash
# Disable root login
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
# Set: PasswordAuthentication no
# Set: PubkeyAuthentication yes

# Restart SSH
sudo systemctl restart sshd
```

### Firewall (UFW)

```bash
# Install UFW
sudo apt install -y ufw

# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (change port if using non-standard)
sudo ufw allow 22/tcp

# Allow API (optional)
sudo ufw allow 8000/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status verbose
```

### Fail2Ban (Protect Against Brute Force)

```bash
# Install fail2ban
sudo apt install -y fail2ban

# Create custom config
sudo nano /etc/fail2ban/jail.local
```

**Fail2Ban Config**:
```ini
[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600
```

```bash
# Restart fail2ban
sudo systemctl restart fail2ban
```

### Automatic Security Updates

```bash
# Install unattended-upgrades
sudo apt install -y unattended-upgrades

# Enable automatic updates
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## 10. Backup Strategy

### Automated Backups

**Create Backup Script**:

```bash
nano /home/algoengine/backup.sh
```

```bash
#!/bin/bash

BACKUP_DIR="/home/algoengine/backups"
DATE=$(date +%Y-%m-%d)

# Create backup directory
mkdir -p $BACKUP_DIR/$DATE

# Backup DuckDB databases
cp -r /home/algoengine/algo-engine/data/*.duckdb $BACKUP_DIR/$DATE/

# Backup config files
cp /home/algoengine/algo-engine/.env $BACKUP_DIR/$DATE/
cp -r /home/algoengine/algo-engine/config $BACKUP_DIR/$DATE/

# Compress backup
tar -czf $BACKUP_DIR/backup-$DATE.tar.gz -C $BACKUP_DIR $DATE

# Remove old backups (keep last 7 days)
find $BACKUP_DIR -name "backup-*.tar.gz" -mtime +7 -delete

# Remove uncompressed backup
rm -rf $BACKUP_DIR/$DATE

echo "Backup completed: backup-$DATE.tar.gz"
```

```bash
chmod +x /home/algoengine/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
0 2 * * * /home/algoengine/backup.sh >> /home/algoengine/backup.log 2>&1
```

### Offsite Backups (Optional)

```bash
# Install rclone for cloud backups
curl https://rclone.org/install.sh | sudo bash

# Configure rclone (e.g., for Backblaze B2)
rclone config

# Add to backup script
rclone copy /home/algoengine/backups/ remote:algo-engine-backups/
```

---

## 11. Performance Optimization

### DuckDB Optimizations

**In `src/market_data/storage/database_manager.py`**:
```python
# Enable WAL mode for better concurrency
conn.execute("PRAGMA journal_mode = WAL")

# Increase cache size (use 25% of available RAM)
conn.execute("PRAGMA cache_size = -2000000")  # 2GB in KB

# Enable memory-mapped I/O
conn.execute("PRAGMA mmap_size = 30000000000")  # 30GB
```

### System-Level Optimizations

```bash
# Increase file descriptor limits
sudo nano /etc/security/limits.conf
# Add:
algoengine soft nofile 65535
algoengine hard nofile 65535

# Optimize network stack for low latency
sudo nano /etc/sysctl.conf
# Add:
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864
net.ipv4.tcp_congestion_control = bbr

# Apply changes
sudo sysctl -p
```

### Python Optimizations

```bash
# Use uvloop for faster async performance
pip install uvloop

# In main.py, add:
import uvloop
uvloop.install()
```

---

## 12. Deployment Checklist

**Pre-Deployment**:
- [ ] Hetzner VPS created (CPX31 recommended)
- [ ] SSH key added
- [ ] Firewall configured
- [ ] Domain name pointed to server IP (optional)

**Initial Setup**:
- [ ] System packages updated
- [ ] Python 3.12 installed
- [ ] User `algoengine` created
- [ ] Virtual environment created
- [ ] Dependencies installed

**Configuration**:
- [ ] `.env` file created with API keys
- [ ] Firebase credentials uploaded
- [ ] Config YAML files configured
- [ ] Data directories created

**Security**:
- [ ] Root login disabled
- [ ] SSH key-only authentication
- [ ] UFW firewall enabled
- [ ] Fail2Ban configured
- [ ] Automatic updates enabled

**Running**:
- [ ] systemd service created
- [ ] Service enabled and started
- [ ] Logs verified (no errors)
- [ ] Health check script created

**Monitoring**:
- [ ] Log rotation configured
- [ ] Cron jobs for cleanup
- [ ] Backup script configured
- [ ] Health checks automated

**Testing**:
- [ ] Test trade executed successfully
- [ ] Email notifications working
- [ ] WebSocket connections stable
- [ ] Database writes working

---

## 13. Quick Commands Reference

```bash
# Service Management
sudo systemctl start algo-engine     # Start service
sudo systemctl stop algo-engine      # Stop service
sudo systemctl restart algo-engine   # Restart service
sudo systemctl status algo-engine    # Check status

# Logs
sudo journalctl -u algo-engine -f    # Follow systemd logs
tail -f data/logs/app.log            # Follow app logs
tail -f data/logs/trades.log         # Follow trade logs

# Database
du -sh data/*.duckdb                 # Check database sizes
python scripts/cleanup_duckdb.py     # Manual cleanup
python scripts/vacuum_duckdb.py      # Vacuum databases

# System Monitoring
htop                                 # CPU/RAM usage
df -h                                # Disk usage
netstat -an | grep ESTABLISHED       # Active connections
```

---

## 14. Support & Resources

**Hetzner Documentation**:
- Cloud Console: https://console.hetzner.cloud/
- API Docs: https://docs.hetzner.cloud/

**Algo Engine**:
- Repository: <your-repo-url>
- Issues: <your-repo-url>/issues
- Email: <your-support-email>

**Emergency Contacts**:
- Hetzner Support: support@hetzner.com
- Exchange Support: See exchange documentation

---

**Deployment completed! Your algo engine is now running 24/7 on Hetzner. 🚀**
