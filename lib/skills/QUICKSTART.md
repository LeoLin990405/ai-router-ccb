# CCB-FindSkills 快速使用指南

## 1. 初始化

### 首次启动 Gateway Server

```bash
cd ~/.local/share/codex-dual

# 启动 Gateway（会自动初始化 Skills Discovery）
python3 -m lib.gateway.gateway_server --port 8765
```

**输出:**
```
[SystemContext] Preloading system information...
[SystemContext] Loaded 53 skills
[SystemContext] Loaded 8 providers
[SystemContext] Loaded 4 MCP servers
[MemoryMiddleware] Initialized (enabled=True)
[SkillsDiscovery] Database initialized
[MemoryMiddleware] Skills discovery: True
[GatewayServer] Memory Middleware initialized successfully
✓ Server running at http://localhost:8765
```

### 刷新 Skills 缓存

```bash
# 扫描所有本地 skills
ccb-skills scan
```

---

## 2. 基本使用

### 场景 1: 自动发现技能

**用户请求:**
```bash
ccb-cli kimi "帮我创建一个 Excel 报表"
```

**Gateway 自动处理:**
1. 提取关键词: `["create", "Excel", "report"]`
2. 查找相关技能: 发现 `xlsx` skill (score: 20)
3. 注入到上下文:
   ```
   ## 🛠️ 相关技能推荐
   - **/xlsx** - Comprehensive spreadsheet creation and editing
     ✓ 已安装，可直接使用: `/xlsx`
   ```
4. AI 看到推荐，使用 `/xlsx` skill
5. 记录使用到数据库

**用户无需任何额外操作！**

---

### 场景 2: 手动查找技能

```bash
# 查找与任务相关的技能
ccb-skills recommend "build a React component"

# 输出:
💡 Analyzing task: build a React component

✓ 发现 2 个相关 Skill: frontend-design, webapp-testing

1. frontend-design (Relevance: 22)
   Create distinctive, production-grade frontend interfaces
   ✓ Installed - Use: /frontend-design

2. webapp-testing (Relevance: 10)
   Toolkit for testing local web applications
   ✓ Installed - Use: /webapp-testing
```

---

### 场景 3: 查看学习统计

```bash
ccb-skills stats

# 输出:
📊 Skills Statistics

  Total skills in cache: 53
  Installed skills: 45
  Total usage records: 127

  Top 10 most used skills:
    - pdf: 23 uses
    - xlsx: 18 uses
    - pptx: 15 uses
    - frontend-design: 12 uses
```

---

## 3. 高级功能

### 查看所有技能

```bash
# 列出所有技能
ccb-skills list

# 只列出已安装的技能
ccb-skills list --installed
```

### 匹配特定任务

```bash
ccb-skills match "create a PDF with charts"

# 输出:
🔍 Finding skills for: create a PDF with charts

✓ 发现 2 个相关 Skill: /pdf, /canvas-design

  pdf (✓ Installed)
    Score: 18
    Comprehensive PDF manipulation toolkit
    Usage: /pdf

  canvas-design (✓ Installed)
    Score: 8
    Create beautiful visual art in documents
    Usage: /canvas-design
```

---

## 4. 配置

### 启用/禁用自动发现

编辑 `~/.ccb/gateway_config.json`:

```json
{
  "skills": {
    "auto_discover": true,           // 自动发现技能
    "recommend_skills": true,        // 推荐技能给用户
    "max_recommendations": 3,        // 最多推荐 3 个
    "cache_ttl_hours": 24            // 缓存 24 小时
  }
}
```

### 重启 Gateway 生效

```bash
# 停止 Gateway (Ctrl+C)
# 重新启动
python3 -m lib.gateway.gateway_server --port 8765
```

---

## 5. 工作流示例

### 完整工作流: PDF 报告生成

```bash
# Step 1: 用户发起请求
ccb-cli kimi "帮我创建一个 PDF 季度报告"

# [Gateway 内部处理]
# - 提取关键词: ["create", "PDF", "report"]
# - 发现技能: pdf (score: 23)
# - 注入推荐到上下文
# - 发送到 Kimi

# Step 2: Kimi 响应
"我可以使用 /pdf skill 来帮你创建 PDF 报告...
建议使用以下结构:
1. 标题页
2. 目录
3. 数据分析
..."

# [Gateway 后处理]
# - 记录对话到 conversations 表
# - 检测到使用了 /pdf skill
# - 记录到 skills_usage 表:
#   INSERT INTO skills_usage VALUES (
#     'pdf', 'create PDF report', 'kimi', '2026-02-04T13:30:00', 1
#   )

# Step 3: 下次相似任务，推荐更准确
ccb-cli kimi "生成 PDF 月报"

# [Gateway]
# - 发现技能: pdf (score: 28) ← +5 from history
# - 推荐更有信心
```

---

## 6. 监控和调试

### 查看实时日志

```bash
# Gateway Server 终端会输出详细日志
[MemoryMiddleware] Pre-request: provider=kimi, message_len=20
[MemoryMiddleware] Extracted keywords: ['create', 'PDF']
[SkillsDiscovery] Searching for skills...
[SkillsDiscovery] Found 1 matching skill: pdf (score: 18)
[MemoryMiddleware] 💡 发现 1 个相关 Skill: /pdf
[MemoryMiddleware] Skills recommendations injected
[MemoryMiddleware] Conversation recorded: provider=kimi
[MemoryMiddleware] Recorded skill usage: ['pdf']
```

### 查看数据库

```bash
# 使用 SQLite 查看
sqlite3 ~/.ccb/ccb_memory.db

# 查询技能缓存
SELECT * FROM skills_cache LIMIT 5;

# 查询使用记录
SELECT skill_name, COUNT(*) as uses
FROM skills_usage
GROUP BY skill_name
ORDER BY uses DESC
LIMIT 10;
```

---

## 7. 常见问题

### Q1: Skills 推荐不准确？

**解决方案:**
```bash
# 1. 刷新缓存
ccb-skills scan

# 2. 查看缓存内容
ccb-skills list

# 3. 如果 skill 不在缓存中，检查 scan-skills.sh
ls ~/.claude/skills/
```

### Q2: 推荐分数太低？

**原因:** 新 skill 或很少使用的 skill 初始分数较低。

**解决方案:** 多使用几次，系统会学习并提高分数。

```bash
# 第 1 次使用: score = 10
# 第 2 次使用: score = 15 (+5 history)
# 第 3 次使用: score = 20 (+10 history)
```

### Q3: 如何添加自定义 Skills？

```bash
# 1. 在 ~/.claude/skills/ 创建新目录
mkdir ~/.claude/skills/my-custom-skill

# 2. 创建 SKILL.md（包含 frontmatter）
cat > ~/.claude/skills/my-custom-skill/SKILL.md << EOF
---
name: my-custom-skill
description: My custom skill description
triggers:
  - custom
  - special
---
# Full skill instructions...
EOF

# 3. 刷新缓存
ccb-skills scan

# 4. 验证
ccb-skills list | grep my-custom-skill
```

---

## 8. 性能优化

### 缓存策略

- **skills_cache** - 24 小时过期
- **skills_usage** - 永久保存
- 使用索引加速关键词搜索

### 推荐算法

```python
# 相关性得分计算
score = 0

# 名称匹配 (最重要)
if keyword in skill_name:
    score += 10

# 描述匹配
if keyword in description:
    score += 5

# 触发器匹配
if keyword in triggers:
    score += 3

# 已安装 bonus
if installed:
    score += 2

# 历史使用 boost (cap at +5 per keyword)
history_count = count_usage(skill, keyword)
score += min(history_count, 5)
```

---

## 9. 集成到工作流

### 在 Claude Code CLI 中使用

```bash
# Claude 会自动使用推荐的技能
# 无需额外配置

# 示例对话:
You: "帮我创建一个 PPT 演示文稿"

Claude: "我发现有 /pptx skill 可以帮助你...
[使用 /pptx 生成代码]"
```

### 在 Web UI 中使用

访问 http://localhost:8765/web

- 查看实时推荐
- 监控技能使用统计
- 查看推荐准确率

---

## 10. 下一步

### 学习更多

- [完整架构文档](INTEGRATION_ARCHITECTURE.md)
- [Skills Discovery API](skills_discovery.py)
- [Memory Middleware 源码](../gateway/middleware/memory_middleware.py)

### 贡献

如果你有新的 skill 推荐算法或改进建议:

1. Fork 仓库
2. 创建分支: `git checkout -b feature/better-matching`
3. 提交 PR

---

## 总结

CCB-FindSkills 集成让 CCB Gateway 能够:

✅ **自动发现** - 根据任务自动找到相关技能
✅ **智能推荐** - 基于历史使用优化推荐
✅ **持续学习** - 使用越多，推荐越准确
✅ **零配置** - 用户无需手动管理

**开始使用:**
```bash
# 1. 启动 Gateway
python3 -m lib.gateway.gateway_server --port 8765

# 2. 发起请求
ccb-cli kimi "你的任务"

# 3. 查看统计
ccb-skills stats
```

**就这么简单！** 🚀
