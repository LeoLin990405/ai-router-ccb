#!/usr/bin/env python3
"""
测试 Memory Middleware 集成
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.gateway.middleware.memory_middleware import MemoryMiddleware


async def test_middleware():
    """测试中间件功能"""
    print("=" * 60)
    print("CCB Memory Middleware 集成测试")
    print("=" * 60)

    middleware = MemoryMiddleware()

    # 测试 1: Pre-request hook
    print("\n[Test 1] Pre-Request Hook")
    print("-" * 60)

    request = {
        "provider": "kimi",
        "message": "如何做前端开发？我想用 React",
        "user_id": "test_user"
    }

    enhanced_request = await middleware.pre_request(request)

    print(f"\n原始消息长度: {len(request['message'])}")
    print(f"增强后长度: {len(enhanced_request['message'])}")
    print(f"记忆已注入: {enhanced_request.get('_memory_injected', False)}")
    print(f"注入记忆数: {enhanced_request.get('_memory_count', 0)}")

    if enhanced_request.get("_recommendation"):
        rec = enhanced_request["_recommendation"]
        print(f"推荐 Provider: {rec['provider']} ({rec['reason']})")

    # 测试 2: Post-response hook
    print("\n[Test 2] Post-Response Hook")
    print("-" * 60)

    response = {
        "response": "建议使用 Gemini 3f 模型，它特别擅长 React 和 Tailwind CSS 开发。",
        "latency_ms": 1500,
        "tokens": 150
    }

    await middleware.post_response(request, response)
    print("✓ 对话已记录到数据库")

    # 测试 3: 统计信息
    print("\n[Test 3] 统计信息")
    print("-" * 60)

    stats = middleware.get_stats()
    print(f"Middleware 启用: {stats['enabled']}")
    print(f"自动注入: {stats['auto_inject']}")
    print(f"自动记录: {stats['auto_record']}")
    print(f"\n记忆统计:")
    memory_stats = stats['memory_stats']
    print(f"  总对话数: {memory_stats.get('total_conversations', 0)}")
    print(f"  Provider 分布: {memory_stats.get('by_provider', {})}")

    # 测试 4: 第二次查询（验证记忆注入）
    print("\n[Test 4] 第二次查询（应注入记忆）")
    print("-" * 60)

    request2 = {
        "provider": "kimi",
        "message": "创建一个登录页面",
        "user_id": "test_user"
    }

    enhanced_request2 = await middleware.pre_request(request2)

    if enhanced_request2.get('_memory_injected'):
        print(f"✓ 成功注入 {enhanced_request2['_memory_count']} 条相关记忆")
        print(f"\n增强后的 Prompt 预览:")
        print("-" * 60)
        print(enhanced_request2['message'][:500])
        print("...")
    else:
        print("✗ 未找到相关记忆")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_middleware())
