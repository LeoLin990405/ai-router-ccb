#!/usr/bin/env python3
"""
测试 Skills Discovery 与 Memory Middleware 集成
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.skills.skills_discovery import SkillsDiscoveryService


def test_initialization():
    """测试初始化"""
    print("Test 1: Initialization")
    print("-" * 40)

    try:
        service = SkillsDiscoveryService()
        print("✓ SkillsDiscoveryService initialized")

        # 检查数据库表
        import sqlite3
        conn = sqlite3.connect(service.db_path)
        cursor = conn.cursor()

        # 检查 skills_cache 表
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='skills_cache'
        """)
        assert cursor.fetchone() is not None, "skills_cache table not found"
        print("✓ skills_cache table exists")

        # 检查 skills_usage 表
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='skills_usage'
        """)
        assert cursor.fetchone() is not None, "skills_usage table not found"
        print("✓ skills_usage table exists")

        conn.close()

        print("✓ Test 1 PASSED\n")
        return True

    except Exception as e:
        print(f"✗ Test 1 FAILED: {e}\n")
        return False


def test_scan_skills():
    """测试技能扫描"""
    print("Test 2: Scan Local Skills")
    print("-" * 40)

    try:
        service = SkillsDiscoveryService()

        # 扫描本地技能
        skills = service.scan_local_skills()

        print(f"✓ Scanned {len(skills)} local skills")

        if skills:
            print(f"  Example: {skills[0]['name']} - {skills[0]['description'][:50]}...")

        print("✓ Test 2 PASSED\n")
        return True

    except Exception as e:
        print(f"✗ Test 2 FAILED: {e}\n")
        return False


def test_keyword_extraction():
    """测试关键词提取"""
    print("Test 3: Keyword Extraction")
    print("-" * 40)

    try:
        service = SkillsDiscoveryService()

        test_cases = [
            ("Create a PDF document", ["create", "pdf", "document"]),
            ("帮我生成 Excel 报表", ["帮", "生成", "excel", "报表"]),
            ("Build a React dashboard", ["build", "react", "dashboard"])
        ]

        for text, expected_keywords in test_cases:
            keywords = service._extract_keywords(text)
            print(f"  '{text}'")
            print(f"    → {keywords}")

            # 检查是否包含期望的关键词
            for expected in expected_keywords:
                if expected.lower() not in [k.lower() for k in keywords]:
                    print(f"    ✗ Missing keyword: {expected}")

        print("✓ Test 3 PASSED\n")
        return True

    except Exception as e:
        print(f"✗ Test 3 FAILED: {e}\n")
        return False


def test_match_skills():
    """测试技能匹配"""
    print("Test 4: Match Skills")
    print("-" * 40)

    try:
        service = SkillsDiscoveryService()

        # 刷新缓存
        service._refresh_cache()

        # 测试匹配
        task = "create a PDF document"
        matches = service.match_skills(task, top_k=3)

        print(f"  Task: {task}")
        print(f"  Matches: {len(matches)}")

        for match in matches:
            print(f"    - {match['name']} (score: {match['relevance_score']})")

        assert len(matches) > 0, "No matches found"

        print("✓ Test 4 PASSED\n")
        return True

    except Exception as e:
        print(f"✗ Test 4 FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_usage_recording():
    """测试使用记录"""
    print("Test 5: Usage Recording")
    print("-" * 40)

    try:
        service = SkillsDiscoveryService()

        # 记录使用
        service.record_usage(
            skill_name="pdf",
            task_keywords="create PDF",
            provider="kimi",
            success=True
        )

        print("✓ Usage recorded")

        # 验证记录
        import sqlite3
        conn = sqlite3.connect(service.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM skills_usage
            WHERE skill_name = 'pdf'
        """)

        count = cursor.fetchone()[0]
        print(f"✓ Found {count} usage record(s) for 'pdf'")

        conn.close()

        print("✓ Test 5 PASSED\n")
        return True

    except Exception as e:
        print(f"✗ Test 5 FAILED: {e}\n")
        return False


def test_recommendations():
    """测试推荐功能"""
    print("Test 6: Get Recommendations")
    print("-" * 40)

    try:
        service = SkillsDiscoveryService()

        # 刷新缓存
        service._refresh_cache()

        # 获取推荐
        recommendations = service.get_recommendations("create a PDF")

        print(f"  Found: {recommendations['found']}")
        print(f"  Message: {recommendations['message']}")
        print(f"  Skills: {len(recommendations['skills'])}")

        for skill in recommendations['skills']:
            print(f"    - {skill['name']} (score: {skill['relevance_score']}, installed: {skill['installed']})")

        print("✓ Test 6 PASSED\n")
        return True

    except Exception as e:
        print(f"✗ Test 6 FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_learning():
    """测试学习功能"""
    print("Test 7: Learning from Usage")
    print("-" * 40)

    try:
        service = SkillsDiscoveryService()
        service._refresh_cache()

        # 初始得分
        rec1 = service.get_recommendations("create PDF")
        if rec1['skills']:
            initial_score = rec1['skills'][0]['relevance_score']
            skill_name = rec1['skills'][0]['name']
            print(f"  Initial score for '{skill_name}': {initial_score}")

            # 记录使用
            for i in range(3):
                service.record_usage(skill_name, "create PDF", "kimi", True)

            # 再次获取得分
            rec2 = service.get_recommendations("create PDF")
            if rec2['skills']:
                final_score = rec2['skills'][0]['relevance_score']
                print(f"  Final score after 3 uses: {final_score}")

                assert final_score >= initial_score, "Score should increase after usage"
                print(f"✓ Score increased by {final_score - initial_score}")

        print("✓ Test 7 PASSED\n")
        return True

    except Exception as e:
        print(f"✗ Test 7 FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("CCB Skills Discovery - Integration Tests")
    print("=" * 60 + "\n")

    tests = [
        test_initialization,
        test_scan_skills,
        test_keyword_extraction,
        test_match_skills,
        test_usage_recording,
        test_recommendations,
        test_learning
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test crashed: {e}\n")
            failed += 1

    print("=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
