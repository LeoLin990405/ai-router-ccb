# 📸 CCB Gateway v0.15 截图需求

## 需要添加的新截图

为了完整展示 v0.15 的新功能，需要添加以下截图到 `screenshots/` 目录：

### 1. 成本仪表板截图 (costs.png)
**文件名:** `screenshots/costs.png`

**截图内容:**
- 打开 Web UI: http://localhost:8765
- 按快捷键 `5` 进入 Costs 标签页
- 确保显示:
  - ✅ 今日/本周/本月成本卡片
  - ✅ 7 天成本趋势图
  - ✅ Provider 成本分解表
  - ✅ 数据已填充（不是全空）

**截图步骤:**
```bash
# 1. 确保有一些请求历史生成成本数据
ccb-cli kimi "Hello"
ccb-cli qwen "Test"
ccb-cli deepseek "Example"

# 2. 打开浏览器并截图
open http://localhost:8765
# 按 5 进入 Costs 标签页
# 使用 Cmd+Shift+4 截图
```

---

### 2. 数据导出截图 (export.png)
**文件名:** `screenshots/export.png`

**截图内容:**
- 打开 Requests 标签页（快捷键 `4`）
- 点击 "Export" 下拉按钮
- 展开显示 CSV 和 JSON 选项
- 最好显示一些请求历史记录

**截图步骤:**
```bash
# 1. 打开 Requests 标签页
open http://localhost:8765
# 按 4 进入 Requests

# 2. 点击 Export 按钮
# 展开下拉菜单

# 3. 截图
# 使用 Cmd+Shift+4 截图
```

---

### 3. 综合新功能截图 (webui-v015-features.png)
**文件名:** `screenshots/webui-v015-features.png`

**截图内容:**
- 一个拼图，展示 3 个新功能:
  1. Costs 标签页
  2. Discussion Templates 模态框
  3. Export 下拉菜单

**可选择的方式:**
- **方式 1:** 使用图片编辑工具拼接 3 张小图
- **方式 2:** 制作一个综合演示截图
- **方式 3:** 使用现有的 `webui-demo.gif` 作为占位符

---

## 快速截图脚本

创建一个自动化截图脚本:

```bash
#!/bin/bash
# capture-screenshots.sh

echo "📸 准备截图..."

# 1. 确保 Gateway 运行
if ! curl -s http://localhost:8765/api/status > /dev/null; then
    echo "⚠️  Gateway 未运行，请先启动"
    exit 1
fi

# 2. 生成一些测试数据
echo "生成测试数据..."
ccb-cli kimi "Hello" >/dev/null 2>&1 &
ccb-cli qwen "Test" >/dev/null 2>&1 &
ccb-cli deepseek "Example" >/dev/null 2>&1 &

sleep 3

# 3. 打开浏览器
echo "打开浏览器..."
open http://localhost:8765

echo ""
echo "📸 手动截图步骤:"
echo ""
echo "1️⃣  Costs 标签页截图:"
echo "   - 按 5 进入 Costs"
echo "   - Cmd+Shift+4 截图"
echo "   - 保存为: screenshots/costs.png"
echo ""
echo "2️⃣  Export 功能截图:"
echo "   - 按 4 进入 Requests"
echo "   - 点击 Export 按钮"
echo "   - Cmd+Shift+4 截图"
echo "   - 保存为: screenshots/export.png"
echo ""
echo "3️⃣  Discussion Template 截图:"
echo "   - 按 3 进入 Discussions"
echo "   - 点击 'Use Template' 按钮"
echo "   - Cmd+Shift+4 截图"
echo "   - 保存为: screenshots/templates.png"
echo ""
```

---

## 截图规范

**分辨率:** 推荐 1400x900 像素（2倍缩放到 700 宽度）

**文件格式:** PNG（支持透明背景）

**文件大小:** < 500KB（优化压缩）

**主题:** 深色模式（与现有截图风格一致）

**浏览器:** Chrome 或 Safari（去掉书签栏）

---

## 完成后

1. 将截图文件移动到 `screenshots/` 目录
2. 检查文件名和尺寸
3. 使用以下命令优化图片:

```bash
# 优化 PNG 文件大小
cd ~/.local/share/codex-dual/screenshots
optipng -o7 costs.png export.png webui-v015-features.png
```

4. 提交到 git:

```bash
cd ~/.local/share/codex-dual
git add screenshots/costs.png screenshots/export.png screenshots/webui-v015-features.png
git commit -m "docs: add v0.15 Web UI feature screenshots"
git push
```

---

## 临时方案（如果暂时没有截图）

README 已经更新，但使用了占位符截图路径。如果暂时没有实际截图:

1. **保留占位符** - 截图路径已设置，等待添加实际文件
2. **使用现有截图** - 可以暂时引用 `webui-demo.gif`
3. **添加 TODO 注释** - 在 README 中标注"即将上线"

**当前 README 引用的截图:**
- ✅ `screenshots/dashboard.png` (已存在)
- ✅ `screenshots/discussions.png` (已存在)
- ✅ `screenshots/monitor.png` (已存在)
- ❌ `screenshots/costs.png` (需要添加)
- ❌ `screenshots/export.png` (需要添加)
- ❌ `screenshots/webui-v015-features.png` (需要添加)

---

**状态:** README 已更新，等待添加 3 个新截图文件
**优先级:** 中等（不影响功能使用，仅影响文档展示）
