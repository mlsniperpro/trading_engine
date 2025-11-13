# Logging Guide - Hetzner Deployment

## 🔍 Quick Log Commands

### View Live Logs (Real-time)
```bash
# SSH into server
ssh root@116.203.216.207

# Follow logs in real-time (all logs)
docker logs -f trading-engine

# Follow only last 100 lines
docker logs -f --tail 100 trading-engine

# Follow with timestamps
docker logs -f --timestamps trading-engine
```

### View Historical Logs
```bash
# View last 50 lines
docker logs --tail 50 trading-engine

# View logs from last hour
docker logs --since 1h trading-engine

# View logs from specific time
docker logs --since "2024-01-15T10:00:00" trading-engine

# View logs until specific time
docker logs --until "2024-01-15T12:00:00" trading-engine
```

### Filter Logs by Level
```bash
# Only errors
docker logs trading-engine 2>&1 | grep ERROR

# Only warnings
docker logs trading-engine 2>&1 | grep WARNING

# Only arbitrage alerts
docker logs -f trading-engine 2>&1 | grep "🚨 ARBITRAGE"

# Only swap events
docker logs -f trading-engine 2>&1 | grep "🔄 Swap"
```

## 📊 Advanced Log Monitoring

### Monitor Specific Events

**DEX Swaps:**
```bash
docker logs -f trading-engine 2>&1 | grep "🔄 Swap"
```

**Arbitrage Opportunities:**
```bash
docker logs -f trading-engine 2>&1 | grep -E "(🚨 ARBITRAGE|OPPORTUNITY)"
```

**Errors Only:**
```bash
docker logs -f trading-engine 2>&1 | grep -E "(ERROR|CRITICAL)"
```

**Price Updates:**
```bash
docker logs -f trading-engine 2>&1 | grep -E "Price: \$"
```

### Search Logs
```bash
# Search for specific text
docker logs trading-engine 2>&1 | grep "ETH-USDC"

# Count occurrences
docker logs trading-engine 2>&1 | grep -c "ARBITRAGE"

# Case-insensitive search
docker logs trading-engine 2>&1 | grep -i "error"

# Show context (5 lines before and after)
docker logs trading-engine 2>&1 | grep -A 5 -B 5 "ERROR"
```

## 📁 Log File Locations

Docker logs are stored at:
```
/var/lib/docker/containers/<container-id>/<container-id>-json.log
```

Current configuration (from docker-compose.yml):
- **Max size per file**: 10MB
- **Number of files**: 3 (rotates automatically)
- **Total max size**: ~30MB

## 🛠️ Helper Scripts

### Create Log Monitor Script

Create `/root/monitor-logs.sh` on server:

```bash
#!/bin/bash
# Log monitoring script for Trading Engine

case "$1" in
  live)
    echo "📊 Monitoring live logs (Ctrl+C to stop)..."
    docker logs -f --tail 50 trading-engine
    ;;
  errors)
    echo "❌ Showing errors..."
    docker logs --tail 200 trading-engine 2>&1 | grep -E "(ERROR|CRITICAL)"
    ;;
  arbitrage)
    echo "🚨 Monitoring arbitrage opportunities..."
    docker logs -f trading-engine 2>&1 | grep -E "(🚨|ARBITRAGE)"
    ;;
  swaps)
    echo "🔄 Monitoring DEX swaps..."
    docker logs -f trading-engine 2>&1 | grep "🔄 Swap"
    ;;
  health)
    echo "💚 System health..."
    docker logs --tail 100 trading-engine 2>&1 | grep -E "(ERROR|WARNING|Connected|Started)"
    ;;
  stats)
    echo "📈 Log statistics..."
    echo "Total log entries: $(docker logs trading-engine 2>&1 | wc -l)"
    echo "Errors: $(docker logs trading-engine 2>&1 | grep -c ERROR)"
    echo "Warnings: $(docker logs trading-engine 2>&1 | grep -c WARNING)"
    echo "Swaps: $(docker logs trading-engine 2>&1 | grep -c 'Swap #')"
    echo "Arbitrage alerts: $(docker logs trading-engine 2>&1 | grep -c ARBITRAGE)"
    ;;
  *)
    echo "Trading Engine Log Monitor"
    echo ""
    echo "Usage: $0 {live|errors|arbitrage|swaps|health|stats}"
    echo ""
    echo "  live       - Follow logs in real-time"
    echo "  errors     - Show recent errors"
    echo "  arbitrage  - Monitor arbitrage opportunities"
    echo "  swaps      - Monitor DEX swaps"
    echo "  health     - Check system health"
    echo "  stats      - Show log statistics"
    ;;
esac
```

Make it executable:
```bash
chmod +x /root/monitor-logs.sh
```

Usage:
```bash
./monitor-logs.sh live        # Live monitoring
./monitor-logs.sh errors      # Show errors
./monitor-logs.sh arbitrage   # Watch arbitrage
./monitor-logs.sh stats       # Statistics
```

## 🔔 Real-time Monitoring Tools

### Option 1: Simple Tail (Recommended for Quick Checks)
```bash
# Basic real-time monitoring
docker logs -f --tail 100 trading-engine

# With grep for filtering
docker logs -f trading-engine 2>&1 | grep --line-buffered -E "(ERROR|ARBITRAGE|Started)"
```

### Option 2: Using `less` for Navigation
```bash
# View logs with search and navigation
docker logs trading-engine 2>&1 | less

# Inside less:
# - Press / to search
# - Press n for next match
# - Press q to quit
```

### Option 3: Export Logs for Analysis
```bash
# Export last 1000 lines to file
docker logs --tail 1000 trading-engine > logs_export.txt

# Export with timestamp
docker logs --timestamps trading-engine > logs_$(date +%Y%m%d_%H%M%S).txt

# Download to local machine
scp root@116.203.216.207:~/logs_export.txt .
```

## 📧 Set Up Log Alerts (Optional)

### Email Alerts for Errors

Create `/root/alert-on-errors.sh`:

```bash
#!/bin/bash
# Alert on critical errors

docker logs --since 5m trading-engine 2>&1 | grep -E "(CRITICAL|FATAL)" && \
  echo "Critical error detected in Trading Engine" | \
  mail -s "Trading Engine Alert" your-email@example.com
```

Add to crontab (check every 5 minutes):
```bash
crontab -e
# Add:
*/5 * * * * /root/alert-on-errors.sh
```

## 🎯 Best Practices

### During Development
```bash
# Watch everything
docker logs -f trading-engine
```

### During Production
```bash
# Watch for important events only
docker logs -f trading-engine 2>&1 | grep -E "(ERROR|ARBITRAGE|WARNING|Started|Stopped)"
```

### For Debugging
```bash
# Full logs with timestamps
docker logs --timestamps trading-engine > debug.log

# Then analyze locally
grep ERROR debug.log
grep -B 10 -A 10 "specific error" debug.log
```

### For Performance Analysis
```bash
# Export last hour of logs
docker logs --since 1h trading-engine > performance_$(date +%H%M).log

# Analyze swap frequency
grep "Swap #" performance_*.log | wc -l

# Analyze arbitrage opportunities
grep "ARBITRAGE" performance_*.log | wc -l
```

## 🚨 Common Issues to Watch For

### Connection Issues
```bash
docker logs trading-engine 2>&1 | grep -i "connection\|timeout\|refused"
```

### Memory Issues
```bash
docker stats trading-engine
# Watch for high memory usage
```

### API Rate Limits
```bash
docker logs trading-engine 2>&1 | grep -i "rate limit\|429\|quota"
```

### WebSocket Issues
```bash
docker logs trading-engine 2>&1 | grep -i "websocket\|disconnect"
```

## 📱 Remote Monitoring from Your Machine

### Watch Logs Remotely (without SSH login)
```bash
# Stream logs directly
ssh root@116.203.216.207 "docker logs -f trading-engine"

# With filtering
ssh root@116.203.216.207 "docker logs -f trading-engine" 2>&1 | grep ARBITRAGE
```

### Create Local Monitoring Script

Save as `monitor-remote.sh`:

```bash
#!/bin/bash
# Monitor Hetzner server logs from local machine

SERVER="root@116.203.216.207"
CONTAINER="trading-engine"

case "$1" in
  live)
    ssh $SERVER "docker logs -f --tail 50 $CONTAINER"
    ;;
  errors)
    ssh $SERVER "docker logs --tail 200 $CONTAINER" 2>&1 | grep ERROR
    ;;
  stats)
    ssh $SERVER "docker logs $CONTAINER" 2>&1 | \
      awk 'END {
        print "Total lines:", NR
      }' && \
    ssh $SERVER "docker logs $CONTAINER" 2>&1 | grep -c ERROR | \
      awk '{print "Errors:", $1}'
    ;;
  *)
    echo "Usage: $0 {live|errors|stats}"
    ;;
esac
```

## 🔍 Troubleshooting

### Logs Not Showing Up?
```bash
# Check container is running
docker ps | grep trading-engine

# Check container status
docker inspect trading-engine | grep -A 10 State

# Restart container to regenerate logs
docker restart trading-engine
```

### Too Many Logs?
```bash
# Reduce log level in .env
LOG_LEVEL=WARNING

# Then restart
docker-compose restart
```

### Want More Detailed Logs?
```bash
# Increase log level in .env
LOG_LEVEL=DEBUG

# Then restart
docker-compose restart
```

## 📈 Log Retention

Current setup (in docker-compose.yml):
- Keeps **3 files** x **10MB each** = 30MB total
- Automatically rotates when files get too large
- No manual cleanup needed

To change retention:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "50m"    # Increase to 50MB per file
    max-file: "5"      # Keep 5 files (250MB total)
```

---

**Quick Reference Card:**

```bash
# Most common commands
docker logs -f trading-engine              # Follow logs
docker logs --tail 100 trading-engine      # Last 100 lines
docker logs trading-engine | grep ERROR    # Find errors
ssh root@116.203.216.207 "docker logs -f trading-engine"  # Remote monitoring
```
