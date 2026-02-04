# CCB Skills Discovery Module

**自学习的技能发现和推荐系统**

## 📁 文件结构

```
lib/skills/
├── README.md                           # 本文件
├── INTEGRATION_ARCHITECTURE.md         # 完整架构设计
├── QUICKSTART.md                       # 快速使用指南
└── skills_discovery.py                 # 核心服务实现

scripts/
└── ccb-skills                          # CLI 管理工具
```

---

## 🎯 核心功能

### 1. 自动发现技能
根据用户任务自动发现相关 Claude Code Skills

### 2. 智能推荐
基于关键词匹配 + 历史使用的混合算法

### 3. 持续学习
记录每次技能使用，优化未来推荐准确度

### 4. 记忆扩展
技能使用记录存储到 CCB 记忆系统

---

## 🚀 快速开始

### 1. 启动 Gateway Server

```bash
cd ~/.local/share/codex-dual
python3 -m lib.gateway.gateway_server --port 8765
```

系统会自动初始化 Skills Discovery Service。

### 2. 使用自动推荐

```bash
# Gateway 会自动发现相关技能
ccb-cli kimi "帮我创建一个 PDF"

# Gateway 输出:
# [MemoryMiddleware] 💡 发现 1 个相关 Skill: /pdf
```

### 3. 手动查找技能

```bash
# 推荐相关技能
ccb-skills recommend "build a React app"

# 查看统计
ccb-skills stats

# 刷新缓存
ccb-skills scan
```

---

## 📊 系统架构

```
用户请求
    │
    ├─→ Memory Middleware: Pre-Request
    │   ├─→ 提取关键词
    │   ├─→ Skills Discovery Service
    │   │   ├─→ 搜索 skills_cache (本地)
    │   │   ├─→ 搜索 skills_usage (历史)
    │   │   └─→ 计算相关性得分
    │   └─→ 注入推荐到上下文
    │
    ├─→ Provider 处理请求
    │
    └─→ Memory Middleware: Post-Response
        ├─→ 记录对话
        └─→ 记录技能使用
```

**详细架构:** 查看 [INTEGRATION_ARCHITECTURE.md](INTEGRATION_ARCHITECTURE.md)

---

## 💾 数据库

### skills_cache 表

存储所有已知技能的元数据:

```sql
CREATE TABLE skills_cache (
    skill_name TEXT PRIMARY KEY,
    description TEXT,
    triggers TEXT,              -- JSON array
    source TEXT,                -- 'local' | 'remote'
    installed INTEGER,          -- 0 | 1
    last_updated TEXT,
    metadata TEXT              -- JSON
);
```

### skills_usage 表

记录技能使用历史（用于学习）:

```sql
CREATE TABLE skills_usage (
    id INTEGER PRIMARY KEY,
    skill_name TEXT,
    task_keywords TEXT,
    provider TEXT,
    timestamp TEXT,
    success INTEGER            -- 0 | 1
);
```

---

## 🛠️ CLI 命令

### ccb-skills scan
刷新技能缓存（扫描 `~/.claude/skills/`）

```bash
ccb-skills scan
# ✓ Skills cache refreshed
```

### ccb-skills recommend "<task>"
获取任务相关的技能推荐

```bash
ccb-skills recommend "create a PDF"
# 💡 发现 1 个相关 Skill: /pdf
```

### ccb-skills match "<task>"
查找匹配的技能（详细输出）

```bash
ccb-skills match "build React component"
# ✓ 发现 2 个相关 Skill: /frontend-design, /webapp-testing
#
#   frontend-design (✓ Installed)
#     Score: 22
#     Create production-grade frontend interfaces
#     Usage: /frontend-design
```

### ccb-skills stats
查看使用统计

```bash
ccb-skills stats
# 📊 Skills Statistics
#   Total skills in cache: 53
#   Installed skills: 45
#   Total usage records: 127
#
#   Top 10 most used skills:
#     - pdf: 23 uses
#     - xlsx: 18 uses
#     ...
```

### ccb-skills list [--installed]
列出所有技能

```bash
# 所有技能
ccb-skills list

# 仅已安装
ccb-skills list --installed
```

---

## 🔧 配置

### ~/.ccb/gateway_config.json

```json
{
  "skills": {
    "auto_discover": true,           // 自动发现技能
    "recommend_skills": true,        // 推荐技能给用户
    "max_recommendations": 3,        // 最多推荐 3 个
    "cache_ttl_hours": 24            // 缓存过期时间
  }
}
```

**修改配置后需要重启 Gateway Server。**

---

## 📖 Python API

```python
from lib.skills.skills_discovery import SkillsDiscoveryService

# 初始化
service = SkillsDiscoveryService()

# 刷新缓存
service._refresh_cache()

# 获取推荐
recommendations = service.get_recommendations("create a PDF")
# {
#   'found': True,
#   'skills': [
#     {
#       'name': 'pdf',
#       'description': '...',
#       'relevance_score': 23,
#       'installed': True,
#       'usage_command': '/pdf'
#     }
#   ],
#   'message': '💡 发现 1 个相关 Skill: /pdf'
# }

# 记录使用
service.record_usage(
    skill_name="pdf",
    task_keywords="create PDF document",
    provider="kimi",
    success=True
)
```

---

## 🧠 推荐算法

### 相关性得分计算

```python
score = 0

# 1. 名称匹配 (最重要)
if keyword in skill_name:
    score += 10

# 2. 描述匹配
if keyword in description:
    score += 5

# 3. 触发器匹配
if keyword in triggers:
    score += 3

# 4. 已安装 bonus
if installed:
    score += 2

# 5. 历史使用 boost (基于 skills_usage 表)
history_count = count_usage(skill_name, keyword)
score += min(history_count, 5)  # Cap at +5 per keyword
```

### 示例

**Task:** "帮我创建一个 PDF"
**Keywords:** ["create", "PDF"]

**Skill: pdf**
- 名称匹配 "pdf": +10
- 描述匹配 "create": +5
- 已安装: +2
- 历史使用 2 次: +2
- **总分: 19**

**Skill: canvas-design**
- 描述匹配 "create": +5
- 已安装: +2
- **总分: 7**

**推荐:** pdf (score: 19) > canvas-design (score: 7)

---

## 📚 文档

| 文档 | 描述 |
|------|------|
| [INTEGRATION_ARCHITECTURE.md](INTEGRATION_ARCHITECTURE.md) | 完整架构设计、数据流程、数据库结构 |
| [QUICKSTART.md](QUICKSTART.md) | 快速使用指南、工作流示例、常见问题 |
| [skills_discovery.py](skills_discovery.py) | 核心服务实现（Python 代码） |

---

## 🔄 工作流示例

### 场景: 创建 PDF 报告

```
T0 - 首次使用
─────────────────
User: "创建一个 PDF 报告"
  ↓
Gateway: 发现 pdf skill (score: 15, 无历史)
  ↓
Kimi: 使用 /pdf skill
  ↓
Gateway: 记录使用 → skills_usage


T1 - 再次使用
─────────────────
User: "生成 PDF 文档"
  ↓
Gateway: 发现 pdf skill (score: 20, +5 历史)
  ↓
Kimi: 使用 /pdf skill
  ↓
Gateway: 记录使用


T2 - 相似任务
─────────────────
User: "制作 PDF 手册"
  ↓
Gateway: 发现 pdf skill (score: 25, +10 历史)
  ↓
Kimi: 自信使用 /pdf skill
  ↓
系统越用越聪明！
```

---

## 🎯 优势

### 1. 零配置
- 用户无需手动记录使用的技能
- 系统自动学习和优化

### 2. 智能推荐
- 关键词匹配 + 历史使用的混合算法
- 推荐准确度随使用提高

### 3. 完全透明
- 所有推荐都有得分和理由
- 可查看详细统计数据

### 4. 可扩展
- 支持本地 skills 扫描
- 可接入远程 find-skills API
- 未来可添加向量搜索

---

## 🚧 未来增强

### v0.20 (Q3 2026)

- [ ] **向量搜索** - 使用 Qdrant 实现语义匹配
- [ ] **远程 Skills Registry** - 连接中心化 skills 库
- [ ] **自动安装** - 发现未安装技能时自动安装
- [ ] **Skills 依赖图** - 管理技能间依赖关系

### v0.21 (Q4 2026)

- [ ] **个性化推荐** - 每个用户独立的使用偏好
- [ ] **A/B 测试** - 测试不同推荐算法效果
- [ ] **Skills 市场** - 社区共享和评分系统

---

## 🤝 贡献

### 改进推荐算法

如果你有更好的推荐算法:

1. Fork 仓库
2. 修改 `skills_discovery.py` 中的 `_rank_skills()` 方法
3. 测试并提交 PR

### 添加新功能

```bash
# 1. 克隆仓库
git clone https://github.com/LeoLin990405/ai-router-ccb.git

# 2. 创建分支
git checkout -b feature/better-matching

# 3. 开发并测试
python3 -m pytest tests/

# 4. 提交 PR
```

---

## 📝 更新日志

### v0.19-alpha (2026-02-04)

- ✨ 初始版本
- ✅ Skills Discovery Service 实现
- ✅ Memory Middleware 集成
- ✅ CLI 工具 (ccb-skills)
- ✅ 数据库架构设计
- ✅ 完整文档

---

## 📞 支持

- 📧 邮箱: [your-email@example.com]
- 🐛 问题: [GitHub Issues](https://github.com/LeoLin990405/ai-router-ccb/issues)
- 📖 文档: [完整文档](https://your-docs-site.com)

---

## 📜 许可

MIT License - 详见 [LICENSE](../../LICENSE)

---

**Made with ❤️ by the CCB Team**

**[⬆ Back to Top](#ccb-skills-discovery-module)**
