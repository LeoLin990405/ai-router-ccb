#!/bin/bash

# Hivemind Development Environment Initialization
# Based on Anthropic's effective harness patterns
# This script should be run at the start of each development session

set -e  # Exit on error

echo "🔧 Hivemind Development Environment Initialization"
echo "=================================================="

# 1. Verify working directory
echo ""
echo "📁 Working Directory:"
pwd

# 2. Verify git status
echo ""
echo "📊 Git Status:"
git status --short
git log --oneline -1

# 3. Check if Gateway API is running
echo ""
echo "🌐 Gateway API Status:"
if curl -s http://localhost:8765/health > /dev/null 2>&1; then
    echo "✅ Gateway API is running"
else
    echo "⚠️  Gateway API is not running"
    echo "   Start with: cd ~/.local/share/codex-dual && python3 -m lib.gateway.gateway_server --port 8765"
fi

# 4. Check Node.js and npm
echo ""
echo "🔧 Node.js Environment:"
node --version
npm --version

# 5. Review current progress
echo ""
echo "📝 Latest Progress:"
tail -20 .harness/claude-progress.txt

# 6. Show next priority feature
echo ""
echo "🎯 Next Priority Feature:"
if command -v jq > /dev/null 2>&1; then
    jq -r '.features[] | select(.passes == false) | "ID: \(.id) | \(.name) | Priority: \(.priority)"' .harness/features.json | head -1
else
    echo "   Install jq for better feature parsing: brew install jq"
    grep -A 3 '"passes": false' .harness/features.json | head -10
fi

# 7. Verify AI provider connectivity (optional, can be slow)
if [ "$1" == "--check-providers" ]; then
    echo ""
    echo "🤖 AI Provider Connectivity:"
    ccb-cli kimi "test" > /dev/null 2>&1 && echo "✅ Kimi" || echo "❌ Kimi"
    ccb-cli qwen "test" > /dev/null 2>&1 && echo "✅ Qwen" || echo "❌ Qwen"
    # Add more as needed
fi

echo ""
echo "=================================================="
echo "✅ Initialization complete!"
echo ""
echo "Standard Session Workflow:"
echo "1. Review features.json for next priority"
echo "2. Work on ONE feature per session"
echo "3. Test thoroughly (write E2E tests when possible)"
echo "4. Commit with clean state"
echo "5. Update claude-progress.txt"
echo ""
echo "Remember: Quality over speed. Clean handoffs matter."
echo "=================================================="
