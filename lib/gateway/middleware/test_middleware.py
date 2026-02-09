#!/usr/bin/env python3
"""
测试 Memory Middleware 集成
"""

import asyncio
import sys
from pathlib import Path

from lib.common.logging import get_logger

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.gateway.middleware.memory_middleware import MemoryMiddleware


logger = get_logger("gateway.middleware.test")


async def test_middleware():
    """测试中间件功能"""
    logger.info("%s", "=" * 60)
    logger.info("CCB Memory Middleware 集成测试")
    logger.info("%s", "=" * 60)

    middleware = MemoryMiddleware()

    # 测试 1: Pre-request hook
    logger.info("\n[Test 1] Pre-Request Hook")
    logger.info("%s", "-" * 60)

    request = {
        "provider": "kimi",
        "message": "如何做前端开发？我想用 React",
        "user_id": "test_user"
    }

    enhanced_request = await middleware.pre_request(request)

    logger.info("\n原始消息长度: %s", len(request["message"]))
    logger.info("增强后长度: %s", len(enhanced_request["message"]))
    logger.info("记忆已注入: %s", enhanced_request.get("_memory_injected", False))
    logger.info("注入记忆数: %s", enhanced_request.get("_memory_count", 0))

    if enhanced_request.get("_recommendation"):
        rec = enhanced_request["_recommendation"]
        logger.info("推荐 Provider: %s (%s)", rec["provider"], rec["reason"])

    # 测试 2: Post-response hook
    logger.info("\n[Test 2] Post-Response Hook")
    logger.info("%s", "-" * 60)

    response = {
        "response": "建议使用 Gemini 3f 模型，它特别擅长 React 和 Tailwind CSS 开发。",
        "latency_ms": 1500,
        "tokens": 150
    }

    await middleware.post_response(request, response)
    logger.info("✓ 对话已记录到数据库")

    # 测试 3: 统计信息
    logger.info("\n[Test 3] 统计信息")
    logger.info("%s", "-" * 60)

    stats = middleware.get_stats()
    logger.info("Middleware 启用: %s", stats["enabled"])
    logger.info("自动注入: %s", stats["auto_inject"])
    logger.info("自动记录: %s", stats["auto_record"])
    logger.info("\n记忆统计:")
    memory_stats = stats["memory_stats"]
    logger.info("  总对话数: %s", memory_stats.get("total_conversations", 0))
    logger.info("  Provider 分布: %s", memory_stats.get("by_provider", {}))

    # 测试 4: 第二次查询（验证记忆注入）
    logger.info("\n[Test 4] 第二次查询（应注入记忆）")
    logger.info("%s", "-" * 60)

    request2 = {
        "provider": "kimi",
        "message": "创建一个登录页面",
        "user_id": "test_user"
    }

    enhanced_request2 = await middleware.pre_request(request2)

    if enhanced_request2.get('_memory_injected'):
        logger.info("✓ 成功注入 %s 条相关记忆", enhanced_request2["_memory_count"])
        logger.info("\n增强后的 Prompt 预览:")
        logger.info("%s", "-" * 60)
        logger.info("%s", enhanced_request2["message"][:500])
        logger.info("...")
    else:
        logger.info("✗ 未找到相关记忆")

    logger.info("\n%s", "=" * 60)
    logger.info("测试完成！")
    logger.info("%s", "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_middleware())
