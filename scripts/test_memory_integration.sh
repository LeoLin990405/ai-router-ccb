#!/bin/bash
# 启动 Gateway Server 并测试 Memory 集成

set -e

PROJECT_ROOT="$HOME/.local/share/codex-dual"

echo "======================================================================"
echo "CCB Gateway Server + Memory Middleware 启动和测试"
echo "======================================================================"

echo ""
echo "[Step 1] 检查依赖..."
cd "$PROJECT_ROOT"

if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "✗ FastAPI not installed"
    echo "  Installing dependencies..."
    pip3 install -q fastapi uvicorn
fi

echo "✓ Dependencies OK"

echo ""
echo "[Step 2] 启动 Gateway Server..."
echo "  URL: http://localhost:8765"
echo "  Press Ctrl+C to stop"
echo ""

# 启动 Gateway（后台运行）
python3 -m lib.gateway.gateway_server --port 8765 > /tmp/gateway.log 2>&1 &
GATEWAY_PID=$!

echo "✓ Gateway Server started (PID: $GATEWAY_PID)"
echo "  Log: /tmp/gateway.log"

# 等待 Gateway 启动
echo ""
echo "[Step 3] Waiting for Gateway to start..."
sleep 3

# 检查 Gateway 是否启动
if curl -s http://localhost:8765/health > /dev/null 2>&1; then
    echo "✓ Gateway is healthy"
else
    echo "✗ Gateway failed to start"
    echo "  Check log: /tmp/gateway.log"
    kill $GATEWAY_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "[Step 4] 运行集成测试..."
echo ""

python3 tests/test_memory_integration.py

TEST_RESULT=$?

echo ""
echo "[Step 5] Cleanup..."

# 停止 Gateway
kill $GATEWAY_PID 2>/dev/null || true
sleep 1

if [ $TEST_RESULT -eq 0 ]; then
    echo ""
    echo "======================================================================"
    echo "🎉 所有测试通过！CCB Memory System 已完全集成！"
    echo "======================================================================"
    echo ""
    echo "下一步："
    echo "  1. 启动 Gateway: python3 -m lib.gateway.gateway_server --port 8765"
    echo "  2. 使用 ccb-cli: ccb-cli kimi \"你的问题\""
    echo "  3. 查看记忆: python3 lib/memory/memory_lite.py recent 10"
    echo ""
else
    echo ""
    echo "✗ 测试失败，请检查日志"
    exit 1
fi
