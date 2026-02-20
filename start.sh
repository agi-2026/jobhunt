#!/bin/bash
# JobHunt Agent - Startup Script
# Usage: ./start.sh
#
# Prerequisites:
#   - OpenClaw installed (see README.md)
#   - Tailscale installed (for Gmail push notifications)
#   - Node.js 20+ and pnpm

set -e

OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/openclaw}"
TAILSCALE_SOCK="$HOME/.tailscale/tailscaled.sock"
DASHBOARD_PORT=8765

echo "=== Starting JobHunt Agent ==="

# 1. Start tailscaled (userspace networking) — needed for Gmail push
if command -v tailscale &>/dev/null; then
  if ! tailscale --socket="$TAILSCALE_SOCK" status &>/dev/null 2>&1; then
    echo "[1/4] Starting Tailscale daemon..."
    tailscaled \
      --state="$HOME/.tailscale/tailscaled.state" \
      --socket="$TAILSCALE_SOCK" \
      --tun=userspace-networking \
      --port=0 &>/dev/null &
    sleep 4
    tailscale --socket="$TAILSCALE_SOCK" up
    echo "  Tailscale connected."
  else
    echo "[1/4] Tailscale already running."
  fi

  # Enable Funnel for Gmail push endpoint
  echo "[2/4] Enabling Tailscale Funnel on port 8788..."
  tailscale --socket="$TAILSCALE_SOCK" funnel --bg --yes 8788 &>/dev/null 2>&1 || true
else
  echo "[1/4] Tailscale not installed (optional — needed for Gmail push notifications)"
  echo "[2/4] Skipping Tailscale Funnel"
fi

# 3. Start OpenClaw gateway
if curl -s -o /dev/null -w "" http://127.0.0.1:18789/ 2>/dev/null; then
  echo "[3/4] OpenClaw gateway already running."
else
  echo "[3/4] Starting OpenClaw gateway..."
  cd "$OPENCLAW_DIR"
  nohup pnpm openclaw gateway --verbose > /tmp/openclaw-gateway.log 2>&1 &
  sleep 8
  if curl -s -o /dev/null http://127.0.0.1:18789/ 2>/dev/null; then
    echo "  Gateway started successfully."
  else
    echo "  WARNING: Gateway may still be starting. Check: tail -f /tmp/openclaw-gateway.log"
  fi
fi

# 4. Start dashboard
echo "[4/4] Starting dashboard on port $DASHBOARD_PORT..."
lsof -ti:$DASHBOARD_PORT | xargs kill 2>/dev/null || true
sleep 1
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
nohup python3 "$SCRIPT_DIR/dashboard/server.py" > /tmp/jobhunt-dashboard.log 2>&1 &
sleep 2

echo ""
echo "=== JobHunt Agent is LIVE ==="
echo "  Gateway:    http://127.0.0.1:18789/"
echo "  Dashboard:  http://127.0.0.1:$DASHBOARD_PORT/"
echo "  Logs:       tail -f /tmp/openclaw-gateway.log"
echo ""
echo "Scheduled agents:"
echo "  Search Agent:      Every 2 hours  (finds jobs via API + browser)"
echo "  Application Agent: Every 2 min    (applies to top-scored jobs)"
echo "  Email Monitor:     Every 2 hours  (detects recruiter responses)"
echo "  Evening Summary:   Daily 9 PM     (pipeline + health report)"
echo "  Analysis Agent:    Daily 8:30 PM  (log analysis + improvements)"
echo "  Health Monitor:    Every 30 min   (alerts on errors)"
echo ""
echo "To stop: pkill -f openclaw-gateway && pkill -f 'dashboard/server.py'"
