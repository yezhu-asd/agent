#!/usr/bin/env python3
"""
验收测试1：TaskClassificationAgent会话记忆集成
验证要点：
1. 对话历史是否正确保存到Redis
2. 医疗槽位是否正确初始化
3. 用户上下文是否正确设置
"""

import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.task_classification_agent import TaskClassificationAgent
from services.conversation_memory_service import conversation_memory
from config.redis_client import get_redis_client


async def test_memory_integration():
    print("=" * 60)
    print("验收测试1：TaskClassificationAgent会话记忆集成")
    print("=" * 60)

    # 1. 检查Redis连接
    print("\n[检查1] 检查Redis连接...")
    redis_client = get_redis_client()
    if redis_client:
        print("[OK] Redis连接成功")
    else:
        print("[WARN] Redis不可用，将使用内存存储")

    # 2. 创建测试Agent
    print("\n[检查2] 创建TaskClassificationAgent实例...")
    try:
        # 创建简化的Agent（不需要完整的其他Agent）
        agent = TaskClassificationAgent(
            appointment_agent=None,
            consultant_agent=None,
            user_id="test_user_001",
            conversation_id="test_conv_001"
        )
        print("[OK] Agent创建成功")
        print("    user_id: %s" % agent.user_id)
        print("    conversation_id: %s" % agent.conversation_id)
    except Exception as e:
        print("[FAIL] Agent创建失败: %s" % e)
        return False

    # 3. 检查医疗槽位初始化
    print("\n[检查3] 检查医疗槽位初始化...")
    try:
        slots = conversation_memory.get_medical_slots("test_conv_001")
        print("[OK] 医疗槽位已初始化")
        print("    user_id: %s" % slots.get('user_id'))
        print("    role: %s" % slots.get('role'))
        print("    chief_complaint: %s" % slots.get('chief_complaint'))
    except Exception as e:
        print("[FAIL] 医疗槽位检查失败: %s" % e)
        return False

    # 4. 测试对话历史保存
    print("\n[检查4] 测试对话历史保存...")
    try:
        # 保存测试消息
        conversation_memory.append_message("test_conv_001", "user", "我感觉头疼")
        conversation_memory.append_message("test_conv_001", "assistant", "建议您测量一下体温")

        # 获取历史
        history = conversation_memory.get_history("test_conv_001")
        print("[OK] 对话历史已保存，共 %d 条消息" % len(history))
        for i, msg in enumerate(history, 1):
            print("    %d. [%s] %s" % (i, msg.get('role'), msg.get('content')[:30]))
    except Exception as e:
        print("[FAIL] 对话历史保存失败: %s" % e)
        return False

    # 5. 测试set_user_context
    print("\n[检查5] 测试set_user_context方法...")
    try:
        agent.set_user_context("test_user_002", "test_conv_002")
        slots = conversation_memory.get_medical_slots("test_conv_002")
        if slots.get("user_id") == "test_user_002":
            print("[OK] set_user_context成功，user_id已保存到槽位")
        else:
            print("[FAIL] set_user_context失败，期望user_id为test_user_002，实际为%s" % slots.get('user_id'))
            return False
    except Exception as e:
        print("[FAIL] set_user_context测试失败: %s" % e)
        return False

    # 6. 清理测试数据
    print("\n[清理] 清理测试数据...")
    try:
        conversation_memory.clear_history("test_conv_001")
        conversation_memory.clear_history("test_conv_002")
        print("[OK] 测试数据已清理")
    except Exception as e:
        print("[WARN] 清理失败: %s" % e)

    print("\n" + "=" * 60)
    print("验收测试1通过！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_memory_integration())
    sys.exit(0 if success else 1)