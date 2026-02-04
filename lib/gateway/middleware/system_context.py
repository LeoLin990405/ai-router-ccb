"""
System Context Builder
预加载所有 Skills、MCP Servers、Providers 信息
避免 Agent 在运行时反向查找
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.memory.registry import CCBRegistry


class SystemContextBuilder:
    """系统上下文构建器 - 预加载并格式化所有系统信息"""

    def __init__(self):
        self.registry = CCBRegistry()
        self.context_cache = None
        self.last_updated = None

        # 启动时预加载
        self._preload()

    def _preload(self):
        """预加载所有系统信息"""
        print("[SystemContext] Preloading system information...")

        try:
            # 扫描 skills
            skills = self.registry.scan_skills()
            print(f"[SystemContext] Loaded {len(skills)} skills")

            # 扫描 providers
            providers = self.registry.scan_providers()
            print(f"[SystemContext] Loaded {len(providers)} providers")

            # 扫描 MCP servers
            mcp_servers = self.registry.scan_mcp_servers()
            print(f"[SystemContext] Loaded {len(mcp_servers)} MCP servers")

            # 构建缓存
            self.context_cache = {
                "skills": skills,
                "providers": providers,
                "mcp_servers": mcp_servers,
                "metadata": {
                    "total_skills": len(skills),
                    "total_providers": len(providers),
                    "total_mcp_servers": len(mcp_servers)
                }
            }

            print("[SystemContext] Preload completed successfully")

        except Exception as e:
            print(f"[SystemContext] Preload error: {e}")
            self.context_cache = {
                "skills": [],
                "providers": [],
                "mcp_servers": [],
                "metadata": {}
            }

    def get_full_context(self) -> str:
        """
        获取完整的系统上下文（Markdown 格式）

        这个上下文会被注入到每次 AI 调用的 system prompt 中
        """
        if not self.context_cache:
            return ""

        parts = []

        # 1. 系统概览
        parts.append("# CCB System Context")
        parts.append("")
        parts.append("## 📊 System Overview")
        metadata = self.context_cache.get("metadata", {})
        parts.append(f"- **Available Skills**: {metadata.get('total_skills', 0)}")
        parts.append(f"- **AI Providers**: {metadata.get('total_providers', 0)}")
        parts.append(f"- **MCP Servers**: {metadata.get('total_mcp_servers', 0)}")
        parts.append("")

        # 2. AI Providers 信息
        parts.append("## 🤖 Available AI Providers")
        parts.append("")
        parts.append("| Provider | Models | Strengths | Use For |")
        parts.append("|----------|--------|-----------|---------|")

        providers = self.context_cache.get("providers", [])
        for provider in providers:
            name = provider.get("name", "unknown")
            models = ", ".join(provider.get("models", [])[:3])  # 最多显示 3 个
            strengths = ", ".join(provider.get("strengths", [])[:2])  # 最多显示 2 个
            use_cases = ", ".join(provider.get("use_cases", [])[:2])

            parts.append(f"| {name} | {models} | {strengths} | {use_cases} |")

        parts.append("")

        # 3. Skills 信息（分类）
        parts.append("## 🛠️ Available Skills")
        parts.append("")

        skills = self.context_cache.get("skills", [])

        # 按类别分组
        skills_by_category = self._group_skills_by_category(skills)

        for category, category_skills in skills_by_category.items():
            parts.append(f"### {category}")
            parts.append("")

            for skill in category_skills[:10]:  # 每个分类最多显示 10 个
                name = skill.get("name", "unknown")
                description = skill.get("description", "No description")
                triggers = skill.get("triggers", [])

                parts.append(f"- **{name}**: {description}")
                if triggers:
                    parts.append(f"  - Triggers: `{', '.join(triggers[:3])}`")

            parts.append("")

        # 4. MCP Servers 信息
        parts.append("## 🔌 Active MCP Servers")
        parts.append("")

        mcp_servers = self.context_cache.get("mcp_servers", [])
        if mcp_servers:
            for server in mcp_servers:
                name = server.get("name", "unknown")
                tools_count = len(server.get("tools", []))
                parts.append(f"- **{name}**: {tools_count} tools available")
        else:
            parts.append("- No MCP servers currently running")

        parts.append("")

        return "\n".join(parts)

    def get_relevant_context(self, keywords: List[str], provider: str) -> str:
        """
        获取与任务相关的上下文（精简版）

        Args:
            keywords: 任务关键词
            provider: 当前使用的 provider
        """
        if not self.context_cache:
            return ""

        parts = []

        # 1. 当前 Provider 信息
        parts.append("## 🤖 Current Provider")
        provider_info = self._get_provider_info(provider)
        if provider_info:
            parts.append(f"- **{provider}**: {provider_info.get('description', '')}")
            models = provider_info.get("models", [])
            if models:
                parts.append(f"- Available models: {', '.join(models[:5])}")
        parts.append("")

        # 2. 相关 Skills
        relevant_skills = self._find_relevant_skills(keywords)
        if relevant_skills:
            parts.append("## 🛠️ Relevant Skills")
            for skill in relevant_skills[:5]:  # 最多 5 个
                name = skill.get("name", "unknown")
                description = skill.get("description", "")
                parts.append(f"- **{name}**: {description}")
            parts.append("")

        # 3. MCP Servers（如果有）
        mcp_servers = self.context_cache.get("mcp_servers", [])
        if mcp_servers:
            parts.append("## 🔌 MCP Tools Available")
            for server in mcp_servers[:3]:  # 最多 3 个
                parts.append(f"- {server.get('name', 'unknown')}: {len(server.get('tools', []))} tools")
            parts.append("")

        return "\n".join(parts)

    def _group_skills_by_category(self, skills: List[Dict]) -> Dict[str, List[Dict]]:
        """按类别分组 skills"""
        categories = {
            "Product Management": [],
            "Development": [],
            "Documentation": [],
            "Collaboration": [],
            "Data & Analytics": [],
            "Other": []
        }

        for skill in skills:
            name = skill.get("name", "")

            # 基于名称判断类别
            if "lenny" in name.lower():
                categories["Product Management"].append(skill)
            elif any(x in name.lower() for x in ["frontend", "pptx", "xlsx", "pdf", "docx", "code"]):
                categories["Development"].append(skill)
            elif any(x in name.lower() for x in ["doc", "markdown", "obsidian", "note"]):
                categories["Documentation"].append(skill)
            elif any(x in name.lower() for x in ["ccb", "ask", "plan", "collaborate"]):
                categories["Collaboration"].append(skill)
            elif any(x in name.lower() for x in ["data", "sql", "analytics", "r-"]):
                categories["Data & Analytics"].append(skill)
            else:
                categories["Other"].append(skill)

        # 移除空分类
        return {k: v for k, v in categories.items() if v}

    def _get_provider_info(self, provider_name: str) -> Optional[Dict]:
        """获取特定 provider 的信息"""
        providers = self.context_cache.get("providers", [])
        for p in providers:
            if p.get("name") == provider_name:
                return p
        return None

    def _find_relevant_skills(self, keywords: List[str]) -> List[Dict]:
        """查找与关键词相关的 skills"""
        if not keywords:
            return []

        skills = self.context_cache.get("skills", [])
        relevant = []

        for skill in skills:
            name = skill.get("name", "").lower()
            description = skill.get("description", "").lower()
            triggers = [t.lower() for t in skill.get("triggers", [])]

            # 计算相关度
            score = 0
            for keyword in keywords:
                kw_lower = keyword.lower()
                if kw_lower in name:
                    score += 3
                if kw_lower in description:
                    score += 2
                if any(kw_lower in trigger for trigger in triggers):
                    score += 1

            if score > 0:
                skill["_relevance_score"] = score
                relevant.append(skill)

        # 按相关度排序
        relevant.sort(key=lambda x: x.get("_relevance_score", 0), reverse=True)

        return relevant

    def reload(self):
        """重新加载系统信息"""
        print("[SystemContext] Reloading system information...")
        self._preload()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.context_cache:
            return {}

        return self.context_cache.get("metadata", {})


# 测试代码
if __name__ == "__main__":
    builder = SystemContextBuilder()

    print("\n" + "=" * 60)
    print("Full Context (Markdown):")
    print("=" * 60)
    print(builder.get_full_context())

    print("\n" + "=" * 60)
    print("Relevant Context for '前端开发':")
    print("=" * 60)
    print(builder.get_relevant_context(["前端", "开发", "React"], "gemini"))

    print("\n" + "=" * 60)
    print("Stats:")
    print("=" * 60)
    print(json.dumps(builder.get_stats(), indent=2))
