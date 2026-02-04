#!/usr/bin/env python3
"""
CCB Skills Discovery 演示脚本

演示如何使用 Skills Discovery Service
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.skills.skills_discovery import SkillsDiscoveryService


def demo_basic_usage():
    """演示基本使用"""
    print("=" * 60)
    print("Demo 1: Basic Usage")
    print("=" * 60)

    # 初始化服务
    service = SkillsDiscoveryService()

    # 刷新缓存
    print("\n🔄 Refreshing skills cache...")
    service._refresh_cache()

    # 获取推荐
    print("\n💡 Getting recommendations for: 'create a PDF document'\n")
    recommendations = service.get_recommendations("create a PDF document")

    print(recommendations['message'])
    print()

    for skill in recommendations['skills']:
        print(f"  • {skill['name']} (score: {skill['relevance_score']})")
        print(f"    {skill['description']}")
        if skill['installed']:
            print(f"    ✓ Usage: {skill['usage_command']}")
        else:
            print(f"    ⚠️ Not installed")
        print()


def demo_learning():
    """演示学习功能"""
    print("=" * 60)
    print("Demo 2: Learning from Usage")
    print("=" * 60)

    service = SkillsDiscoveryService()

    # 初始推荐
    print("\n📊 Initial recommendation for 'create PDF':\n")
    rec1 = service.get_recommendations("create PDF")
    if rec1['skills']:
        skill1 = rec1['skills'][0]
        print(f"  {skill1['name']}: score = {skill1['relevance_score']}")

    # 记录使用
    print("\n✍️  Recording usage...")
    service.record_usage("pdf", "create PDF", "kimi", success=True)
    service.record_usage("pdf", "create PDF", "kimi", success=True)

    # 再次推荐
    print("\n📈 After 2 uses:\n")
    rec2 = service.get_recommendations("create PDF")
    if rec2['skills']:
        skill2 = rec2['skills'][0]
        print(f"  {skill2['name']}: score = {skill2['relevance_score']}")

    print("\n✓ Score increased due to usage history!")


def demo_multiple_keywords():
    """演示多关键词匹配"""
    print("=" * 60)
    print("Demo 3: Multiple Keyword Matching")
    print("=" * 60)

    service = SkillsDiscoveryService()

    tasks = [
        "build a React dashboard",
        "create Excel spreadsheet",
        "design presentation slides",
        "write SQL query"
    ]

    for task in tasks:
        print(f"\n📝 Task: {task}")
        recommendations = service.get_recommendations(task)

        if recommendations['skills']:
            top_skill = recommendations['skills'][0]
            print(f"   → Recommended: {top_skill['name']} (score: {top_skill['relevance_score']})")
        else:
            print(f"   → No recommendations")


def demo_stats():
    """演示统计功能"""
    print("=" * 60)
    print("Demo 4: Usage Statistics")
    print("=" * 60)

    import sqlite3
    service = SkillsDiscoveryService()

    conn = sqlite3.connect(service.db_path)
    cursor = conn.cursor()

    # 总统计
    cursor.execute("SELECT COUNT(*) FROM skills_cache")
    total_skills = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM skills_cache WHERE installed = 1")
    installed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM skills_usage")
    total_usage = cursor.fetchone()[0]

    print(f"\n📊 Statistics:")
    print(f"  Total skills: {total_skills}")
    print(f"  Installed: {installed}")
    print(f"  Total usage records: {total_usage}")

    # Top skills
    cursor.execute("""
        SELECT skill_name, COUNT(*) as count
        FROM skills_usage
        GROUP BY skill_name
        ORDER BY count DESC
        LIMIT 5
    """)

    top_skills = cursor.fetchall()

    if top_skills:
        print(f"\n🏆 Top 5 most used skills:")
        for name, count in top_skills:
            print(f"  {name}: {count} uses")
    else:
        print(f"\n  No usage data yet")

    conn.close()


def main():
    """运行所有演示"""
    print("\n" + "=" * 60)
    print("CCB Skills Discovery - Interactive Demo")
    print("=" * 60 + "\n")

    try:
        # Demo 1: 基本使用
        demo_basic_usage()

        input("\nPress Enter to continue to Demo 2...")

        # Demo 2: 学习功能
        demo_learning()

        input("\nPress Enter to continue to Demo 3...")

        # Demo 3: 多关键词匹配
        demo_multiple_keywords()

        input("\nPress Enter to continue to Demo 4...")

        # Demo 4: 统计
        demo_stats()

        print("\n" + "=" * 60)
        print("✓ Demo completed!")
        print("=" * 60 + "\n")

        print("Next steps:")
        print("  1. Start Gateway Server:")
        print("     python3 -m lib.gateway.gateway_server --port 8765")
        print()
        print("  2. Use ccb-cli with automatic skill discovery:")
        print("     ccb-cli kimi 'create a PDF'")
        print()
        print("  3. Check stats:")
        print("     ccb-skills stats")
        print()

    except KeyboardInterrupt:
        print("\n\n✗ Demo interrupted")
        return 1

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
