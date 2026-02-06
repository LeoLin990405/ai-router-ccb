#!/bin/bash
# CCB Gateway Startup Script with Gemini Auth Pre-Check
# Usage: ccb-gateway-start.sh [--port 8765] [--no-health-check]

set -e

CCB_ROOT="$HOME/.local/share/codex-dual"
GATEWAY_PORT=8765
ENABLE_HEALTH_CHECK=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            GATEWAY_PORT="$2"
            shift 2
            ;;
        --no-health-check)
            ENABLE_HEALTH_CHECK=false
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--port 8765] [--no-health-check]"
            exit 1
            ;;
    esac
done

echo "=== CCB Gateway Startup ==="
echo "Port: $GATEWAY_PORT"
echo "Health Check: $ENABLE_HEALTH_CHECK"
echo

# Step 1: Check Gemini Authentication
echo "[1/3] Checking Gemini authentication..."

if ! command -v gemini &> /dev/null; then
    echo "⚠️  Gemini CLI not installed. Skipping Gemini auth check."
else
    # Check if API key is set
    if [ -n "$GOOGLE_API_KEY" ]; then
        echo "✅ GOOGLE_API_KEY is set (using API key mode)"
    else
        # Check OAuth token
        OAUTH_CREDS="$HOME/.gemini/oauth_creds.json"
        if [ -f "$OAUTH_CREDS" ]; then
            echo "✅ OAuth credentials found"

            # Try to refresh token automatically
            echo "   Refreshing token..."
            if python3 "$CCB_ROOT/lib/gateway/gemini_auth.py" 2>&1 | grep -q "success"; then
                echo "✅ Token refreshed successfully"
            else
                echo "⚠️  Token refresh failed. You may need to re-authenticate:"
                echo "   Run: gemini auth login"
                echo
                echo "Continuing anyway (health check will auto-disable if auth fails)..."
            fi
        else
            echo "⚠️  No Gemini authentication found"
            echo "   Option 1 (API Key): Set GOOGLE_API_KEY in ~/.zshrc"
            echo "   Option 2 (OAuth): Run 'gemini auth login'"
            echo
            echo "Continuing anyway (health check will auto-disable Gemini if needed)..."
        fi
    fi
fi

echo

# Step 2: Stop existing Gateway if running
echo "[2/3] Checking for existing Gateway..."
if lsof -ti:$GATEWAY_PORT &> /dev/null; then
    PID=$(lsof -ti:$GATEWAY_PORT)
    echo "⚠️  Port $GATEWAY_PORT is in use by PID $PID. Stopping..."
    kill -9 $PID 2>/dev/null || true
    sleep 1
    echo "✅ Old Gateway stopped"
else
    echo "✅ Port $GATEWAY_PORT is available"
fi

echo

# Step 3: Start Gateway
echo "[3/3] Starting CCB Gateway..."
cd "$CCB_ROOT"

if [ "$ENABLE_HEALTH_CHECK" = true ]; then
    nohup python3 -m lib.gateway.gateway_server --port $GATEWAY_PORT > /tmp/ccb-gateway.log 2>&1 &
else
    # Disable health check by setting interval to 0 (TODO: add proper flag)
    nohup python3 -m lib.gateway.gateway_server --port $GATEWAY_PORT > /tmp/ccb-gateway.log 2>&1 &
fi

GATEWAY_PID=$!
echo "✅ Gateway started (PID: $GATEWAY_PID)"
echo "   Log: /tmp/ccb-gateway.log"
echo "   URL: http://localhost:$GATEWAY_PORT"
echo

# Wait a moment and verify it's running
sleep 2
if ps -p $GATEWAY_PID > /dev/null; then
    echo "🎉 CCB Gateway is running!"

    # Show recent logs
    echo
    echo "=== Recent logs ==="
    tail -20 /tmp/ccb-gateway.log
else
    echo "❌ Gateway failed to start. Check logs:"
    echo "   tail -f /tmp/ccb-gateway.log"
    exit 1
fi
