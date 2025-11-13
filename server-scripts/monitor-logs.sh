#!/bin/bash
# Log monitoring script for Trading Engine on Hetzner
# Usage: ./monitor-logs.sh [live|errors|arbitrage|swaps|health|stats]

CONTAINER="trading-engine"

case "$1" in
  live)
    echo "📊 Monitoring live logs (Ctrl+C to stop)..."
    docker logs -f --tail 50 --timestamps $CONTAINER
    ;;
  errors)
    echo "❌ Recent errors:"
    echo "================================"
    docker logs --tail 200 $CONTAINER 2>&1 | grep -E "(ERROR|CRITICAL)" | tail -20
    ;;
  arbitrage)
    echo "🚨 Monitoring arbitrage opportunities..."
    docker logs -f $CONTAINER 2>&1 | grep --line-buffered -E "(🚨|ARBITRAGE)"
    ;;
  swaps)
    echo "🔄 Monitoring DEX swaps..."
    docker logs -f $CONTAINER 2>&1 | grep --line-buffered "🔄 Swap"
    ;;
  health)
    echo "💚 System Health Check"
    echo "================================"
    echo "Container Status:"
    docker ps --filter name=$CONTAINER --format "table {{.Status}}\t{{.Ports}}"
    echo ""
    echo "Recent Activity (last 50 lines):"
    docker logs --tail 50 $CONTAINER 2>&1 | grep -E "(ERROR|WARNING|Connected|Started|🚨)" | tail -10
    ;;
  stats)
    echo "📈 Log Statistics"
    echo "================================"
    TOTAL=$(docker logs $CONTAINER 2>&1 | wc -l)
    ERRORS=$(docker logs $CONTAINER 2>&1 | grep -c "ERROR")
    WARNINGS=$(docker logs $CONTAINER 2>&1 | grep -c "WARNING")
    SWAPS=$(docker logs $CONTAINER 2>&1 | grep -c "Swap #")
    ARBITRAGE=$(docker logs $CONTAINER 2>&1 | grep -c "ARBITRAGE")

    echo "Total log entries: $TOTAL"
    echo "Errors: $ERRORS"
    echo "Warnings: $WARNINGS"
    echo "DEX Swaps: $SWAPS"
    echo "Arbitrage alerts: $ARBITRAGE"
    echo ""
    echo "Last 5 errors:"
    docker logs --tail 500 $CONTAINER 2>&1 | grep "ERROR" | tail -5
    ;;
  export)
    FILENAME="logs_$(date +%Y%m%d_%H%M%S).txt"
    echo "📦 Exporting logs to $FILENAME..."
    docker logs --timestamps $CONTAINER > $FILENAME
    echo "✓ Exported $(wc -l < $FILENAME) lines to $FILENAME"
    echo "Download with: scp root@$(hostname -I | awk '{print $1}'):~/$FILENAME ."
    ;;
  tail)
    LINES=${2:-100}
    echo "📄 Last $LINES lines:"
    echo "================================"
    docker logs --tail $LINES --timestamps $CONTAINER
    ;;
  since)
    TIME=${2:-1h}
    echo "🕐 Logs since $TIME ago:"
    echo "================================"
    docker logs --since $TIME --timestamps $CONTAINER
    ;;
  *)
    echo "🔍 Trading Engine Log Monitor"
    echo "================================"
    echo ""
    echo "Usage: $0 {command} [options]"
    echo ""
    echo "Commands:"
    echo "  live              - Follow logs in real-time"
    echo "  errors            - Show recent errors"
    echo "  arbitrage         - Monitor arbitrage opportunities"
    echo "  swaps             - Monitor DEX swaps"
    echo "  health            - Check system health"
    echo "  stats             - Show log statistics"
    echo "  export            - Export logs to file"
    echo "  tail [N]          - Show last N lines (default: 100)"
    echo "  since [TIME]      - Show logs since TIME (e.g., 1h, 30m, 2d)"
    echo ""
    echo "Examples:"
    echo "  $0 live           # Real-time monitoring"
    echo "  $0 tail 500       # Last 500 lines"
    echo "  $0 since 2h       # Last 2 hours"
    echo ""
    ;;
esac
