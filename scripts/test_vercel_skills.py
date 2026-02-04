#!/usr/bin/env python3
"""
测试 Vercel Skills CLI 集成
"""

import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lib.skills.skills_discovery import SkillsDiscoveryService


def test_npx_skills_available():
    """测试 npx skills 是否可用"""
    print("=" * 60)
    print("Test 1: Verify npx skills CLI is available")
    print("=" * 60)

    try:
        result = subprocess.run(
            ["npx", "skills", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )

        print(f"✓ npx skills is available")
        print(f"  Version output: {result.stdout.strip() or result.stderr.strip()}")
        return True

    except Exception as e:
        print(f"✗ npx skills not available: {e}")
        print("\nInstall with:")
        print("  npm install -g skills")
        return False


def test_remote_search():
    """测试远程技能搜索"""
    print("\n" + "=" * 60)
    print("Test 2: Search Remote Skills")
    print("=" * 60)

    try:
        service = SkillsDiscoveryService()

        keywords = ["react", "testing"]
        print(f"\nSearching for: {keywords}\n")

        remote_skills = service.search_remote_skills(keywords)

        if remote_skills:
            print(f"✓ Found {len(remote_skills)} remote skills:")
            for skill in remote_skills[:3]:
                print(f"\n  • {skill['name']}")
                print(f"    {skill['description']}")
                print(f"    Install: {skill.get('install_command')}")
                print(f"    URL: {skill.get('url')}")
        else:
            print("  No remote skills found")

        return True

    except Exception as e:
        print(f"✗ Remote search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_combined_search():
    """测试本地+远程综合搜索"""
    print("\n" + "=" * 60)
    print("Test 3: Combined Local + Remote Search")
    print("=" * 60)

    try:
        service = SkillsDiscoveryService()

        task = "create a PDF document"
        print(f"\nTask: {task}\n")

        recommendations = service.get_recommendations(task)

        print(f"✓ {recommendations['message']}\n")

        for skill in recommendations['skills']:
            source_emoji = "📦" if skill['source'] == 'local' else "🌐"
            status = "✓ Installed" if skill['installed'] else "○ Not installed"

            print(f"{source_emoji} {skill['name']} ({status})")
            print(f"   Score: {skill['relevance_score']}")
            print(f"   {skill['description'][:60]}...")

            if skill['installed']:
                print(f"   Usage: {skill['usage_command']}")
            elif skill.get('install_command'):
                print(f"   Install: {skill['install_command']}")

            print()

        return True

    except Exception as e:
        print(f"✗ Combined search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Vercel Skills CLI Integration Tests")
    print("=" * 60 + "\n")

    tests = [
        test_npx_skills_available,
        test_remote_search,
        test_combined_search
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except KeyboardInterrupt:
            print("\n\n✗ Tests interrupted")
            return 1
        except Exception as e:
            print(f"✗ Test crashed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    if failed == 0:
        print("✓ All tests passed! Vercel Skills integration is working.\n")
        print("Next steps:")
        print("  1. Start Gateway Server:")
        print("     python3 -m lib.gateway.gateway_server --port 8765")
        print()
        print("  2. Test with ccb-cli:")
        print("     ccb-cli kimi 'help me with React testing'")
        print()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
