#!/bin/bash
# HiveMind Electron 应用测试脚本

echo "=========================================="
echo "  HiveMind Electron 应用完整测试"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数器
PASSED=0
FAILED=0
TOTAL=0

# 测试函数
test_item() {
    TOTAL=$((TOTAL + 1))
    echo -n "[$TOTAL] $1 ... "
}

pass() {
    PASSED=$((PASSED + 1))
    echo -e "${GREEN}✓ PASS${NC}"
}

fail() {
    FAILED=$((FAILED + 1))
    echo -e "${RED}✗ FAIL${NC}"
    if [ ! -z "$1" ]; then
        echo "    ↳ $1"
    fi
}

skip() {
    echo -e "${YELLOW}⊘ SKIP${NC}"
    if [ ! -z "$1" ]; then
        echo "    ↳ $1"
    fi
}

echo "阶段 1: 环境检查"
echo "------------------------------------------"

# 1. Node.js 版本检查
test_item "Node.js 版本检查"
NODE_VERSION=$(node -v 2>/dev/null)
if [ $? -eq 0 ]; then
    pass
    echo "    ↳ $NODE_VERSION"
else
    fail "Node.js 未安装"
fi

# 2. npm 版本检查
test_item "npm 版本检查"
NPM_VERSION=$(npm -v 2>/dev/null)
if [ $? -eq 0 ]; then
    pass
    echo "    ↳ v$NPM_VERSION"
else
    fail "npm 未安装"
fi

# 3. node_modules 检查
test_item "依赖安装检查"
if [ -d "node_modules" ]; then
    pass
    SIZE=$(du -sh node_modules 2>/dev/null | cut -f1)
    echo "    ↳ node_modules: $SIZE"
else
    fail "node_modules 不存在，运行 npm install"
fi

# 4. 配置文件检查
test_item "Webpack 配置文件检查"
CONFIG_FILES=(
    "config/webpack/webpack.config.ts"
    "config/webpack/webpack.renderer.config.ts"
    "config/webpack/webpack.plugins.ts"
    "config/webpack/webpack.rules.ts"
)
ALL_EXISTS=true
for file in "${CONFIG_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        ALL_EXISTS=false
        break
    fi
done
if [ "$ALL_EXISTS" = true ]; then
    pass
else
    fail "部分配置文件缺失"
fi

echo ""
echo "阶段 2: 数据库检查"
echo "------------------------------------------"

# 5. 数据库文件检查
test_item "SQLite 数据库文件"
DB_PATH="$HOME/Library/Application Support/HiveMind/hivemind/hivemind.db"
if [ -f "$DB_PATH" ]; then
    pass
    SIZE=$(ls -lh "$DB_PATH" | awk '{print $5}')
    echo "    ↳ 大小: $SIZE"
else
    skip "数据库将在首次启动时创建"
fi

echo ""
echo "阶段 3: 编译测试"
echo "------------------------------------------"

# 6. 配置验证
test_item "Electron Forge 配置验证"
if npx electron-forge package --dry-run > /dev/null 2>&1; then
    pass
else
    fail "配置验证失败"
fi

echo ""
echo "阶段 4: 应用启动测试"
echo "------------------------------------------"

# 7. 应用启动（需要手动测试）
test_item "Electron 应用启动"
echo ""
echo "    ${YELLOW}⚠ 此步骤需要手动验证${NC}"
echo ""
echo "    请在另一个终端运行: npm start"
echo ""
echo "    验证项："
echo "    - [ ] 应用窗口成功打开"
echo "    - [ ] 无 JavaScript 错误（查看 DevTools Console）"
echo "    - [ ] 主界面正常显示"
echo "    - [ ] 可以创建新对话"
echo "    - [ ] 可以发送消息"
echo ""
read -p "    应用是否成功启动？(y/n): " answer
if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
    pass
    echo "    ↳ 应用启动成功"
else
    fail "应用启动失败或功能异常"
fi

echo ""
echo "=========================================="
echo "  测试结果汇总"
echo "=========================================="
echo ""
echo "总计: $TOTAL 项测试"
echo -e "${GREEN}通过: $PASSED${NC}"
echo -e "${RED}失败: $FAILED${NC}"
echo ""

# 计算通过率
if [ $TOTAL -gt 0 ]; then
    PASS_RATE=$((PASSED * 100 / TOTAL))
    echo "通过率: $PASS_RATE%"
    echo ""

    if [ $PASS_RATE -eq 100 ]; then
        echo -e "${GREEN}✓ 所有测试通过！${NC}"
        exit 0
    elif [ $PASS_RATE -ge 80 ]; then
        echo -e "${YELLOW}⚠ 大部分测试通过，但有些问题需要修复${NC}"
        exit 1
    else
        echo -e "${RED}✗ 测试失败过多，需要修复关键问题${NC}"
        exit 2
    fi
else
    echo -e "${RED}✗ 没有执行任何测试${NC}"
    exit 3
fi
